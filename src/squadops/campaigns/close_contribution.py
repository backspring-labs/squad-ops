"""A Campaign that closes with an accepted increment opens one contribution to the product
(SIP-0109 §24dc, #2861).

Campaigns 4 and 6 on ``prj-shelfnote`` closed with accepted increments that lived only on their
campaign branches, and the next Campaign started without them. So the close itself opens the
contribution:
- **the closing row says what is due.** The row that completes a repository-backed Campaign (its
  terminal decision, or the owner's abort) carries ``contribution``: ``due`` with the accepted
  increments, or not due with why (``no accepted increment``). It is written in the closing
  transaction, as a launch intent is written with its decision (§12b): the intent, never the act;
- **the act follows the commit.** Opening the review request is a push and a forge call, which
  can't join the control log's transaction. ``CampaignContribution.open`` makes it after the
  close commits, through the contribution path (``squadops.projects.contribution
  .contribute_campaign``): one commit on the branch's head with the criterion files moved
  (#2860's interim, made the rule), pushed as ``squadops/<campaign>``, recorded ``pending`` as the
  Project's contribution. Merging stays the owner's;
- **a failure is recorded, and retried.** Each attempt that fails writes a ``contribution_failed``
  row naming why, and the contribution stays due. It is attempted again at every startup, and
  when the supervisor asks (``POST /api/v1/campaigns/{id}/contributions``, with its own token).
  The Campaign is closed either way: nothing here can reopen it;
- **the token** is the one the deploy holds for the Project (``projects.review_request_tokens``),
  or the one a retry carries. With neither, the attempt is refused as ``no review-request token``
  and recorded, and the supervisor's retry opens it (§24ci (b): nothing is stored for it by
  default).

A Campaign closed before this rule carries no ``contribution`` on its closing row, and is never
contributed by it: its work was contributed by hand, or is the owner's to contribute.
"""

from __future__ import annotations

import logging
import uuid
from collections.abc import Iterable, Mapping
from typing import Any

from squadops.campaigns.campaign_branch import branch_base, head
from squadops.campaigns.models import (
    Campaign,
    CampaignState,
    CampaignTransition,
    ControlLogEntry,
    ControlOperation,
    ControlOutcome,
    CycleKind,
    LaunchIntent,
)
from squadops.campaigns.review_push import (
    OPENED_AT_CLOSE,
    campaign_push_lock,
    review_body,
    review_title,
)

logger = logging.getLogger(__name__)

#: The closing row's key for what its contribution is (§24dc).
CONTRIBUTION_KEY = "contribution"
#: The kinds whose acceptance is an increment's: the increment itself, or its repair or retry.
INCREMENT_FAMILY = frozenset({CycleKind.INCREMENT, CycleKind.REPAIR, CycleKind.RETRY})
#: Why a closing row records nothing due.
NO_ACCEPTED_INCREMENT = "no accepted increment: the Campaign opens no contribution"
#: The actor of the attempts the deploy makes: at the close, and at startup.
DEPLOY_ACTOR, DEPLOY_ROLE = "squadops", "completion"


def accepted_on_branch(
    log: Iterable[ControlLogEntry], intents: Iterable[LaunchIntent]
) -> tuple[tuple[str, str | None], ...]:
    """Each accepted increment on the Campaign's branch, in promotion order: its cycle, and the
    commit that holds it now. A rebase (§24bv point 4) replays each commit as a new one, so the
    commit is followed through every rebase since; ``None`` when a rebase dropped it, because the
    commit it rebased onto already held its change (the owner's merge, §24cd point 4). A sample
    application's increments name no commit, and aren't listed."""
    kinds = {i.cycle_id: i.cycle_kind for i in intents if i.cycle_id}
    current: dict[str, str | None] = {}
    for e in log:
        if e.outcome is not ControlOutcome.APPLIED:
            continue
        b = e.binding
        if (
            e.operation is ControlOperation.PROMOTE
            and b.get("commit")
            and kinds.get(b.get("cycle_id")) in INCREMENT_FAMILY
        ):
            current.setdefault(b["cycle_id"], b["commit"])
        elif e.operation is ControlOperation.BRANCH_REBASED:
            replayed = {old: new for old, new in b.get("replayed") or ()}
            dropped = set(b.get("dropped") or ())
            for cycle_id, commit in current.items():
                if commit in dropped:
                    current[cycle_id] = None
                elif commit in replayed:
                    current[cycle_id] = replayed[commit]
    return tuple(current.items())


