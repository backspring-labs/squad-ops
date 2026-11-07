"""The owner's grant of a Campaign's goal-set curation to the operator (SIP-0115 Q41, §10c; SIP-0109
§24dd; #2886).

The operator may promote a candidate, drop one or split a backlog item only within a Campaign the
owner has granted it. The operator can create a Campaign itself (``campaigns:manage``), so who created
one says nothing about the owner: the grant is a row the owner writes.

- It is an **applied ``goal_delegation_granted`` row of the Campaign's own control log.** Nothing
  else stands in for one: not a binding on another row, not a field of a definition the operator
  submitted, not a refused attempt.
- It moves no state, and a completed Campaign refuses it.
- It lasts the Campaign's life. There is no revocation: the owner aborts the Campaign, or writes
  the goal set.

Pure: the route writes the transition, and ``goal_set_actions`` reads the log.
"""

from __future__ import annotations

from collections.abc import Iterable

from squadops.campaigns.models import (
    Campaign,
    CampaignState,
    CampaignTransition,
    ControlLogEntry,
    ControlOperation,
    ControlOutcome,
)

#: The binding's key for where the owner's decision came from (SIP-0115 §6): a link, when it came
#: from a conversation.
SOURCE_REF_KEY = "source_ref"


def goal_delegation_transition(
    campaign: Campaign,
    *,
    actor: str,
    actor_role: str,
    reason: str,
    idempotency_key: str,
    source_ref: str | None = None,
    expected_state: CampaignState | None = None,
) -> CampaignTransition:
    """The grant's row, on a Campaign that names a goal set. Who may write it is the route's:
    ``campaigns:control``, the owner's alone.

    Raises ``ValueError`` when the Campaign names no goal set, or a required field is blank."""
    goals = campaign.objective.goals
    if goals is None:
        raise ValueError(f"campaign {campaign.campaign_id} names no goal set (objective.goals)")
    return CampaignTransition(
        operation=ControlOperation.GOAL_DELEGATION_GRANTED,
        actor=actor,
        actor_role=actor_role,
        reason=reason,
        idempotency_key=idempotency_key,
        next_state=None,
        target=goals.goal_set,
        binding={
            "goal_set": goals.goal_set,
            **({SOURCE_REF_KEY: source_ref} if source_ref is not None else {}),
        },
        expected_state=expected_state,
    )


def goal_delegation(log: Iterable[ControlLogEntry]) -> ControlLogEntry | None:
    """The first applied grant in the Campaign's control log, or ``None``."""
    return next(
        (
            e
            for e in log
            if e.operation is ControlOperation.GOAL_DELEGATION_GRANTED
            and e.outcome is ControlOutcome.APPLIED
        ),
        None,
    )
