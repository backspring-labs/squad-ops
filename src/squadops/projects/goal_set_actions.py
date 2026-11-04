"""Slice 3's actions on a Project's goal set, recorded as revisions (SIP-0115 §5.4, §5.5a, §6,
Q41; #2886): a candidate added, promoted or dropped, and a backlog item split.

Each reads the revision the action is against, applies the goal set's own action
(``goal_set.add_candidate`` and its siblings), and records the result as the next revision with
the acting principal as its author, the reason given, and the action named on it (``Change``).
A retry under its key replays what was written: the action is recomputed against the same base
revision, and the store answers the first write.

**Who may** (§6, Q41, ruled 2026-11-03). The owner, holding ``admin:write``, may do each. The
crew's supervisor seat may add a candidate; and may promote, drop or split **only within a
Campaign:** the request names the Campaign, which is on this Project, names this goal set, and is
live (not ``completed``, the lifecycle's one terminal state). Q41's "a Campaign the owner
started" is read so (§10c, the supervisor's narrowing for the owner's review): the crew's broker
creates the Campaigns the owner approves in Buzz, and SquadOps records no approval to read, so
the delegation lasts the Campaign's life. A promotion by the crew is appended at the end of the
backlog: a position anywhere else is a reorder, which stays the owner's (Q41). The Campaign a
delegated act was within is recorded on the revision.

**A split waits** (§5.5a) while any live Campaign on the Project reads the item ``proposed`` or
``in_increment``, read with slice 2's derived view per Campaign; a completed Campaign doesn't
count.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from squadops.campaigns.backlog import ItemStatus, campaign_backlog
from squadops.campaigns.models import Campaign, CampaignState
from squadops.projects.development_configuration import submission_digest
from squadops.projects.goal_set import (
    Change,
    ChangeKind,
    GoalSet,
    GoalSetInvalid,
    GoalSetRevision,
    add_candidate,
    drop_candidate,
    promote_candidate,
    split_item,
)

if TYPE_CHECKING:
    from squadops.ports.cycles.campaign_registry import CampaignRegistryPort
    from squadops.ports.cycles.project_registry import ProjectRegistryPort
    from squadops.ports.projects.goal_sets import GoalSetRegistryPort


class NotDelegated(PermissionError):
    """The crew acted outside what Q41 delegates: not within a live Campaign on this Project
    reading this goal set (none named, another Project's, a requirements Campaign, or one that
    has completed), or a promotion anywhere but the end of the backlog."""


class BacklogItemInProgress(RuntimeError):
    """A split of an item a live Campaign reads ``proposed`` or ``in_increment`` (§5.5a)."""


@dataclass(frozen=True)
class Actor:
    """Who acts: the principal, and whether it holds the owner's write scope."""

    principal: str
    owner: bool


@dataclass(frozen=True)
class ActionWrite:
    """What every action's revision carries beside its content (§6): who, against which
    revision, why, from where, under which key, and the Campaign it was within, when it was."""

    actor: Actor
    expected_revision: int
    reason: str
    idempotency_key: str
    source_ref: str | None = None
    campaign_id: str | None = None
    now: datetime | None = None


def not_within(campaign: Campaign, *, project_id: str) -> str | None:
    """Why ``campaign`` is not one an action may be within on ``project_id``'s goal set (Q41,
    §10c), or ``None``: it is on this Project, names a goal set, and is live. The same for the
    owner and the crew: the owner needs no Campaign, and one named is checked so the record on
    the revision is true. ``completed`` is the lifecycle's one terminal state (no legal move
    leaves it); how it ended is its ``outcome``."""
    if campaign.project_id != project_id:
        return (
            f"campaign {campaign.campaign_id} is on Project {campaign.project_id}, not {project_id}"
        )
    if campaign.objective.goals is None:
        return f"campaign {campaign.campaign_id} names no goal set (objective.goals)"
    if campaign.state is CampaignState.COMPLETED:
        ended = campaign.outcome.value if campaign.outcome is not None else "completed"
        return (
            f"campaign {campaign.campaign_id} has completed ({ended}): the delegation lasted its "
            "life (SIP-0115 Q41, §10c)"
        )
    return None