def closing_contribution(
    log: Iterable[ControlLogEntry], intents: Iterable[LaunchIntent], *, repository_backed: bool
) -> dict | None:
    """What the row that closes a Campaign records of its contribution (§24dc): ``None`` for a
    sample application's, which has no product to contribute to; otherwise due with the accepted
    increments' cycles, or not due and why."""
    if not repository_backed:
        return None
    accepted = [cycle_id for cycle_id, _commit in accepted_on_branch(log, intents)]
    if not accepted:
        return {"due": False, "reason": NO_ACCEPTED_INCREMENT}
    return {"due": True, "accepted": accepted}


def closing_row(log: Iterable[ControlLogEntry]) -> ControlLogEntry | None:
    """The applied row that completed the Campaign: its terminal decision, or the abort."""
    return next(
        (
            e
            for e in log
            if e.outcome is ControlOutcome.APPLIED
            and e.next_state is CampaignState.COMPLETED
            and e.prior_state is not CampaignState.COMPLETED
        ),
        None,
    )


def criterion_paths(log: Iterable[ControlLogEntry]) -> tuple[str, ...]:
    """Every criterion file the Campaign's promotions froze (§8.1), retired ones too: each is a
    test file the Campaign placed on its branch."""
    paths: list[str] = []
    for e in log:
        if e.operation is ControlOperation.PROMOTE and e.outcome is ControlOutcome.APPLIED:
            for criterion in e.binding.get("frozen_criteria") or ():
                path = criterion.get("test_path")
                if path and path not in paths:
                    paths.append(path)
    return tuple(paths)


