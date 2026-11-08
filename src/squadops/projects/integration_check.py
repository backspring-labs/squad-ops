"""The integration check a Campaign's draft makes, where it is drafted (SIP-0112 H.30; #2862).

The operator's supervisor reads a repository-backed Project's accepted Campaign work not yet in its
integrated commit (SIP-0109 §24dc), and the next Campaign's draft waits while any is listed. A
review request the owner merged on the forge reads ``contribution_pending`` until a sync records
it, and until then the draft waits on work that is in. So the draft step asks for this check first,
and the check, in one request:

1. **reads the set.** With no row ``contribution_pending`` or ``merged_not_synced`` it records
   nothing, and answers the set;
2. **syncs** (E.4.4): the managed clone fetches the base ref, and each pending review request's
   state is read on the forge. One merged into the base ref is recorded integrated against the
   commit that took it. A patch export, and a merge with a merge commit, are read by ancestry
   alone, which needs no forge and no forge token. The sync's key is the upstream commit's, so a
   second check at the same commit records no second sync: it replays the first;
3. **re-validates, within a bounded delegation,** when a row stands ``merged_not_synced`` and the
   sync completed: a READY Project, a contribution recorded integrated, and only the commit the sync
   just read, which carries it. The adoption is fenced on the baseline read before the fetch, so a
   validation another request overtook writes nothing and the Project is read again. Configure and
   baseline capture at the new commit are still required before a cycle, as after any
   re-validation (the owner's ruling of 2026-11-05);
4. **reads the set again,** from what is recorded, and answers it, each row with what it waits on.

**Nothing reaches the forge but a read.** The fetch is the managed clone's, and the forge is asked
only ``review_request_state``. Nothing is pushed, commented, merged or labelled.

**A merge state is never guessed.** A pending review request needs a token (the request's, else the
one the deploy holds for the Project) and a forge. Without them the merge isn't read, and the
answer says so with a typed reason, never "not merged". A fetch the remote refused for its
credentials is answered apart from a missing token. A sync that was needed and didn't complete
advances nothing: no re-validation follows it. A sync or a validation that fails is answered with
its reason and never retried in silence: the next check tries again, and says so.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from squadops.campaigns.models import CampaignState
from squadops.campaigns.unintegrated import Standing, UnintegratedIncrement, unintegrated_increments
from squadops.projects.contribution import PENDING
from squadops.projects.models import ContributionMode, ProjectLifecycleStatus, SourceUnavailable
from squadops.projects.sync import SyncRefused, sync_project, unreconciled
from squadops.projects.validation import validate_project


class NoSourceRepository(RuntimeError):
    """A sample application: it has no integrated commit, and its Campaigns contribute nothing."""


class Unread(StrEnum):
    """Why the sync a row needed didn't complete, so no merge state was read."""

    #: a pending review request needs a token, and neither the request nor the deploy holds one
    NO_TOKEN = "no_token"
    #: a pending review request needs a forge, and the deploy has none
    NO_FORGE = "no_forge"
    #: the sync was refused (a Project with no development baseline)
    SYNC_REFUSED = "sync_refused"
    #: the remote refused the fetch for its credentials: none given, or the ones given refused
    FETCH_UNAUTHORIZED = "fetch_unauthorized"
    #: the managed clone couldn't fetch the base ref for another reason
    SOURCE_UNAVAILABLE = "source_unavailable"
    #: the forge refused the read, or couldn't be reached
    FORGE_UNAVAILABLE = "forge_unavailable"


class WaitsOn(StrEnum):
    """What a row still listed waits on."""

    #: its Campaign hasn't closed, so nothing of it is contributed yet
    CAMPAIGN_OPEN = "campaign_open"
    #: its Campaign closed, and its contribution hasn't been opened
    CONTRIBUTION_NOT_OPENED = "contribution_not_opened"
    #: its contribution was read, and isn't in the base ref
    MERGE = "merge"
    #: the sync it needed didn't complete (``merge_state_unread`` says why)
    MERGE_STATE_UNREAD = "merge_state_unread"
    #: a sync recorded it integrated, and the re-validation that carries it hasn't happened
    REVALIDATION = "revalidation"
    #: its review request was closed unmerged
    CLOSED_UNMERGED = "closed_unmerged"