async def record_candidate(
    project_id: str,
    candidate: Mapping[str, Any],
    write: ActionWrite,
    *,
    projects: ProjectRegistryPort,
    goal_sets: GoalSetRegistryPort,
) -> tuple[GoalSetRevision, bool]:
    """Add ``candidate`` to the goal set as its next revision (§5.4).

    Raises:
        ProjectNotFoundError, GoalSetNotFoundError: no such Project, or no goal set written yet.
        GoalSetInvalid: the candidate, naming its field.
        StaleGoalSetRevisionError, RegistrationKeyConflictError: the store's refusals.
    """
    base = await _base(project_id, write, projects=projects, goal_sets=goal_sets)
    when = write.now or datetime.now(UTC)
    goal_set = add_candidate(base.goal_set, candidate, found_at=when)
    added = goal_set.candidates[-1]
    change = Change(ChangeKind.CANDIDATE_ADDED, added.id, campaign_id=write.campaign_id)
    return await _record(
        base, goal_set, change, write, goal_sets=goal_sets, inputs={"candidate": dict(candidate)}
    )


async def record_promotion(
    project_id: str,
    candidate_id: str,
    *,
    serves: Sequence[str],
    position: int | None,
    write: ActionWrite,
    projects: ProjectRegistryPort,
    goal_sets: GoalSetRegistryPort,
    campaigns: CampaignRegistryPort,
) -> tuple[GoalSetRevision, bool]:
    """Promote the candidate into the backlog at ``position`` (the end when ``None``), keeping
    its id, as the next revision (§5.4, §10a).

    Raises:
        NotDelegated: the crew outside a Campaign the owner started, or not at the end.
        CandidateNotFound: the revision holds no such candidate.
        CampaignNotFoundError: the Campaign named doesn't exist.
        GoalSetInvalid: ``serves`` or ``position``, naming it.
        ProjectNotFoundError, GoalSetNotFoundError, StaleGoalSetRevisionError,
        RegistrationKeyConflictError: as ``record_candidate``.
    """
    base = await _base(project_id, write, projects=projects, goal_sets=goal_sets)
    await _within(project_id, write, campaigns, what="promote a candidate")
    end = len(base.goal_set.backlog) + 1
    if not write.actor.owner and position is not None and position != end:
        raise NotDelegated(
            f"{write.actor.principal} appends a promoted candidate at the end of the backlog "
            f"(position {end}); position {position} is a reorder, the owner's (SIP-0115 Q41)"
        )
    goal_set, at = promote_candidate(base.goal_set, candidate_id, serves=serves, position=position)
    change = Change(
        ChangeKind.CANDIDATE_PROMOTED, candidate_id, position=at, campaign_id=write.campaign_id
    )
    inputs = {"candidate_id": candidate_id, "serves": list(serves), "position": position}
    return await _record(base, goal_set, change, write, goal_sets=goal_sets, inputs=inputs)


async def record_drop(
    project_id: str,
    candidate_id: str,
    *,
    write: ActionWrite,
    projects: ProjectRegistryPort,
    goal_sets: GoalSetRegistryPort,
    campaigns: CampaignRegistryPort,
) -> tuple[GoalSetRevision, bool]:
    """Drop the candidate, with the reason, as the next revision (§5.4). Who may is as for a
    promotion.

    Raises: as ``record_promotion``, less ``GoalSetInvalid``.
    """
    base = await _base(project_id, write, projects=projects, goal_sets=goal_sets)
    await _within(project_id, write, campaigns, what="drop a candidate")
    goal_set = drop_candidate(base.goal_set, candidate_id)
    change = Change(ChangeKind.CANDIDATE_DROPPED, candidate_id, campaign_id=write.campaign_id)
    inputs = {"candidate_id": candidate_id}
    return await _record(base, goal_set, change, write, goal_sets=goal_sets, inputs=inputs)


async def record_split(
    project_id: str,
    item_id: str,
    into: Sequence[Mapping[str, Any]],
    *,
    write: ActionWrite,
    projects: ProjectRegistryPort,
    goal_sets: GoalSetRegistryPort,
    campaigns: CampaignRegistryPort,
) -> tuple[GoalSetRevision, bool]:
    """Split the backlog item into the parts of ``into``, which take its place (§5.5a), as the
    next revision naming them (``change.split_into``). Who may is as for a promotion.

    Raises:
        BacklogItemInProgress: a live Campaign reads the item ``proposed`` or ``in_increment``.
        BacklogItemNotFound: the revision holds no such item.
        GoalSetInvalid: the parts, naming the field.
        NotDelegated, CampaignNotFoundError, ProjectNotFoundError, GoalSetNotFoundError,
        StaleGoalSetRevisionError, RegistrationKeyConflictError: as ``record_promotion``.
    """
    base = await _base(project_id, write, projects=projects, goal_sets=goal_sets)
    await _within(project_id, write, campaigns, what="split a backlog item")
    goal_set = split_item(base.goal_set, item_id, into)
    await _not_in_progress(project_id, item_id, goal_sets=goal_sets, campaigns=campaigns)
    parts = tuple(str(part["id"]) for part in into)
    change = Change(ChangeKind.ITEM_SPLIT, item_id, split_into=parts, campaign_id=write.campaign_id)
    inputs = {"item_id": item_id, "into": [dict(part) for part in into]}
    return await _record(base, goal_set, change, write, goal_sets=goal_sets, inputs=inputs)


