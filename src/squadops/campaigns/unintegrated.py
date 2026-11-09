"""Accepted Campaign work not yet in its Project's integrated commit (SIP-0109 §24dc, #2863).

A Campaign drafted on a product reads it at the Project's integrated commit (#2855). An increment a
Campaign accepted that the commit doesn't carry yet is work the draft can't see, so the supervisor
gates on this set: a draft waits while it is non-empty. Each accepted increment on a Campaign's
branch (``close_contribution.accepted_on_branch``) is listed unless the integrated commit carries
it, and stands as one of:
- ``not_contributed``: no contribution of it is recorded, by its Campaign or its own run. A running
  Campaign's increments stand here too;
- ``contribution_pending``: one is recorded, pending. A merge on the forge is read only by a sync
  (``POST /api/v1/projects/{id}/syncs``), so a merged request reads pending until one runs. The
  draft's integration check runs one where it is needed (``squadops.projects.integration_check``,
  SIP-0112 H.30);
- ``merged_not_synced``: a sync recorded one integrated, and the Project's integrated commit
  doesn't carry it yet: the Project is re-validated at the new commit (E.4.4) to move it;
- ``contribution_closed``: its review request was closed unmerged, and ``review_url`` names it. The
  work still isn't in, so it keeps blocking. Recovery is the owner's: on the forge, reopen the
  request and merge it with a merge commit, then sync and re-validate; or declare the work won't
  land, ``squadops campaigns dismiss-contribution`` (§24dg), which clears the row. An increment a
  live record still carries stands by that record, and stays listed.
  ``squadops campaigns contribute`` can't do this: it answers the closed record (SIP-0109 §24dc).

"Carries" is read in the managed clone: the increment's commit, or the merge commit a sync
recorded (a squash merge makes a new one), is in the integrated commit's history. An increment a
rebase dropped, because the commit it rebased onto already held its change, is carried. A history
the clone can't read is read as not carried, so the set over-reports rather than hides (logged).
"""

from __future__ import annotations

import logging
from collections.abc import Iterable
from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING, Any

from squadops.campaigns.backlog import ItemStatus, campaign_backlog
from squadops.campaigns.close_contribution import accepted_on_branch
from squadops.campaigns.contribution_dismissal import contribution_dismissal
from squadops.campaigns.ledger import ledger
from squadops.campaigns.models import Campaign
from squadops.cycles.models import GoalSetNotFoundError

if TYPE_CHECKING:
    from squadops.ports.cycles.campaign_registry import CampaignRegistryPort
    from squadops.ports.projects.goal_sets import GoalSetRegistryPort

logger = logging.getLogger(__name__)

#: Which of an increment's contributions says where it stands: the furthest along.
_ORDER = {"integrated": 0, "pending": 1, "closed": 2}


class Standing(StrEnum):
    NOT_CONTRIBUTED = "not_contributed"
    CONTRIBUTION_PENDING = "contribution_pending"
    MERGED_NOT_SYNCED = "merged_not_synced"
    CONTRIBUTION_CLOSED = "contribution_closed"


@dataclass(frozen=True)
class UnintegratedIncrement:
    campaign_id: str
    campaign_state: str
    cycle_id: str
    #: The backlog item's title, for an increment that served one (SIP-0115); ``None`` otherwise.
    title: str | None
    #: The commit that holds the increment on its Campaign's branch now.
    commit: str
    standing: Standing
    #: Its Campaign's review request, when its contribution opened one.
    review_url: str | None


