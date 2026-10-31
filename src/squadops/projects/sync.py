"""Reading a Project's upstream against its approved development baseline (SIP-0112 FR-06,
FR-09, FR-21; E.4.4).

An outside developer advances the product, and SquadOps's own contributions may have been taken
in. A sync fetches the product's base ref through the managed clone and records:
- **the drift** from the approved development baseline to the upstream head, path by path, in
  the categories of evidence it invalidates (squadops.projects.drift), with what SquadOps's own
  integrated contributions account for apart from what changed outside it (#2606);
- **where each pending contribution stands:**
  - integrated, when its commit is in upstream's history, or when its review request was
    merged and the merge is (a squash merge makes a new commit);
  - closed, when its review request was closed unmerged;
  - pending otherwise.

A sync moves nothing else. The development baseline advances through validation, and the
Development Configuration and inherited baseline are recorded again at the new commit before a
unit relies on them. `prepare_cycle` refuses until they are, so the next unit can't develop on
evidence the drift invalidated (``unreconciled``, #2608).
"""

from __future__ import annotations

import logging
from collections.abc import Mapping, Sequence
from typing import Any

from squadops.projects.contribution import CLOSED, INTEGRATED, PENDING, Contribution
from squadops.projects.development_configuration import submission_digest
from squadops.projects.drift import ContributedChange, drift_between
from squadops.projects.models import ContributionMode, SourceUnavailable

logger = logging.getLogger(__name__)

SYNC_SCHEMA = "source-sync/v1"


class SyncRefused(RuntimeError):
    """A Project whose upstream can't be read against a baseline, with the reason."""


async def sync_project(
    project_id: str,
    *,
    registry: Any,
    repository: Any,
    forge: Any,
    tokens: Mapping[str, str],
    actor: str,
    idempotency_key: str,
) -> tuple[dict[str, Any], bool]:
    """Fetch upstream, name its drift from the approved baseline and where each pending
    contribution stands, and record both."""
    project = await registry.get_project(project_id)
    if project.source is None:
        raise SyncRefused(f"Project {project_id} is a sample application: it has no upstream")
    baseline = project.development_baseline_commit
    if baseline is None:
        raise SyncRefused(f"Project {project_id} has no development baseline: validate it first")
    source = project.source
    upstream = await repository.sync(
        project_id, source.repo_uri, source.base_ref, token=tokens.get(project_id)
    )
    contributions = []
    for contribution in await registry.contributions(project_id):
        if contribution.state == PENDING:
            state, integrated = await _standing(
                contribution, project, upstream, repository, forge, tokens
            )
            if state != PENDING:
                contribution = await registry.record_contribution_state(
                    project_id,
                    contribution.cycle_id,
                    contribution.run_id,
                    state=state,
                    integrated_commit=integrated,
                    actor=actor,
                )
        contributions.append(contribution)
    drift = None
    if upstream != baseline:
        configuration = await registry.get_development_configuration(project_id)
        old = await repository.tree_at(project_id, baseline)
        new = await repository.tree_at(project_id, upstream)
        drift = drift_between(
            project_id,
            baseline,
            upstream,
            old.files,
            new.files,
            configuration,
            contributed=await _contributed_since(project_id, baseline, contributions, repository),
        ).to_document()
    document = {
        "schema": SYNC_SCHEMA,
        "project_id": project_id,
        "baseline_commit": baseline,
        "upstream_commit": upstream,
        "drift": drift,
        "contributions": [c.to_document() for c in contributions],
    }
    return await registry.record_sync(
        document,
        actor=actor,
        idempotency_key=idempotency_key,
        request_hash=submission_digest({"project_id": project_id, "upstream": upstream}),
    )


def unreconciled(syncs: Sequence[Mapping[str, Any]], baseline: str) -> Mapping[str, Any] | None:
    """The latest sync, when it read upstream past ``baseline`` with drift in evidence a unit relies
    on (#2608): a unit on the older evidence is refused until the Project is reconciled at the new
    commit. ``None`` when the latest sync found no such drift, or read a baseline since replaced,
    which validation advanced: the configuration and the inherited baseline are then each
    required at the new commit on their own."""
    if not syncs:
        return None
    latest = syncs[-1]
    drift = latest.get("drift") or {}
    if latest.get("baseline_commit") != baseline or not drift.get("relevant"):
        return None
    return latest


async def _contributed_since(
    project_id: str, baseline: str, contributions: Sequence[Contribution], repository: Any
) -> list[ContributedChange]:
    """The integrated contributions the baseline doesn't carry yet, oldest first, each with its
    commit's tree and its parent's. One whose trees can't be read is left out, and so its paths
    read as outside drift: a sync over-reports rather than hides a change (logged)."""
    changes = []
    for c in contributions:
        if c.state != INTEGRATED:
            continue
        try:
            if await repository.is_ancestor(project_id, c.commit, baseline):
                continue
            before = await repository.tree_at(project_id, c.parent_commit)
            after = await repository.tree_at(project_id, c.commit)
        except SourceUnavailable:
            logger.warning(
                "sync_contribution_unread project=%s cycle=%s commit=%s",
                project_id,
                c.cycle_id,
                c.commit,
                exc_info=True,
            )
            continue
        changes.append(ContributedChange(c.cycle_id, c.run_id, c.commit, before.files, after.files))
    return changes


async def _standing(
    contribution: Contribution,
    project: Any,
    upstream: str,
    repository: Any,
    forge: Any,
    tokens: Mapping[str, str],
) -> tuple[str, str | None]:
    """A pending contribution's standing against the upstream head: (state, integrated commit)."""
    project_id = project.project_id
    if await repository.is_ancestor(project_id, contribution.commit, upstream):
        return INTEGRATED, contribution.commit
    token = tokens.get(project_id)
    if (
        contribution.mode != ContributionMode.REVIEW_REQUEST
        or not contribution.review_url
        or forge is None
        or not token
    ):
        return PENDING, None
    request = await forge.review_request_state(url=contribution.review_url, token=token)
    if request.state == "closed":
        return CLOSED, None
    merged = request.merge_commit
    if request.state == "merged" and merged:
        try:
            if await repository.is_ancestor(project_id, merged, upstream):
                return INTEGRATED, merged
        except SourceUnavailable:
            pass  # merged into a branch this Project's base ref doesn't carry
    # merged on the forge, but not into the base ref this Project develops from
    return PENDING, None