# --- the steps the actions share ---


async def _base(
    project_id: str,
    write: ActionWrite,
    *,
    projects: ProjectRegistryPort,
    goal_sets: GoalSetRegistryPort,
) -> GoalSetRevision:
    """The revision the action is against: ``expected_revision`` itself, not the latest, so a
    retry recomputes the same result and the store replays it; a later writer is refused at the
    write (``StaleGoalSetRevisionError``)."""
    # deferred (pair): squadops.cycles imports this package at load
    from squadops.cycles.models import GoalSetNotFoundError

    await projects.get_project(project_id)
    if not write.reason.strip():
        raise GoalSetInvalid("reason", "required: why this revision is written")
    if write.expected_revision < 1:
        raise GoalSetNotFoundError(
            f"Project {project_id} has no goal set revision {write.expected_revision}: an action "
            "is on a written goal set; write its first revision with the goal and expected results"
        )
    return await goal_sets.get_revision(project_id, write.expected_revision)


async def _within(
    project_id: str, write: ActionWrite, campaigns: CampaignRegistryPort, *, what: str
) -> Campaign | None:
    """The Campaign the action is within, checked (Q41): required of the crew, optional of the
    owner, and when named it is a live Campaign on this Project reading a goal set, so the record
    on the revision is true."""
    if write.campaign_id is None:
        if write.actor.owner:
            return None
        raise NotDelegated(
            f"{write.actor.principal} may {what} only within a live Campaign on this Project: "
            "name campaign_id (SIP-0115 Q41)"
        )
    campaign = await campaigns.get_campaign(write.campaign_id)
    refusal = not_within(campaign, project_id=project_id)
    if refusal is not None:
        raise NotDelegated(refusal)
    return campaign


async def _not_in_progress(
    project_id: str,
    item_id: str,
    *,
    goal_sets: GoalSetRegistryPort,
    campaigns: CampaignRegistryPort,
) -> None:
    """§5.5a: no live Campaign on the Project reads the item ``proposed`` or ``in_increment``."""
    for campaign in await campaigns.list_campaigns(project_id):
        if campaign.state is CampaignState.COMPLETED or campaign.objective.goals is None:
            continue
        view, _revisions = await campaign_backlog(
            campaign, goal_sets=goal_sets, campaigns=campaigns
        )
        found = next((i for i in view.items if i.item_id == item_id), None)
        if found is not None and found.status in (ItemStatus.PROPOSED, ItemStatus.IN_INCREMENT):
            raise BacklogItemInProgress(
                f"{item_id} is {found.status.value} in campaign {campaign.campaign_id}: a split "
                "waits until that increment ends (SIP-0115 §5.5a)"
            )


async def _record(
    base: GoalSetRevision,
    goal_set: GoalSet,
    change: Change,
    write: ActionWrite,
    *,
    goal_sets: GoalSetRegistryPort,
    inputs: Mapping[str, Any],
) -> tuple[GoalSetRevision, bool]:
    """Record ``goal_set`` as the revision after ``base``, under the key, hashed over the action
    as it was asked (its inputs against ``base``), so a retry with the same request replays."""
    revision = GoalSetRevision(
        project_id=base.project_id,
        revision=base.revision + 1,
        goal_set=goal_set,
        author=write.actor.principal,
        reason=write.reason,
        created_at=write.now or datetime.now(UTC),
        source_ref=write.source_ref,
        change=change,
    )
    return await goal_sets.record_revision(
        revision,
        idempotency_key=write.idempotency_key,
        request_hash=submission_digest(
            {
                "project_id": base.project_id,
                "expected_revision": write.expected_revision,
                "reason": write.reason,
                "source_ref": write.source_ref,
                "campaign_id": write.campaign_id,
                "action": change.kind.value,
                "inputs": dict(inputs),
            }
        ),
    )