async def unintegrated_increments(
    project: Any,
    *,
    campaigns: CampaignRegistryPort,
    contributions: Iterable[Any],
    repository: Any,
    goal_sets: GoalSetRegistryPort,
) -> list[UnintegratedIncrement]:
    """``project``'s accepted Campaign increments its integrated commit doesn't carry, Campaign by
    Campaign, oldest first, each in promotion order. ``contributions`` are the Project's."""
    # deferred (pair): squadops.projects imports this package at load
    from squadops.projects.contribution import CLOSED, INTEGRATED

    by_campaign: dict[str, Any] = {}
    by_cycle: dict[str, list[Any]] = {}
    for c in contributions:
        if c.campaign_id:
            by_campaign[c.campaign_id] = c
        else:
            by_cycle.setdefault(c.cycle_id, []).append(c)
    listed = sorted(await campaigns.list_campaigns(project.project_id), key=lambda c: c.created_at)
    out = []
    for campaign in listed:
        log = await campaigns.control_log(campaign.campaign_id)
        intents = await campaigns.launch_intents(campaign.campaign_id)
        accepted = accepted_on_branch(log, intents)
        if not accepted:
            continue
        whole = by_campaign.get(campaign.campaign_id)
        dismissed = contribution_dismissal(log) is not None
        titles = await _titles(campaign, log, intents, campaigns, goal_sets)
        for cycle_id, commit in accepted:
            if commit is None or await _carried(project, commit, repository):
                continue
            # Its own run's records, and its Campaign's: the furthest along says where it stands.
            held = [*by_cycle.get(cycle_id, ()), *([whole] if whole is not None else ())]
            merges = [c.integrated_commit for c in held if c.integrated_commit]
            if any([await _carried(project, m, repository) for m in merges]):
                continue
            contribution = min(held, key=lambda c: _ORDER[c.state], default=None)
            if contribution is None:
                standing = Standing.NOT_CONTRIBUTED
            elif contribution.state == CLOSED:
                if dismissed:
                    continue
                standing = Standing.CONTRIBUTION_CLOSED
            elif contribution.state == INTEGRATED:
                standing = Standing.MERGED_NOT_SYNCED
            else:
                standing = Standing.CONTRIBUTION_PENDING
            out.append(
                UnintegratedIncrement(
                    campaign_id=campaign.campaign_id,
                    campaign_state=campaign.state.value,
                    cycle_id=cycle_id,
                    title=titles.get(cycle_id),
                    commit=commit,
                    standing=standing,
                    review_url=contribution.review_url if contribution is not None else None,
                )
            )
    return out


async def _carried(project: Any, commit: str, repository: Any) -> bool:
    """Whether the Project's integrated commit carries ``commit``. ``False`` with no integrated
    commit, or a history the clone can't read (logged): over-reported, never hidden."""
    # deferred (pair): squadops.projects imports this package at load
    from squadops.projects.models import SourceUnavailable

    integrated = project.integrated_upstream_commit
    if integrated is None:
        return False
    try:
        return bool(await repository.is_ancestor(project.project_id, commit, integrated))
    except SourceUnavailable:
        logger.warning(
            "unintegrated_ancestry_unread",
            extra={"project_id": project.project_id, "commit": commit},
            exc_info=True,
        )
        return False


async def _titles(
    campaign: Campaign,
    log: list,
    intents: list,
    campaigns: CampaignRegistryPort,
    goal_sets: GoalSetRegistryPort,
) -> dict[str, str]:
    """Each accepted cycle's backlog item title, for a goal-set Campaign: the cycle's proposal
    (its own, or the one its repair or retry continues, by the ledger), and the item that proposal
    was accepted for. Empty for a requirements Campaign, or a goal set that can't be read."""
    if campaign.objective.goals is None:
        return {}
    try:
        view, _revisions = await campaign_backlog(
            campaign, goal_sets=goal_sets, campaigns=campaigns
        )
    except (GoalSetNotFoundError, ValueError):
        logger.warning("unintegrated_titles_unread", extra={"campaign_id": campaign.campaign_id})
        return {}
    by_proposal = {
        i.proposal_id: i.title
        for i in view.items
        if i.status is ItemStatus.ACCEPTED and i.proposal_id
    }
    titles = {}
    for entry in ledger(log, intents):
        title = by_proposal.get(entry.proposal_id)
        if title is None:
            continue
        for cycle in entry.cycles or ({"cycle_id": entry.cycle_id},):
            titles[cycle["cycle_id"]] = title
    return titles
