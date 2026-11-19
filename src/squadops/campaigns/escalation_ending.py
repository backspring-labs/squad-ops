"""Ending a plan-gate escalation from the decision stored on its run (SIP-0109 §24eh; #3174).

A person's decision on an escalated plan gate ends the escalation. Until §24eh only the sweep
wrote that ending, every interval, and only for a campaign in a building state. A run that ended
soon after the decision took its campaign out of those states before the next sweep, and the
escalation read ``pending`` for good (``cmp_c22ad50e1de0``, 2026-11-17).

So the ending is written where the decision is recorded, and again wherever it is found missing:
- :func:`end_decided` is the one writer. It reads each pending plan-gate escalation of a campaign
  against the decision **stored on its run**, never against a decision in hand, so the route that
  records a decision and the sweep that finds one write the same row;
- every ending of one escalation shares a key (``escalation.closing_transitions``), so the same
  decision posted twice, or the route and the sweep meeting, writes one row.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from datetime import datetime
from typing import TYPE_CHECKING

from squadops.campaigns.escalation import (
    EscalationKind,
    EscalationState,
    RunAtGate,
    closing_transitions,
    escalations,
)
from squadops.campaigns.models import (
    Campaign,
    CampaignState,
    ControlLogEntry,
    ControlOperationRefused,
)
from squadops.cycles.gate_attribution import is_machine_decision
from squadops.cycles.models import GateDecision, Run

if TYPE_CHECKING:
    from squadops.ports.cycles.campaign_registry import CampaignRegistryPort
    from squadops.ports.cycles.cycle_registry import CycleRegistryPort

logger = logging.getLogger(__name__)


def person_decision(run: Run, gate_name: str) -> GateDecision | None:
    """The decision a person (or a declared agent) recorded on ``gate_name`` of ``run``; ``None``
    when nobody has, or only a machine path has."""
    return next(
        (
            d
            for d in run.gate_decisions
            if d.gate_name == gate_name and not is_machine_decision(d.decided_by)
        ),
        None,
    )


async def end_decided(
    campaigns: CampaignRegistryPort,
    cycles: CycleRegistryPort,
    campaign: Campaign,
    now: datetime,
    *,
    log: Sequence[ControlLogEntry] | None = None,
) -> list[ControlLogEntry]:
    """End each pending plan-gate escalation of ``campaign`` whose gate a person has decided, from
    the decision its run stores. Returns the rows written now: none for an escalation already
    ended, for a gate nobody decided, and for a completed campaign, whose own terminal row is its
    escalations' record (§24bk).

    It ends nothing else. An escalation nobody decided is the sweep's, in the states it reads
    (``CampaignProgress._end_escalations``)."""
    if campaign.state is CampaignState.COMPLETED:
        return []
    if log is None:
        log = await campaigns.control_log(campaign.campaign_id)
    runs = {}
    for esc in escalations(log, campaign.state):
        if esc.kind is not EscalationKind.PLAN_REVIEW or esc.state is not EscalationState.PENDING:
            continue
        decision = person_decision(await cycles.get_run(esc.run_id), esc.gate_name)
        if decision is not None:
            runs[esc.run_id] = RunAtGate(
                waiting=False, decided_by=decision.decided_by, decided_at=decision.decided_at
            )
    written = []
    for transition in closing_transitions(campaign, log, runs, now):
        try:
            result = await campaigns.transition(campaign.campaign_id, transition)
        except ControlOperationRefused as refused:
            # Another writer ended it between the read and the write: it ends once.
            logger.info(
                "campaign_escalation_close_refused",
                extra={"campaign_id": campaign.campaign_id, "refusal": refused.entry.refusal},
            )
            continue
        if not result.replayed:
            written.append(result.entry)
    return written
