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

A Campaign that closes with an accepted increment is contributed through it too (SIP-0109 §24dc,
#2861, ``contribute_campaign``): its branch's head, with the criterion files its increments placed
renamed out of the ``criterion_`` stem and moved off the root (#2860's interim, made the rule),
pushed as ``squadops/<campaign>`` and recorded as one of the Project's contributions, under the
Campaign's id and ``campaign`` where a run's cycle and run stand.

Either is recorded ``pending``. A review request opened is not integration (FR-06): the revision
the product takes is recorded when it takes it (E.4.4). A direct push is integration, which 2.4
doesn't delegate, so a ``direct_push`` Project is refused by name.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import PurePosixPath
from typing import Any

from squadops.campaigns.campaign_branch import campaign_ref
from squadops.campaigns.criterion_placement import CRITERION_STEM
from squadops.projects.development_configuration import submission_digest
from squadops.projects.models import ContributionMode
from squadops.projects.workspaces import captured_change

#: The modes 2.4 contributes through. A direct push is integration, and isn't delegated in 2.4.
CONTRIBUTION_MODES_MADE = (ContributionMode.PATCH_EXPORT, ContributionMode.REVIEW_REQUEST)
PENDING, INTEGRATED, CLOSED = "pending", "integrated", "closed"
CONTRIBUTION_STATES = (PENDING, INTEGRATED, CLOSED)
_HEADS = "refs/heads/"
#: A Campaign's contribution stands where a run's run id does (SIP-0109 §24dc): one per Campaign,
#: under the Campaign's id where the run's cycle id stands.
CAMPAIGN_RUN = "campaign"
#: Where a criterion file at the product's root goes in a Campaign's contribution (#2860).
CRITERION_DIRECTORY = "tests"


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

    @property
    def campaign_id(self) -> str | None:
        """The Campaign this contributes, for a Campaign's contribution (SIP-0109 §24dc)."""
        return self.cycle_id if self.run_id == CAMPAIGN_RUN else None

    def to_document(self) -> dict[str, Any]:
        return {
            "project_id": self.project_id,
            "campaign_id": self.campaign_id,
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


def campaign_contribution_ref(campaign_id: str) -> str:
    """Where a Campaign's contribution commit is kept in the managed clone (SIP-0109 §24dc): its
    branch's head with the criterion files moved. Beside the branch's own ref, never under it."""
    return f"refs/squadops/{campaign_id}/contribution"


def relocated_criterion_files(paths: Iterable[str], campaign_id: str) -> dict[str, str]:
    """Where each of a Campaign's criterion files goes in its contribution (#2860's interim, made
    the rule; SIP-0109 §24dc):
    - ``criterion_`` in the file's name becomes the Campaign's id, so no later Campaign's
      placement finds the name taken (§24cx);
    - a file at the root moves under ``tests/``.

    ``test_criterion_T1.py`` of ``cmp_b498332d326e…`` becomes ``tests/test_cmp_b498332d326e_T1.py``.
    A path whose name doesn't carry the stem is left where it is."""
    tag = campaign_id[:16]
    moves = {}
    for path in sorted(set(paths)):
        placed = PurePosixPath(path)
        if CRITERION_STEM not in placed.name:
            continue
        name = placed.name.replace(CRITERION_STEM, f"{tag}_", 1)
        directory = str(placed.parent)
        moves[path] = f"{CRITERION_DIRECTORY if directory in ('', '.') else directory}/{name}"
    return moves


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


async def contribute_campaign(
    project: Any,
    campaign_id: str,
    *,
    head: str,
    base: str,
    criterion_paths: Iterable[str],
    title: str,
    body: str,
    registry: Any,
    repository: Any,
    forge: Any,
    token: str | None,
    actor: str,
    idempotency_key: str,
) -> tuple[Contribution, bool]:
    """Contribute a closed Campaign's branch through the Project's mode, and record it pending
    (SIP-0109 §24dc, #2861).

    The commit is ``head`` with ``criterion_paths`` moved (``relocated_criterion_files``), as one
    commit on it, or ``head`` itself when none of them is on it. ``base`` is the branch's base, so
    the contribution's change is ``base..commit``.
    - ``review_request``: pushed as ``squadops/<campaign>``, never forced, and the review request
      opened. An open one a review push made is returned by the forge rather than duplicated
      (the port's contract), so the Campaign has one.
    - ``patch_export``: recorded, and nothing leaves the deploy.

    A Campaign already contributed is answered with its record, and nothing is pushed again.

    Raises:
        ContributionRefused: A sample application; a mode that is integration; no token, no forge,
            or a base that isn't a branch; a moved file's new path already held; a tree the clone
            can't commit whole. Nothing left the deploy.
        SourceUnavailable: The clone or the product refused, as a branch with other history is:
            never forced.
        ReviewRequestFailed: The forge refused to open the request, after the push.
    """
    project_id = project.project_id
    for existing in await registry.contributions(project_id):
        if (existing.cycle_id, existing.run_id) == (campaign_id, CAMPAIGN_RUN):
            return existing, True
    if project.source is None:
        raise ContributionRefused(
            f"Project {project_id} is a sample application: it has no product to contribute to"
        )
    mode = project.source.contribution_mode
    if mode not in CONTRIBUTION_MODES_MADE:
        raise ContributionRefused(
            f"Project {project_id} contributes by {mode}, which is integration: a Campaign "
            f"contributes by {' or '.join(CONTRIBUTION_MODES_MADE)}"
        )
    source = None
    if mode == ContributionMode.REVIEW_REQUEST:
        source = _review_target(
            project,
            token,
            forge,
            no_token=(
                "the deploy names none for it (projects.review_request_tokens), so the supervisor "
                "opens it with its own (`squadops campaigns contribute <campaign> --token-from-gh`)"
            ),
        )
    commit, moved = await _with_criteria_moved(
        project_id, campaign_id, head, criterion_paths, repository
    )
    branch = review_url = None
    if source is not None:
        assert token is not None
        branch = campaign_review_branch(campaign_id)
        await repository.push_capture(
            project_id,
            source.repo_uri,
            ref=campaign_contribution_ref(campaign_id) if moved else campaign_ref(campaign_id),
            branch=branch,
            token=token,
        )
        review_url = await forge.open_review_request(
            repo_uri=source.repo_uri,
            head=branch,
            base=source.base_ref.removeprefix(_HEADS),
            title=title,
            body=_moves_stated(body, moved),
            token=token,
        )
    contribution = Contribution(
        project_id=project_id,
        cycle_id=campaign_id,
        run_id=CAMPAIGN_RUN,
        commit=commit,
        parent_commit=base,
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
        request_hash=submission_digest({"project_id": project_id, "campaign_id": campaign_id}),
    )


async def _with_criteria_moved(
    project_id: str,
    campaign_id: str,
    head: str,
    criterion_paths: Iterable[str],
    repository: Any,
) -> tuple[str, dict[str, str]]:
    """The commit a Campaign contributes, and the files it moved: ``head`` when none of its
    criterion files is on it, or one commit on ``head`` with them moved. A retry reuses the commit
    an earlier attempt made at the contribution ref on this head, so a branch a crash left pushed
    is up to date rather than refused."""
    tree = await repository.tree_at(project_id, head)
    moves = {
        old: new
        for old, new in relocated_criterion_files(criterion_paths, campaign_id).items()
        if old in tree.files
    }
    if not moves:
        return head, {}
    taken = sorted(new for new in moves.values() if new in tree.files)
    if taken:
        raise ContributionRefused(
            f"the criterion files would move onto {', '.join(taken)}, which the branch already "
            "holds: never overwritten"
        )
    if tree.capability_gaps:
        raise ContributionRefused(
            "the branch's tree can't be committed whole with its criterion files moved: "
            + "; ".join(tree.capability_gaps)
        )
    ref = campaign_contribution_ref(campaign_id)
    held = await repository.ref_commit(project_id, ref)
    if held is not None and held != head and await repository.is_ancestor(project_id, head, held):
        return held, moves
    commit = await repository.commit_tree(
        project_id,
        parent=head,
        files={moves.get(path, path): content for path, content in tree.files.items()},
        executable={moves.get(path, path) for path in tree.executable},
        ref=ref,
        message=_moves_stated(
            f"SquadOps campaign {campaign_id}: its criterion files, renamed for the product\n\n"
            "Each keeps its test, under a name no later Campaign places (SIP-0109 §24dc).",
            moves,
        ),
    )
    return commit, moves


def _moves_stated(text: str, moves: Mapping[str, str]) -> str:
    """``text``, with the criterion files a contribution moved listed after it."""
    if not moves:
        return text
    lines = [f"- {old} -> {new}" for old, new in sorted(moves.items())]
    return "\n".join([text, "", "Criterion files moved (SIP-0109 §24dc):", *lines])
