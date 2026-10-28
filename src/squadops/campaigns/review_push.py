"""A repository-backed Campaign's review request, pushed by the supervisor (SIP-0109 §24ci (b)).

The owner's ruling of 2026-10-28: the supervisor pushes the Campaign's one review request, at the
Campaign's close or when the owner asks for it mid-Campaign. It is an operator's act, never the
deploy's:
- **the token comes with the request,** as a contribution's does (``--token-from-gh``, the box's
  ``gh`` login). Nothing is stored in the deploy for it, and nothing pushes by itself;
- **the branch is the campaign branch's head,** pushed to the product as ``squadops/<campaign>``
  through the contribution path (``squadops.projects.contribution.push_campaign_review``). The
  first push opens the review request against the Project's base branch, and each later push
  moves the branch the open request follows;
- **after a rebase** (§24bv point 4) the head is no descendant of what was pushed, so the push is
  forced, with a lease on the commit the control log last recorded as pushed. A branch someone
  else moved since is refused, never overwritten. Every later push carries that lease, so one
  that isn't a rebase's refuses a moved branch too;
- **each push is a ``REVIEW_PUSHED`` row**, a record, accepted on a completed Campaign: the
  branch, the commit, the lease it was pushed under, whether it rewrote the branch, and the
  review request's address. Its commit is the next push's lease.

A push and its row can't share a transaction, and neither can the forge's review request (the
second review, SIP-0112 H.12, P1 on #2772). So each remote step is one a retry repeats safely:
- **the push** of a commit the product's branch already holds is up to date, and changes nothing;
- **the review request** is opened through the port's contract, which returns an open request of
  the same head against the same base rather than opening another
  (``ReviewRequestPort.open_review_request``). A retry after a crash between the forge's answer and
  the row recovers that request, and its row records the recovered address;
- **one push at a time per Campaign.** Retries that arrive together are serialized here, in this
  process, and each reads the control log afresh inside the lock: the second finds the first's row
  and is answered with it, with no remote call. The runtime API is one process; a second one
  would need the lock in the registry.
"""

from __future__ import annotations

import asyncio
import logging
import weakref
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from squadops.campaigns.campaign_branch import NoCampaignHead, branch_base, campaign_ref, head
from squadops.campaigns.models import (
    Campaign,
    CampaignError,
    CampaignTransition,
    ControlLogEntry,
    ControlOperation,
    ControlOutcome,
    TransitionResult,
)

logger = logging.getLogger(__name__)


#: One lock per Campaign, per event loop: a lock belongs to the loop it was first awaited on.
_PUSHING: weakref.WeakKeyDictionary[asyncio.AbstractEventLoop, dict[str, asyncio.Lock]] = (
    weakref.WeakKeyDictionary()
)


def _lock_for(campaign_id: str) -> asyncio.Lock:
    locks = _PUSHING.setdefault(asyncio.get_running_loop(), {})
    return locks.setdefault(campaign_id, asyncio.Lock())


class ReviewPushRefused(CampaignError):
    """A review request this Campaign can't push, and why. Nothing left the deploy."""


@dataclass(frozen=True)
class ReviewPush:
    """What one push recorded, and whether this request replayed a push already recorded."""

    branch: str
    commit: str
    lease: str | None
    forced: bool
    review_url: str
    entry_id: str
    replayed: bool

    @classmethod
    def of(cls, entry: ControlLogEntry, *, replayed: bool) -> ReviewPush:
        b = entry.binding
        return cls(
            b["branch"], b["commit"], b["lease"], b["forced"], b["review_url"], entry.entry_id,
            replayed,
        )  # fmt: skip


def _pushes(log: list[ControlLogEntry]) -> list[ControlLogEntry]:
    return [
        e
        for e in log
        if e.operation is ControlOperation.REVIEW_PUSHED and e.outcome is ControlOutcome.APPLIED
    ]


def _key(idempotency_key: str) -> str:
    return f"review-push:{idempotency_key}"


def _title(campaign: Campaign) -> str:
    return f"SquadOps campaign {campaign.campaign_id}: {campaign.objective.statement}"[:240]


def _body(campaign: Campaign, log: list[ControlLogEntry]) -> str:
    """What the review request says: the objective, and each increment and rebase on the branch."""
    lines = [campaign.objective.statement, "", "On the campaign branch:"]
    for e in log:
        if e.outcome is not ControlOutcome.APPLIED:
            continue
        b = e.binding
        if e.operation is ControlOperation.PROMOTE and b.get("cycle_id") and b.get("commit"):
            lines.append(f"- increment {b['cycle_id']}: {b['commit'][:12]}")
        elif e.operation is ControlOperation.BRANCH_REBASED:
            lines.append(f"- rebased onto {b['base'][:12]}: {b['commit'][:12]}")
    lines += ["", "Pushed by the campaign's supervisor (SIP-0109 §24ci (b)). The owner merges it."]
    return "\n".join(lines)