@dataclass(frozen=True)
class Failure:
    reason: str
    message: str


@dataclass(frozen=True)
class Waiting:
    increment: UnintegratedIncrement
    waits_on: WaitsOn
    clears_when: str


@dataclass(frozen=True)
class IntegrationCheck:
    project_id: str
    #: The Project's integrated commit before the check, and after it.
    integrated_commit_before: str | None
    integrated_commit: str | None
    #: The sync this check recorded, or replayed at the same upstream commit; ``None`` when none ran.
    sync: Mapping[str, Any] | None
    sync_replayed: bool
    #: Why the sync a row needed didn't complete; ``None`` when it did, or none was needed.
    merge_state_unread: Failure | None
    #: The commit this check moved the development baseline to; ``None`` when it didn't.
    revalidated_at: str | None
    #: Why a re-validation the set asked for didn't adopt; ``None`` when none failed.
    validation_failed: Failure | None
    #: The latest sync, when it read upstream past the baseline with drift in evidence a unit
    #: relies on (``sync.unreconciled``): new cycles are refused until the Project is reconciled.
    unreconciled: Mapping[str, Any] | None
    #: What is left, in the set's order, as recorded after the check.
    remaining: tuple[Waiting, ...]

    @property
    def clear(self) -> bool:
        """Every accepted increment is in the integrated commit: the draft may proceed."""
        return not self.remaining

    @property
    def next_step(self) -> str | None:
        """What the Project needs before a cycle on it starts, when the check moved its baseline
        or read drift that isn't reconciled; ``None`` otherwise."""
        if self.revalidated_at is not None:
            return (
                f"the Project was re-validated at {self.revalidated_at[:12]}: record its "
                "Development Configuration and capture its inherited baseline there before a cycle "
                "starts (squadops projects configure, projects baseline --capture)"
            )
        if self.unreconciled is not None:
            relevant = ", ".join(self.unreconciled["drift"]["relevant"])
            return (
                f"the upstream is at {self.unreconciled['upstream_commit'][:12]}, past the "
                f"baseline, with {relevant} changed: reconcile it at the new commit before a cycle "
                "starts (squadops projects validate, configure, baseline --capture)"
            )
        return None


def sync_key(project_id: str, upstream: str) -> str:
    """The check's sync key: one per Project and upstream commit."""
    return f"integration-check:{project_id}:sync:{upstream}"


def validation_key(project_id: str, baseline: str | None, adopted: str) -> str:
    """The check's re-validation key: one per move of the Project's baseline, from the baseline it
    read to the commit it adopts. A replay means that move was recorded, and a later check that
    reads another baseline has a key of its own, so a spent key never holds a retry back."""
    return f"integration-check:{project_id}:validate:{baseline}:{adopted}"


