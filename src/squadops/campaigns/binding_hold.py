"""A Campaign cycle held on its instruction bindings, escalated as its own kind (SIP-0109 §24bw;
SIP-0110 §A.3.6, #2178).

SIP-0110's hold, the executor's, holds a run whose task instructions can't be bound and records it
on the run (``Run.binding_holds``). A Campaign's cycle needs the owner to see it, and an end. This
decides both:

- the ``escalation_opened`` row the hold's opening writes, keyed by the hold, so a restart that
  re-enters the hold replays it;
- each pending one's ending, read against its run's hold record: ``resolved`` with the release's
  cause, ``superseded`` when the run stopped being held with no re-supply (a cancel), or
  ``expired`` when the ruling bound passed with it still held.

An expiry ends the cycle by the hold's cause class, never as a park (``continuation``). ``store``
reads as an infrastructure ending (rows 10 and 11), and ``input`` escalates the campaign (row 17).
Neither counts toward ``max_unaccepted_increments``: a hold says nothing about the squad's work.
Pure, so the executor and the sweep write exactly what this decides, except ``open_binding_hold``,
the executor's one call on the Campaign side.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Any

from squadops.campaigns.escalation import (
    EscalationKind,
    EscalationState,
    LogRow,
    escalations,
    kind_of,
)
from squadops.campaigns.gate import EXECUTOR_ROLE, SWEEP_ROLE
from squadops.campaigns.models import (
    Campaign,
    CampaignState,
    CampaignTransition,
    ControlOperation,
    ControlOutcome,
)


class HoldClass(StrEnum):
    """Why a hold's records couldn't be bound, as its expiry reads it: the store didn't answer,
    or an operator's input can't be bound (a required reference at the cycle's commit, or an
    instruction withdrawn or narrowed to nothing)."""

    STORE = "store"
    INPUT = "input"


#: SIP-0110's release causes (#2178) that end a hold by re-supply.
RESUPPLIED = frozenset({"store_answered", "instruction_changed", "rebound"})
#: The release cause the executor records when the run is cancelled while held.
CANCELLED_CAUSE = "cancelled"
#: The release cause this sweep records when the ruling bound ends a hold.
EXPIRED_CAUSE = "expired"
#: The reason an expired hold's run is cancelled with, recorded on the run.
HOLD_EXPIRED_REASON = "binding_hold_expired"


def hold_class(unresolved: Sequence[Sequence[str]]) -> HoldClass:
    """A hold's cause class, from each unresolved record's ``(ref, reason, kind)``. ``store`` when
    any record couldn't be read because the store didn't answer, since nothing else can be judged
    then. Otherwise ``input``, as is a record whose kind wasn't given: the owner hears of it."""
    kinds = {entry[2] if len(entry) > 2 else HoldClass.INPUT for entry in unresolved}
    return HoldClass.STORE if HoldClass.STORE in kinds else HoldClass.INPUT


def escalation_id(campaign_id: str, run_id: str, hold_id: str) -> str:
    digest = hashlib.sha256(
        json.dumps([EscalationKind.BINDING_HOLD, campaign_id, run_id, hold_id]).encode("utf-8")
    ).hexdigest()
    return f"esc_{digest[:12]}"


def opening_transition(
    campaign_id: str, cycle_id: str, run_id: str, hold: Any, opened_at: datetime
) -> CampaignTransition:
    """The ``escalation_opened`` row a held Campaign cycle's hold writes (§24bw). ``hold`` is the
    run's ``BindingHold``. Keyed by the hold, so re-entering it after a restart replays the row,
    and its bound runs from the first opening."""
    unresolved = [
        {
            "ref": entry[0],
            "reason": entry[1],
            "kind": str(entry[2]) if len(entry) > 2 else str(HoldClass.INPUT),
        }
        for entry in hold.unresolved
    ]
    cls = hold_class(hold.unresolved)
    esc_id = escalation_id(campaign_id, run_id, hold.hold_id)
    return CampaignTransition(
        operation=ControlOperation.ESCALATION_OPENED,
        actor="squadops",
        actor_role=EXECUTOR_ROLE,
        reason=f"{hold.task_id} is held: its instructions could not be bound ({cls}): "
        + "; ".join(f"{u['ref']}: {u['reason']}" for u in unresolved),
        idempotency_key=f"escalation:{esc_id}",
        next_state=None,
        target=run_id,
        binding={
            "escalation_id": esc_id,
            "kind": str(EscalationKind.BINDING_HOLD),
            "identity": {
                "campaign_id": campaign_id,
                "cycle_id": cycle_id,
                "run_id": run_id,
                "hold_id": hold.hold_id,
                "task_id": hold.task_id,
                "task_type": hold.task_type,
            },
            "hold_id": hold.hold_id,
            "hold_class": str(cls),
            "unresolved": unresolved,
            "opened_at": opened_at.isoformat(),
        },
    )