async def push_review(
    campaign_id: str,
    *,
    campaigns: Any,
    projects: Any,
    repository: Any,
    forge: Any,
    token: str,
    actor: str,
    actor_role: str,
    idempotency_key: str,
    record: Callable[[CampaignTransition], Awaitable[TransitionResult]] | None = None,
) -> ReviewPush:
    """Push the Campaign's review request (§24ci (b)), and record it, one push at a time per
    Campaign. A request whose key is recorded, or whose head is the one last pushed, is answered
    with that push, and nothing is pushed again. ``record`` commits the row (the route's, which
    projects it); by default the registry's own transition.

    Raises:
        ReviewPushRefused: A sample application's Campaign; a Project that doesn't contribute by
            review request; a branch with nothing on it upstream lacks; or a branch whose ref is
            behind its row (the sweep moves it). Nothing was pushed.
        squadops.projects.contribution.ContributionRefused: The contribution path refused it
            (no token, no forge, a base that isn't a branch). Nothing was pushed.
        squadops.projects.models.SourceUnavailable: The product refused the push, with reason
            ``lease_refused`` when someone else moved the branch since the last push.
    """
    async with _lock_for(campaign_id):
        return await _push_review(
            campaign_id,
            campaigns=campaigns,
            projects=projects,
            repository=repository,
            forge=forge,
            token=token,
            actor=actor,
            actor_role=actor_role,
            idempotency_key=idempotency_key,
            record=record,
        )


async def _push_review(
    campaign_id: str,
    *,
    campaigns: Any,
    projects: Any,
    repository: Any,
    forge: Any,
    token: str,
    actor: str,
    actor_role: str,
    idempotency_key: str,
    record: Callable[[CampaignTransition], Awaitable[TransitionResult]] | None,
) -> ReviewPush:
    """``push_review``'s body, under the Campaign's lock: every read of the log is inside it."""
    # deferred (pair): squadops.projects imports this package at load
    from squadops.projects.contribution import campaign_review_branch, push_campaign_review

    # deferred (pair): squadops.projects imports this package at load
    from squadops.projects.models import ContributionMode

    campaign = await campaigns.get_campaign(campaign_id)
    log = await campaigns.control_log(campaign_id)
    pushes = _pushes(log)
    for entry in pushes:
        if entry.idempotency_key == _key(idempotency_key):
            return ReviewPush.of(entry, replayed=True)
    project = await projects.get_project(campaign.project_id)
    if project.source is None:
        raise ReviewPushRefused(
            f"campaign {campaign_id} is on a sample application: it has no product to review"
        )
    if project.source.contribution_mode != ContributionMode.REVIEW_REQUEST:
        raise ReviewPushRefused(
            f"Project {project.project_id} contributes by {project.source.contribution_mode}: a "
            "campaign's review request is pushed only to a review_request Project"
        )
    try:
        at = head(campaign, log)
    except NoCampaignHead as e:
        raise ReviewPushRefused(str(e)) from e
    base = branch_base(log)
    if base is not None and at.commit == base.commit:
        raise ReviewPushRefused(
            f"campaign {campaign_id}'s branch is at its base {at.commit[:12]}: it holds nothing "
            "upstream doesn't, so there is nothing to review"
        )
    held = await repository.ref_commit(campaign.project_id, campaign_ref(campaign_id))
    if held != at.commit:
        raise ReviewPushRefused(
            f"campaign {campaign_id}'s branch ref names {str(held)[:12]}, and its control log's "
            f"head is {at.commit[:12]}: the sweep moves the ref to the row, then push again"
        )
    previous = pushes[-1] if pushes else None
    if previous is not None and previous.binding["commit"] == at.commit:
        return ReviewPush.of(previous, replayed=True)
    lease = previous.binding["commit"] if previous is not None else None
    forced = lease is not None and not await repository.is_ancestor(
        campaign.project_id, lease, at.commit
    )
    branch = campaign_review_branch(campaign_id)
    review_url = await push_campaign_review(
        project,
        campaign_id,
        lease=lease,
        review_url=previous.binding["review_url"] if previous is not None else None,
        title=_title(campaign),
        body=_body(campaign, log),
        repository=repository,
        forge=forge,
        token=token,
    )
    commit_row = record or (lambda t: campaigns.transition(campaign_id, t))
    result = await commit_row(
        CampaignTransition(
            operation=ControlOperation.REVIEW_PUSHED,
            actor=actor,
            actor_role=actor_role,
            reason=(
                f"the campaign's review request pushed: {branch} at {at.commit[:12]}"
                + (f", forced with a lease on {lease[:12]}" if forced and lease else "")
            ),
            idempotency_key=_key(idempotency_key),
            next_state=None,
            target=branch,
            binding={
                "branch": branch,
                "commit": at.commit,
                "lease": lease,
                "forced": forced,
                "review_url": review_url,
            },
        ),
    )
    logger.info(
        "campaign_review_pushed",
        extra={"campaign_id": campaign_id, "commit": at.commit, "forced": forced},
    )
    return ReviewPush.of(result.entry, replayed=result.replayed)