async def check_integration(
    project_id: str,
    *,
    registry: Any,
    repository: Any,
    forge: Any,
    campaigns: Any,
    goal_sets: Any,
    tokens: Mapping[str, str],
    actor: str,
) -> IntegrationCheck:
    """Sync and re-validate ``project_id`` where its unintegrated set asks for it, then answer the
    set that remains. ``tokens`` holds the Project's token, the request's or the deploy's; it is
    used for this request's fetch and forge reads only, and never recorded."""
    # deferred (pair): squadops.ports imports this package at load
    from squadops.ports.projects.review_request import ReviewRequestFailed

    project = await registry.get_project(project_id)
    if project.source is None:
        raise NoSourceRepository(
            f"{project_id} is a sample application: it has no integrated commit, and its "
            "Campaigns contribute nothing"
        )
    before = project.integrated_upstream_commit

    async def read(project: Any) -> list[UnintegratedIncrement]:
        return await unintegrated_increments(
            project,
            campaigns=campaigns,
            contributions=await registry.contributions(project_id),
            repository=repository,
            goal_sets=goal_sets,
        )

    rows = await read(project)
    token = tokens.get(project_id)
    synced: Mapping[str, Any] | None = None
    replayed, unread = False, None
    needed = {Standing.CONTRIBUTION_PENDING, Standing.MERGED_NOT_SYNCED}
    if any(r.standing in needed for r in rows):
        # A pending review request is read on the forge; anything else by ancestry alone.
        forge_read = any(
            c.state == PENDING and c.mode == ContributionMode.REVIEW_REQUEST and c.review_url
            for c in await registry.contributions(project_id)
        )
        if forge_read and not token:
            unread = Failure(
                Unread.NO_TOKEN,
                f"a pending review request is read on the forge, and there is no token for "
                f"{project_id}: pass one with the request, or hold one for the Project in "
                "projects.review_request_tokens",
            )
        elif forge_read and forge is None:
            unread = Failure(
                Unread.NO_FORGE, "this deploy has no forge to read a review request on"
            )
        else:
            try:
                synced, replayed = await sync_project(
                    project_id,
                    registry=registry,
                    repository=repository,
                    forge=forge,
                    tokens={project_id: token} if token else {},
                    actor=actor,
                    idempotency_key=lambda upstream: sync_key(project_id, upstream),
                )
            except SyncRefused as e:
                unread = Failure(Unread.SYNC_REFUSED, str(e))
            except SourceUnavailable as e:
                unread = _fetch_failure(e, project_id, token)
            except ReviewRequestFailed as e:
                unread = Failure(Unread.FORGE_UNAVAILABLE, str(e))
        # What is recorded now: a sync that failed part-way may have recorded some contributions.
        rows = await read(project)
    revalidated, failed = None, None
    if synced is not None and any(r.standing is Standing.MERGED_NOT_SYNCED for r in rows):
        revalidated, failed, project = await _revalidate(
            project,
            synced["upstream_commit"],
            registry=registry,
            repository=repository,
            token=token,
            actor=actor,
        )
        rows = await read(project)
        if failed is not None and not any(r.standing is Standing.MERGED_NOT_SYNCED for r in rows):
            failed = None  # another request's adoption carried it: nothing waits on this one
    finding = (
        unreconciled(await registry.source_syncs(project_id), project.development_baseline_commit)
        if project.development_baseline_commit
        else None
    )
    return IntegrationCheck(
        project_id=project_id,
        integrated_commit_before=before,
        integrated_commit=project.integrated_upstream_commit,
        sync=synced,
        sync_replayed=replayed,
        merge_state_unread=unread,
        revalidated_at=revalidated,
        validation_failed=failed,
        unreconciled=finding,
        remaining=tuple(_waiting(r, project, unread, failed) for r in rows),
    )


def _fetch_failure(e: SourceUnavailable, project_id: str, token: str | None) -> Failure:
    """A failed fetch, a refused credential told apart from the rest."""
    if e.reason != "unauthorized":
        return Failure(Unread.SOURCE_UNAVAILABLE, f"{e.reason}: {e}")
    if token:
        return Failure(
            Unread.FETCH_UNAUTHORIZED,
            f"the remote refused the token for {project_id}: {e}",
        )
    return Failure(
        Unread.FETCH_UNAUTHORIZED,
        f"the remote refused a fetch with no token: {e}. Pass one with the request, or hold one "
        f"for {project_id} in projects.review_request_tokens",
    )