@dataclass(frozen=True)
class HoldAtRun:
    """What the sweep read of a binding hold's run: whether the run is still held on it, and the
    cause the hold was released with, if it was."""

    held: bool
    released_cause: str | None


def _closing(esc_id: str, run_id: str, state: EscalationState, reason: str, **extra: Any):
    return CampaignTransition(
        operation=ControlOperation.ESCALATION_CLOSED,
        actor="squadops",
        actor_role=SWEEP_ROLE,
        reason=reason,
        # One key for every ending, as a plan gate's: a hold's escalation ends exactly once.
        idempotency_key=f"escalation_closed:{esc_id}",
        next_state=None,
        target=run_id,
        binding={"escalation_id": esc_id, "state": str(state), **extra},
    )


def closing_transitions(
    campaign: Campaign,
    log: Sequence[LogRow],
    holds: Mapping[str, HoldAtRun],
    now: datetime,
) -> list[CampaignTransition]:
    """Each pending binding hold's ending at ``now``, read against its run (``holds``, by hold id):

    - released by re-supply: ``resolved``, with the release's cause;
    - no longer held with no re-supply (the run was cancelled, or ended otherwise): ``superseded``;
    - still held, with the campaign's ruling bound passed since it opened: ``expired``, with its
      cause class. The sweep then cancels the run and records the release.

    A hold the sweep couldn't read is left pending."""
    if campaign.state is CampaignState.COMPLETED:
        return []
    bound = campaign.policy.ruling_bound_s
    out = []
    for esc in escalations(log, campaign.state):
        if esc.kind is not EscalationKind.BINDING_HOLD or esc.state is not EscalationState.PENDING:
            continue
        reading = holds.get(esc.hold_id or "")
        if reading is None:
            continue
        if reading.released_cause in RESUPPLIED:
            out.append(
                _closing(
                    esc.escalation_id,
                    esc.run_id,
                    EscalationState.RESOLVED,
                    f"{esc.run_id}'s hold was released: {reading.released_cause}",
                    cause=reading.released_cause,
                )
            )
        elif not reading.held:
            out.append(
                _closing(
                    esc.escalation_id,
                    esc.run_id,
                    EscalationState.SUPERSEDED,
                    f"{esc.run_id} is no longer held, and nothing re-supplied it "
                    f"({reading.released_cause or 'no release recorded'})",
                    cause=reading.released_cause,
                )
            )
        elif (now - esc.opened_at).total_seconds() >= bound:
            out.append(
                _closing(
                    esc.escalation_id,
                    esc.run_id,
                    EscalationState.EXPIRED,
                    f"the hold opened at {esc.opened_at.isoformat()} and the ruling bound of "
                    f"{bound}s passed with its instructions still unbound ({esc.hold_class}): its "
                    "run is cancelled, and the cycle ends by that cause, never parked",
                    cause=EXPIRED_CAUSE,
                    hold_class=esc.hold_class,
                )
            )
    return out


def held_expiry(log: Sequence[LogRow], run_id: str) -> HoldClass | None:
    """The cause class of a binding hold that expired on ``run_id``, or ``None``: the cycle then
    ends ``held_store`` or ``held_input`` (``continuation``), never parked."""
    applied = [e for e in log if e.outcome is ControlOutcome.APPLIED]
    expired = {
        e.binding["escalation_id"]
        for e in applied
        if e.operation is ControlOperation.ESCALATION_CLOSED
        and e.binding.get("state") == EscalationState.EXPIRED
    }
    for e in applied:
        b = e.binding
        if (
            e.operation is ControlOperation.ESCALATION_OPENED
            and kind_of(b) is EscalationKind.BINDING_HOLD
            and b["escalation_id"] in expired
            and b["identity"]["run_id"] == run_id
        ):
            return HoldClass(b["hold_class"])
    return None


async def open_binding_hold(
    campaigns: Any, cycle: Any, run_id: str, hold: Any, now: datetime
) -> bool:
    """The executor's one call on the Campaign side (§24bw), after it records ``hold`` on the run:
    a Campaign cycle's hold opens its escalation, so the owner sees it and the sweep ends it. A
    standalone cycle holds with no escalation (SIP-0110 §A.3.6). A restart that re-enters the
    hold finds the escalation standing and writes nothing, so its bound runs from the first
    opening. Returns whether an escalation stands for it. A refusal raises, for the caller to
    log: the run stays held either way."""
    if cycle.campaign_id is None:
        return False
    campaign = await campaigns.get_campaign(cycle.campaign_id)
    log = await campaigns.control_log(cycle.campaign_id)
    esc_id = escalation_id(cycle.campaign_id, run_id, hold.hold_id)
    if any(e.escalation_id == esc_id for e in escalations(log, campaign.state)):
        return True
    await campaigns.transition(
        cycle.campaign_id, opening_transition(cycle.campaign_id, cycle.cycle_id, run_id, hold, now)
    )
    return True
