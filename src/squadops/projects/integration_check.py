"""The integration check a Campaign's draft makes, where it is drafted (SIP-0112 H.30; #2862).

The operator's supervisor reads a repository-backed Project's accepted Campaign work not yet in its
integrated commit (SIP-0109 §24dc), and the next Campaign's draft waits while any is listed. A
review request the owner merged on the forge reads ``contribution_pending`` until a sync records
it, and until then the draft waits on work that is in. So the draft step asks for this check first,
and the check, in one request:

1. **reads the set.** With no row ``contribution_pending`` or ``merged_not_synced`` it records
   nothing, and answers the set;
2. **syncs,** when a row is ``contribution_pending`` (E.4.4): the managed clone fetches the base
   ref, and each pending review request's state is read on the forge. One merged into the base ref
   is recorded integrated against the commit that took it. The sync's key is the upstream commit's,
   so a second check at the same commit records no second sync: it replays the first;
3. **re-validates,** when a row stands ``merged_not_synced``: the development baseline and the
   integrated commit move to the upstream's commit, so the row is carried. New cycles then wait for
   configure and baseline capture at that commit, as after any re-validation (the owner's ruling of
   2026-11-05);
4. **reads the set again,** and answers it, each row with what it waits on.

**Nothing reaches the forge but a read.** The fetch is the managed clone's, and the forge is asked
only ``review_request_state``. Nothing is pushed, commented, merged or labelled.

**A merge state is never guessed.** Without a token (the request's, else the one the deploy holds
for the Project) or a forge, the merge isn't read, and the answer says so with a typed reason, so a
pending row is never read as "not merged". A sync or a validation the source or the forge refuses
is answered with its reason and never retried in silence: the next check tries again, and says so.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from squadops.campaigns.models import CampaignState
from squadops.campaigns.unintegrated import Standing, UnintegratedIncrement, unintegrated_increments
from squadops.ports.projects.review_request import ReviewRequestFailed
from squadops.projects.models import ProjectLifecycleStatus, SourceUnavailable
from squadops.projects.sync import SyncRefused, sync_project, unreconciled
from squadops.projects.validation import validate_project


class NoSourceRepository(RuntimeError):
    """A sample application: it has no integrated commit, and its Campaigns contribute nothing."""


class Unread(StrEnum):
    """Why a pending row's merge state wasn't read."""

    #: no token in the request, and none held for the Project
    NO_TOKEN = "no_token"
    #: the deploy has no forge to read a review request on
    NO_FORGE = "no_forge"
    #: the sync was refused (a Project with no development baseline)
    SYNC_REFUSED = "sync_refused"
    #: the managed clone couldn't fetch the base ref
    SOURCE_UNAVAILABLE = "source_unavailable"
    #: the forge refused the read, or couldn't be reached
    FORGE_UNAVAILABLE = "forge_unavailable"


class WaitsOn(StrEnum):
    """What a row still listed waits on."""

    #: its Campaign hasn't closed, so nothing of it is contributed yet
    CAMPAIGN_OPEN = "campaign_open"
    #: its Campaign closed, and its contribution hasn't been opened
    CONTRIBUTION_NOT_OPENED = "contribution_not_opened"
    #: its review request was read, and isn't merged into the base ref
    MERGE = "merge"
    #: its review request's merge state wasn't read (``merge_state_unread`` says why)
    MERGE_STATE_UNREAD = "merge_state_unread"
    #: a sync recorded it integrated, and the re-validation that carries it failed
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
    #: Why a pending row's merge state wasn't read; ``None`` when it was, or none was pending.
    merge_state_unread: Failure | None
    #: The commit the development baseline moved to; ``None`` when it didn't move.
    revalidated_at: str | None
    #: Why a re-validation the set asked for failed; ``None`` when none failed.
    validation_failed: Failure | None
    #: The latest sync, when it read upstream past the baseline with drift in evidence a unit
    #: relies on (``sync.unreconciled``): new cycles are refused until the Project is reconciled.
    unreconciled: Mapping[str, Any] | None
    #: What is left, in the set's order.
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


def validation_key(project_id: str, upstream: str) -> str:
    """The check's re-validation key: one per Project and the upstream commit synced."""
    return f"integration-check:{project_id}:validate:{upstream}"


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
    if any(r.standing is Standing.CONTRIBUTION_PENDING for r in rows):
        if not token:
            unread = Failure(
                Unread.NO_TOKEN,
                f"no token for {project_id}: pass one with the request, or hold one for the "
                "Project in projects.review_request_tokens",
            )
        elif forge is None:
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
                    tokens={project_id: token},
                    actor=actor,
                    idempotency_key=lambda upstream: sync_key(project_id, upstream),
                )
            except SyncRefused as e:
                unread = Failure(Unread.SYNC_REFUSED, str(e))
            except SourceUnavailable as e:
                unread = Failure(Unread.SOURCE_UNAVAILABLE, f"{e.reason}: {e}")
            except ReviewRequestFailed as e:
                unread = Failure(Unread.FORGE_UNAVAILABLE, str(e))
            else:
                rows = await read(project)
    revalidated, failed = None, None
    if any(r.standing is Standing.MERGED_NOT_SYNCED for r in rows):
        revalidated, failed, project = await _revalidate(
            project, synced, registry=registry, repository=repository, token=token, actor=actor
        )
        if revalidated is not None:
            rows = await read(project)
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


async def _revalidate(
    project: Any,
    synced: Mapping[str, Any] | None,
    *,
    registry: Any,
    repository: Any,
    token: str | None,
    actor: str,
) -> tuple[str | None, Failure | None, Any]:
    """E.4.4's reconciliation, for a row a sync recorded integrated: (the commit adopted, the
    failure, the Project after). Its key is the synced upstream commit's, so it runs once there."""
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
    if synced is None:
        syncs = await registry.source_syncs(project_id)
        upstream = syncs[-1]["upstream_commit"] if syncs else "unsynced"
    else:
        upstream = synced["upstream_commit"]
    try:
        updated, _ = await validate_project(
            project_id,
            registry=registry,
            repository=repository,
            actor=actor,
            idempotency_key=validation_key(project_id, upstream),
            tokens={project_id: token} if token else {},
        )
    except SourceUnavailable as e:
        return None, Failure(e.reason, f"{e.reason}: {e}"), project
    moved = updated.development_baseline_commit
    return (moved if moved != project.development_baseline_commit else None), None, updated


def _waiting(
    row: UnintegratedIncrement, project: Any, unread: Failure | None, failed: Failure | None
) -> Waiting:
    """What ``row`` waits on, and what clears it."""
    where = row.review_url or "the contribution"
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
        return Waiting(
            row,
            WaitsOn.MERGE,
            f"the owner merges {where} into {project.source.base_ref}; the next check records it",
        )
    if row.standing is Standing.MERGED_NOT_SYNCED:
        why = f" ({failed.reason}: {failed.message})" if failed is not None else ""
        return Waiting(
            row,
            WaitsOn.REVALIDATION,
            f"the Project is re-validated at the commit that took it{why}; the next check tries "
            "again",
        )
    return Waiting(
        row,
        WaitsOn.CLOSED_UNMERGED,
        f"the owner reopens {where} and merges it with a merge commit, or dismisses it "
        f"(POST /api/v1/campaigns/{row.campaign_id}/contribution-dismissal)",
    )