async def _revalidate(
    project: Any,
    target: str,
    *,
    registry: Any,
    repository: Any,
    token: str | None,
    actor: str,
) -> tuple[str | None, Failure | None, Any]:
    """E.4.4's reconciliation, delegated to the drafting seat within bounds: a READY Project, and
    only ``target``, the upstream commit the sync just read and recorded a contribution integrated
    against. Returns (the commit this check adopted, the failure, the Project after)."""
    # deferred (pair): squadops.cycles imports this package at load
    from squadops.cycles.models import ProjectBaselineMovedError

    project_id = project.project_id
    if project.lifecycle_status is not ProjectLifecycleStatus.READY:
        return (
            None,
            Failure(
                "not_ready",
                f"{project_id} is {project.lifecycle_status.value}: only a READY Project is "
                "re-validated at its upstream's commit",
            ),
            project,
        )
    read_at = project.development_baseline_commit
    try:
        updated, _replayed = await validate_project(
            project_id,
            registry=registry,
            repository=repository,
            actor=actor,
            idempotency_key=lambda adopted: validation_key(project_id, read_at, adopted),
            tokens={project_id: token} if token else {},
            adopt_only=target,
        )
    except SourceUnavailable as e:
        return None, Failure(e.reason, f"{e.reason}: {e}"), project
    except ProjectBaselineMovedError as e:
        return (
            None,
            Failure(
                "baseline_moved",
                f"another validation moved the baseline to {e.held} while this one read "
                f"{read_at}: nothing was written, and the Project is read as it is now",
            ),
            await registry.get_project(project_id),
        )
    moved = updated.development_baseline_commit
    if moved != target:
        return (
            None,
            Failure(
                "superseded",
                f"the baseline is at {moved}, not {target}: the next check syncs and tries again",
            ),
            updated,
        )
    return (moved if moved != read_at else None), None, updated


def _waiting(
    row: UnintegratedIncrement, project: Any, unread: Failure | None, failed: Failure | None
) -> Waiting:
    """What ``row`` waits on, and what clears it."""
    where = row.review_url or "the contribution"
    base = project.source.base_ref
    if row.standing is Standing.NOT_CONTRIBUTED:
        if row.campaign_state != CampaignState.COMPLETED:
            return Waiting(
                row,
                WaitsOn.CAMPAIGN_OPEN,
                f"Campaign {row.campaign_id} is {row.campaign_state}: its contribution is opened "
                "after it closes",
            )
        return Waiting(
            row,
            WaitsOn.CONTRIBUTION_NOT_OPENED,
            f"the supervisor opens Campaign {row.campaign_id}'s contribution "
            f"(POST /api/v1/campaigns/{row.campaign_id}/contributions)",
        )
    if row.standing is Standing.CONTRIBUTION_PENDING:
        if unread is not None:
            return Waiting(
                row,
                WaitsOn.MERGE_STATE_UNREAD,
                f"its merge state wasn't read ({unread.reason}): {unread.message}",
            )
        if row.review_url is None:
            return Waiting(
                row,
                WaitsOn.MERGE,
                f"the exported change's commit lands in {base}, applied as it was exported: a "
                "patch export is read by ancestry alone; the next check records it",
            )
        return Waiting(
            row, WaitsOn.MERGE, f"the owner merges {where} into {base}; the next check records it"
        )
    if row.standing is Standing.MERGED_NOT_SYNCED:
        if unread is not None:
            why = f"the sync didn't complete ({unread.reason}: {unread.message})"
        elif failed is not None:
            why = f"the re-validation didn't adopt ({failed.reason}: {failed.message})"
        else:
            why = "the re-validation hasn't run"
        return Waiting(
            row,
            WaitsOn.REVALIDATION,
            f"the Project is re-validated at the commit that took it; {why}. The next check "
            "tries again",
        )
    return Waiting(
        row,
        WaitsOn.CLOSED_UNMERGED,
        f"the owner reopens {where} on the forge and merges it into {base} with a merge commit "
        "(a squash merge of a closed request can't be read), then syncs and re-validates the "
        f"Project (POST /api/v1/projects/{project.project_id}/syncs, then …/validate; squadops "
        "projects sync, then projects validate): this check reads only pending contributions, so "
        "it doesn't. Or the owner dismisses it "
        f"(POST /api/v1/campaigns/{row.campaign_id}/contribution-dismissal)",
    )
