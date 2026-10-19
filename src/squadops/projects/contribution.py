"""A verified change, contributed through the product's own process (SIP-0112 FR-06; E.4.3).

A source-backed run captures its accepted change as one commit in the managed clone, under
``refs/squadops/<cycle>/<run>`` (squadops.execution.source_delivery). Contributing it is the
owner's act, once per run. The Project's contribution mode says what it is:
- ``patch_export``: the run's patch (``source_change.patch``) is the contribution, and nothing
  leaves the deploy;
- ``review_request``: the commit is pushed to the product's repository as ``squadops/<cycle>``,
  never forced, and a review request is opened against the Project's base branch, with the
  repository-scoped token the deploy holds for that Project.

Either is recorded ``pending``. A review request opened is not integration (FR-06): the revision
the product takes is recorded when it takes it (E.4.4). A direct push is integration, which 2.4
doesn't delegate, so a ``direct_push`` Project is refused by name.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from squadops.projects.development_configuration import submission_digest
from squadops.projects.models import ContributionMode
from squadops.projects.workspaces import CAPTURED, SEEDED

#: The modes 2.4 contributes through. A direct push is integration, and isn't delegated in 2.4.
CONTRIBUTION_MODES_MADE = (ContributionMode.PATCH_EXPORT, ContributionMode.REVIEW_REQUEST)
PENDING = "pending"
CONTRIBUTION_STATES = (PENDING, "integrated", "closed")
_HEADS = "refs/heads/"


class ContributionRefused(RuntimeError):
    """A contribution that can't be made, with the reason. Nothing left the deploy."""


@dataclass(frozen=True)
class Contribution:
    project_id: str
    cycle_id: str
    run_id: str
    commit: str
    parent_commit: str
    mode: str
    state: str
    branch: str | None
    review_url: str | None
    contributed_by: str
    contributed_at: datetime

    def to_document(self) -> dict[str, Any]:
        return {
            "project_id": self.project_id,
            "cycle_id": self.cycle_id,
            "run_id": self.run_id,
            "commit": self.commit,
            "parent_commit": self.parent_commit,
            "mode": self.mode,
            "state": self.state,
            "branch": self.branch,
            "review_url": self.review_url,
            "contributed_by": self.contributed_by,
            "contributed_at": self.contributed_at.isoformat(),
        }


def capture_ref(cycle_id: str, run_id: str) -> str:
    """Where a run's accepted change is kept in the managed clone."""
    return f"refs/squadops/{cycle_id}/{run_id}"


def review_branch(cycle_id: str) -> str:
    return f"squadops/{cycle_id}"


async def contribute(
    project_id: str,
    cycle_id: str,
    run_id: str,
    *,
    registry: Any,
    repository: Any,
    forge: Any,
    tokens: Mapping[str, str],
    actor: str,
    idempotency_key: str,
) -> tuple[Contribution, bool]:
    """Contribute a run's captured change through the Project's mode, and record it pending.
    A run already contributed is answered with its record, and nothing is pushed again."""
    project = await registry.get_project(project_id)
    if project.source is None:
        raise ContributionRefused(
            f"Project {project_id} is a sample application: it has no product to contribute to"
        )
    for existing in await registry.contributions(project_id):
        if (existing.cycle_id, existing.run_id) == (cycle_id, run_id):
            return existing, True
    mappings = await registry.source_mappings(project_id)
    captured = [
        m
        for m in mappings
        if m.direction == CAPTURED
        and m.cycle_id == cycle_id
        and m.workspace_id.startswith(f"src-{run_id}-")
    ]
    if not captured:
        raise ContributionRefused(
            f"run {run_id} of cycle {cycle_id} captured no accepted change: only a change the "
            "product's own checks accepted is contributed"
        )
    capture = captured[-1]
    parent = next(
        m.commit
        for m in mappings
        if m.direction == SEEDED and m.workspace_id == capture.workspace_id
    )
    mode = project.source.contribution_mode
    branch = review_url = None
    if mode == ContributionMode.REVIEW_REQUEST:
        branch, review_url = await _open_review_request(
            project, cycle_id, run_id, capture.commit, repository, forge, tokens
        )
    elif mode != ContributionMode.PATCH_EXPORT:
        raise ContributionRefused(
            f"Project {project_id} contributes by {mode}, which is integration: 2.4 contributes "
            f"by {' or '.join(CONTRIBUTION_MODES_MADE)}"
        )
    contribution = Contribution(
        project_id=project_id,
        cycle_id=cycle_id,
        run_id=run_id,
        commit=capture.commit,
        parent_commit=parent,
        mode=mode,
        state=PENDING,
        branch=branch,
        review_url=review_url,
        contributed_by=actor,
        contributed_at=datetime.now(UTC),
    )
    return await registry.record_contribution(
        contribution,
        idempotency_key=idempotency_key,
        request_hash=submission_digest(
            {"project_id": project_id, "cycle_id": cycle_id, "run_id": run_id}
        ),
    )


async def _open_review_request(
    project: Any,
    cycle_id: str,
    run_id: str,
    commit: str,
    repository: Any,
    forge: Any,
    tokens: Mapping[str, str],
) -> tuple[str, str]:
    source = project.source
    token = tokens.get(project.project_id)
    if not token:
        raise ContributionRefused(
            f"the deploy holds no review-request token for Project {project.project_id} "
            "(projects.review_request_tokens): its owner names one, scoped to that repository"
        )
    if forge is None:
        raise ContributionRefused("this runtime has no forge to open a review request on")
    if not source.base_ref.startswith(_HEADS):
        raise ContributionRefused(
            f"a review request targets a branch, and the Project's base is {source.base_ref}"
        )
    message = await repository.commit_message(project.project_id, commit)
    title, _, body = message.partition("\n")
    branch = review_branch(cycle_id)
    await repository.push_capture(
        project.project_id,
        source.repo_uri,
        ref=capture_ref(cycle_id, run_id),
        branch=branch,
        token=token,
    )
    url = await forge.open_review_request(
        repo_uri=source.repo_uri,
        head=branch,
        base=source.base_ref.removeprefix(_HEADS),
        title=title,
        body=body.strip(),
        token=token,
    )
    return branch, url
