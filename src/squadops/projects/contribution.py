"""A verified change, contributed through the product's own process (SIP-0112 FR-06; E.4.3).

A source-backed run captures its accepted change as one commit in the managed clone, under
``refs/squadops/<cycle>/<run>`` (squadops.execution.source_delivery). Contributing it is the
owner's act, once per run. The Project's contribution mode says what it is:
- ``patch_export``: the run's patch (``source_change.patch``) is the contribution, and nothing
  leaves the deploy;
- ``review_request``: the commit is pushed to the product's repository as ``squadops/<cycle>``,
  never forced, and a review request is opened against the Project's base branch, with the
  repository-scoped token the deploy holds for that Project.

A repository-backed Campaign's one review request is pushed through the same path, by the
supervisor at the Campaign's close or on request (SIP-0109 §24ci (b), ``push_campaign_review``),
with the token the request carries and none the deploy holds.

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
from squadops.projects.workspaces import captured_change

#: The modes 2.4 contributes through. A direct push is integration, and isn't delegated in 2.4.
CONTRIBUTION_MODES_MADE = (ContributionMode.PATCH_EXPORT, ContributionMode.REVIEW_REQUEST)
PENDING, INTEGRATED, CLOSED = "pending", "integrated", "closed"
CONTRIBUTION_STATES = (PENDING, INTEGRATED, CLOSED)
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
    #: The commit through which the product took it: its own, or a squash merge's (E.4.4).
    integrated_commit: str | None = None

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
            "integrated_commit": self.integrated_commit,
        }


def capture_ref(cycle_id: str, run_id: str) -> str:
    """Where a run's accepted change is kept in the managed clone."""
    return f"refs/squadops/{cycle_id}/{run_id}"


def review_branch(cycle_id: str) -> str:
    return f"squadops/{cycle_id}"


def campaign_review_branch(campaign_id: str) -> str:
    """Where a Campaign's one review request is pushed (SIP-0109 §24ci (b))."""
    return f"squadops/{campaign_id}"


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
    capture = captured_change(await registry.source_mappings(project_id), cycle_id, run_id)
    if capture is None:
        raise ContributionRefused(
            f"run {run_id} of cycle {cycle_id} captured no accepted change: only a change the "
            "product's own checks accepted is contributed"
        )
    parent = capture.parent
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
    token = tokens.get(project.project_id)
    source = _review_target(
        project,
        token,
        forge,
        no_token=(
            "pass the contributor's own with the request (`squadops projects contribute "
            "--token-from-gh`), or the deploy names one (projects.review_request_tokens)"
        ),
    )
    assert token is not None
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


def _review_target(project: Any, token: str | None, forge: Any, *, no_token: str) -> Any:
    """What a review request needs before anything is pushed: a token, a forge, and a base that is
    a branch. Returns the Project's source.

    Raises:
        ContributionRefused: One is missing, named, with ``no_token`` saying where a token comes
            from.
    """
    source = project.source
    if not token:
        raise ContributionRefused(
            f"no review-request token for Project {project.project_id}: {no_token}"
        )
    if forge is None:
        raise ContributionRefused("this runtime has no forge to open a review request on")
    if not source.base_ref.startswith(_HEADS):
        raise ContributionRefused(
            f"a review request targets a branch, and the Project's base is {source.base_ref}"
        )
    return source


async def push_campaign_review(
    project: Any,
    campaign_id: str,
    *,
    lease: str | None,
    review_url: str | None,
    title: str,
    body: str,
    repository: Any,
    forge: Any,
    token: str,
) -> str:
    """SIP-0109 §24ci (b): push a Campaign's branch to the product as its review branch, forced
    only with ``lease`` (``SourceRepositoryPort.push_campaign_branch``), and open its review
    request against the Project's base branch the first time (``review_url`` ``None``). A later
    push moves the branch the open request follows, and is answered with its address. The token
    comes with the request alone: a Campaign's push has no deploy token to fall back on.

    Raises:
        ContributionRefused: No token, no forge, or a base that isn't a branch. Nothing pushed.
        SourceUnavailable: The product refused the push (``lease_refused``: the branch moved).
        ReviewRequestFailed: The forge refused to open the request, after the push.
    """
    source = _review_target(
        project,
        token,
        forge,
        no_token="a campaign's review request is pushed with the supervisor's own token, passed "
        "with the request (`squadops campaigns push-review --token-from-gh`)",
    )
    branch = campaign_review_branch(campaign_id)
    await repository.push_campaign_branch(
        project.project_id,
        source.repo_uri,
        campaign_id=campaign_id,
        branch=branch,
        token=token,
        lease=lease,
    )
    if review_url is not None:
        return review_url
    # The port returns an open request of this head against this base rather than opening another,
    # so after a crash between the forge's answer and the Campaign's row this recovers it.
    return await forge.open_review_request(
        repo_uri=source.repo_uri,
        head=branch,
        base=source.base_ref.removeprefix(_HEADS),
        title=title,
        body=body,
        token=token,
    )