class CampaignContribution:
    """Opens a closed Campaign's contribution, after its close commits (§24dc)."""

    def __init__(
        self,
        *,
        campaigns: Any,
        projects: Any,
        repository: Any,
        forge: Any,
        tokens: Mapping[str, str],
    ) -> None:
        self._campaigns = campaigns
        self._projects = projects
        self._repository = repository
        self._forge = forge
        self._tokens = tokens

    async def open(
        self,
        campaign_id: str,
        *,
        token: str | None = None,
        actor: str = DEPLOY_ACTOR,
        actor_role: str = DEPLOY_ROLE,
    ) -> tuple[Any, bool]:
        """Open the closed Campaign's contribution, once, with ``token`` or the deploy's own for
        its Project. Serialized with the Campaign's review pushes. Returns the contribution and
        whether it was recorded already.

        Raises:
            squadops.projects.contribution.ContributionRefused: The Campaign hasn't closed, closed
                before this rule, or has no accepted increment (nothing written); or the
                contribution path refused it (recorded as ``contribution_failed``).
            squadops.projects.models.SourceUnavailable: The clone or the product refused
                (recorded).
            squadops.ports.projects.review_request.ReviewRequestFailed: The forge refused
                (recorded).
        """
        async with campaign_push_lock(campaign_id):
            return await self._open(campaign_id, token, actor, actor_role)

    async def _open(
        self, campaign_id: str, token: str | None, actor: str, actor_role: str
    ) -> tuple[Any, bool]:
        # deferred (pair): squadops.projects imports this package at load
        from squadops.ports.projects.review_request import ReviewRequestFailed

        # deferred (pair): squadops.projects imports this package at load
        from squadops.projects.contribution import ContributionRefused, contribute_campaign

        # deferred (pair): squadops.projects imports this package at load
        from squadops.projects.models import SourceUnavailable

        campaign = await self._campaigns.get_campaign(campaign_id)
        log = await self._campaigns.control_log(campaign_id)
        self._refuse_unless_due(campaign, log)
        project = await self._projects.get_project(campaign.project_id)
        base = branch_base(log)
        assert base is not None  # an accepted increment is on a branch, which has a base
        try:
            return await contribute_campaign(
                project,
                campaign_id,
                head=head(campaign, log).commit,
                base=base.commit,
                criterion_paths=criterion_paths(log),
                title=review_title(campaign),
                body=review_body(campaign, log, OPENED_AT_CLOSE),
                registry=self._projects,
                repository=self._repository,
                forge=self._forge,
                token=token or self._tokens.get(campaign.project_id),
                actor=actor,
                idempotency_key=f"campaign-contribution:{campaign_id}",
            )
        except (ContributionRefused, SourceUnavailable, ReviewRequestFailed) as e:
            await self._failed(campaign_id, e, actor, actor_role)
            raise

    def _refuse_unless_due(self, campaign: Campaign, log: list[ControlLogEntry]) -> None:
        # deferred (pair): squadops.projects imports this package at load
        from squadops.projects.contribution import ContributionRefused

        closing = closing_row(log) if campaign.state is CampaignState.COMPLETED else None
        if closing is None:
            raise ContributionRefused(
                f"campaign {campaign.campaign_id} is {campaign.state.value}: its contribution is "
                "opened at its close (SIP-0109 §24dc)"
            )
        recorded = closing.binding.get(CONTRIBUTION_KEY)
        if recorded is None:
            raise ContributionRefused(
                f"campaign {campaign.campaign_id}'s close records no contribution: a sample "
                "application's, or one closed before SIP-0109 §24dc, is contributed by its owner"
            )
        if not recorded.get("due"):
            raise ContributionRefused(
                f"campaign {campaign.campaign_id} closed with {recorded.get('reason')}"
            )

    async def _failed(self, campaign_id: str, error: Exception, actor: str, role: str) -> None:
        """The attempt's failure, as a record on the closed Campaign: never lost, and never
        raised over the close. Its key is the attempt's own, so each attempt is one row."""
        reason = getattr(error, "reason", None)
        binding = {"error": type(error).__name__, "reason": reason, "message": str(error)[:1000]}
        try:
            await self._campaigns.transition(
                campaign_id,
                CampaignTransition(
                    operation=ControlOperation.CONTRIBUTION_FAILED,
                    actor=actor,
                    actor_role=role,
                    reason=f"the campaign's contribution was not opened: {str(error)[:300]}",
                    idempotency_key=f"contribution-failed:{uuid.uuid4().hex}",
                    next_state=None,
                    binding=binding,
                ),
            )
        except Exception:
            logger.exception(
                "campaign_contribution_failure_not_recorded", extra={"campaign_id": campaign_id}
            )
        logger.warning(
            "campaign_contribution_failed",
            extra={"campaign_id": campaign_id, "error": binding["error"], "reason": reason},
        )

    async def at_close(self, campaign_id: str) -> None:
        """After a Campaign's close commits: open its contribution when its close says it is due.
        Never raises: the Campaign is closed, and a failure is recorded for the next attempt."""
        try:
            log = await self._campaigns.control_log(campaign_id)
            closing = closing_row(log)
            if closing is None or not (closing.binding.get(CONTRIBUTION_KEY) or {}).get("due"):
                return
            await self.open(campaign_id)
        except Exception:
            logger.exception("campaign_contribution_not_opened", extra={"campaign_id": campaign_id})

    async def open_due(self) -> list[str]:
        """At startup: each completed Campaign whose close says its contribution is due and which
        none records yet is attempted again. Returns the Campaigns contributed."""
        opened = []
        recorded: dict[str, set[str]] = {}
        for campaign in await self._campaigns.campaigns_in_state(CampaignState.COMPLETED):
            try:
                closing = closing_row(await self._campaigns.control_log(campaign.campaign_id))
                if closing is None or not (closing.binding.get(CONTRIBUTION_KEY) or {}).get("due"):
                    continue
                if campaign.project_id not in recorded:
                    recorded[campaign.project_id] = {
                        c.campaign_id
                        for c in await self._projects.contributions(campaign.project_id)
                        if c.campaign_id
                    }
                if campaign.campaign_id in recorded[campaign.project_id]:
                    continue
                await self.open(campaign.campaign_id)
            except Exception:
                logger.exception(
                    "campaign_contribution_not_opened", extra={"campaign_id": campaign.campaign_id}
                )
                continue
            opened.append(campaign.campaign_id)
        return opened
