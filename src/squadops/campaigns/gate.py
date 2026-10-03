"""The increment gate (SIP-0109 §9.2; #1801): the proposal submitted to it, and the ruling on it.

The gate follows a campaign increment cycle's ``proposal`` workload. When it opens, the proposal
the run produced is **submitted**: a control-log row that pins it as the campaign's proposal and
moves the campaign to ``awaiting_ruling``. The supervisor's ruling is recorded through the
existing gate decision path (``squadops runs gate``) as a ``rule`` row first, checked in that
row's transaction against the submitted proposal and the accepted tree, so an old approval
cannot authorize changed scope; the gate decision on the run follows the row.

The gate is never passed through by the absence of design questions (#807): an increment cycle
carries its baseline's manifest, which asks nothing, and only the ruling moves this gate.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Any

import yaml

from squadops.campaigns.models import (
    RULING_MOVES,
    Campaign,
    CampaignState,
    CampaignTransition,
    ControlLogEntry,
    ControlOperation,
    ControlOutcome,
    IncrementRuling,
    ProposalBinding,
    SubmittedProposal,
)
from squadops.cycles.models import GateDecisionValue, RunStatus, WorkloadType

#: The gate's name, as a campaign increment profile declares it after the proposal workload. A
#: progression gate by SIP-0076's naming canon: the ruling decides whether framing begins (§24k).
INCREMENT_RULING_GATE = "progress_increment_ruling"

#: The provenance of the candidate manifest an approved increment seeds for its framing (§7.3).
INCREMENT_SEED_PRODUCER = "campaign.increment_seed"

#: The role on the rows the executor writes for the campaign.
EXECUTOR_ROLE = "executor"

#: The role on the rows the campaign sweep writes (§24ae).
SWEEP_ROLE = "sweep"


def increment_sequence_refusal(defaults: Mapping[str, Any]) -> str | None:
    """Why a request profile's ``defaults`` cannot run a campaign's increment cycles, or None
    (§7.3, #1705 step b).

    The sequence opens with the proposal workload, gated by the ruling, and a workload follows:
    the sequence ends on its last workload before that workload's gate (§24f), so a ruling gate
    there would never be reached. The gate is declared, since a decision on an undeclared gate is
    refused, and with no ``after_task_types``: a task boundary pauses the run mid-flight, waiting
    on a ruling for a proposal the campaign was never handed (§24k)."""
    sequence = defaults.get("workload_sequence") or []
    opening = sequence[0] if sequence and isinstance(sequence[0], Mapping) else {}
    if (opening.get("type"), opening.get("gate")) != (WorkloadType.PROPOSAL, INCREMENT_RULING_GATE):
        return (
            f"its workload_sequence must open with the {WorkloadType.PROPOSAL} workload, gated by "
            f"{INCREMENT_RULING_GATE}"
        )
    if len(sequence) < 2:
        return (
            f"a workload must follow {INCREMENT_RULING_GATE}: the sequence ends before its last "
            "workload's gate"
        )
    gates = (defaults.get("task_flow_policy") or {}).get("gates") or []
    declared = [g for g in gates if g.get("name") == INCREMENT_RULING_GATE]
    if not declared:
        return f"its task_flow_policy must declare the {INCREMENT_RULING_GATE} gate"
    if declared[0].get("after_task_types"):
        return (
            f"{INCREMENT_RULING_GATE} takes no after_task_types: a task boundary pauses the "
            "proposal run before its proposal is submitted"
        )
    return None


def binding_from_change_request(document: str) -> ProposalBinding:
    """The binding of a stored change request (``change_request.yaml``, the proposal run's
    artifact). Its identity fields are the framework's, written by the proposal's rails."""
    data = yaml.safe_load(document)
    if not isinstance(data, dict):
        raise ValueError("the change request is not a mapping")
    return ProposalBinding(
        proposal_id=str(data.get("proposal_id") or ""),
        version=int(data.get("version") or 0),
        content_hash=str(data.get("content_hash") or ""),
        baseline_tree=str(data.get("baseline_tree") or ""),
    )


def submission(state: CampaignState, proposal: SubmittedProposal) -> CampaignTransition:
    """The row that pins ``proposal`` at the gate. It moves an ``at_proposal`` campaign to
    ``awaiting_ruling``; a campaign holding (paused, escalated, launch-blocked) records the
    proposal in place, and its resume returns it to the gate. Keyed by the run, so the executor
    re-entering the gate after a restart replays the row."""
    return CampaignTransition(
        operation=ControlOperation.SUBMIT,
        actor="squadops",
        actor_role=EXECUTOR_ROLE,
        reason=(
            f"proposal {proposal.binding.proposal_id} v{proposal.binding.version} "
            f"at the increment gate"
        ),
        idempotency_key=f"submit:{proposal.run_id}",
        next_state=(CampaignState.AWAITING_RULING if state is CampaignState.AT_PROPOSAL else state),
        target=proposal.run_id,
        binding={
            "proposal_id": proposal.binding.proposal_id,
            "version": proposal.binding.version,
            "content_hash": proposal.binding.content_hash,
            "baseline_tree": proposal.binding.baseline_tree,
            "cycle_id": proposal.cycle_id,
        },
        submitted=proposal,
    )


def ruling_transition(
    decision: GateDecisionValue,
    binding: ProposalBinding,
    *,
    run_id: str,
    actor: str,
    actor_role: str,
    reason: str,
    idempotency_key: str,
) -> CampaignTransition:
    """The ``rule`` row. A decision the gate does not take still becomes a row, refused as
    ``illegal_ruling`` and recorded; it moves nothing."""
    return CampaignTransition(
        operation=ControlOperation.RULE,
        actor=actor,
        actor_role=actor_role,
        reason=reason,
        idempotency_key=idempotency_key,
        next_state=RULING_MOVES.get(decision, CampaignState.AWAITING_RULING),
        target=run_id,
        binding={
            "decision": decision.value,
            "proposal_id": binding.proposal_id,
            "version": binding.version,
            "content_hash": binding.content_hash,
            "baseline_tree": binding.baseline_tree,
        },
        ruling=IncrementRuling(decision, binding, run_id),
    )


def gate_opened_at(log: Sequence[ControlLogEntry]) -> datetime | None:
    """When the increment gate last opened: the latest applied row that moved the campaign into
    ``awaiting_ruling``. A submission opens it; so does a resume that returns a held proposal to
    the gate, which is when the supervisor could first rule on it."""
    opened = None
    for entry in log:
        if (
            entry.outcome is ControlOutcome.APPLIED
            and entry.next_state is CampaignState.AWAITING_RULING
            and entry.prior_state is not CampaignState.AWAITING_RULING
        ):
            opened = entry.committed_at
    return opened


def ruling_overdue_transitions(
    campaign: Campaign, log: Sequence[ControlLogEntry], now: datetime
) -> list[CampaignTransition]:
    """The ``ruling_overdue`` row the gate is owed at ``now`` (§9.2, §9.5; §24ae, §24al): one,
    once the supervisor's bound has passed since the gate opened, written once per proposal
    version. The bound is the supervisor's, whoever holds the seat.

    It keeps the campaign ``awaiting_ruling``, which is the bound's pause, and nothing rules on
    the gate: a ruling still resolves it, and the campaign never proceeds unapproved. Pure, so the
    sweep writes exactly what this decides.
    """
    proposal = campaign.proposal
    if campaign.state is not CampaignState.AWAITING_RULING or proposal is None:
        return []
    opened = gate_opened_at(log)
    if opened is None:
        return []
    written = {e.idempotency_key for e in log if e.outcome is ControlOutcome.APPLIED}
    bound = campaign.policy.ruling_bound_s
    binding = proposal.binding
    key = f"ruling_overdue:{proposal.run_id}:v{binding.version}"
    if (now - opened).total_seconds() < bound or key in written:
        return []
    return [
        CampaignTransition(
            operation=ControlOperation.RULING_OVERDUE,
            actor="squadops",
            actor_role=SWEEP_ROLE,
            reason=(
                f"the increment gate opened at {opened.isoformat()} and its ruling bound of "
                f"{bound}s has passed; the campaign stays awaiting_ruling and nothing proceeds "
                f"unapproved"
            ),
            idempotency_key=key,
            expected_state=CampaignState.AWAITING_RULING,
            next_state=CampaignState.AWAITING_RULING,
            target=proposal.run_id,
            binding={
                "proposal_id": binding.proposal_id,
                "version": binding.version,
                "opened_at": opened.isoformat(),
                "bound_s": bound,
            },
        )
    ]


# =============================================================================
# The plan gate's bound (#1708; §9.2's bound, applied to the gate after framing)
# =============================================================================


@dataclass(frozen=True)
class WaitingGate:
    """The inter-workload gate a campaign's cycle waits at, and since when."""

    cycle_id: str
    run_id: str
    gate_name: str
    opened_at: datetime


def waiting_gate(
    cycle_id: str, workload_sequence: Sequence[Mapping[str, Any]], runs
) -> WaitingGate | None:
    """The gate a cycle waits at, or None: its latest run completed, that run's workload names a
    gate after it, and the gate holds no decision. The latest run is read by its number, not by
    position, so a re-rolled framing (a second run of one workload) reads correctly."""
    live = [r for r in runs if r.status != RunStatus.CANCELLED]
    if not live:
        return None
    last = max(live, key=lambda r: r.run_number)
    if last.status != RunStatus.COMPLETED or last.finished_at is None:
        return None
    gate = next(
        (w.get("gate") for w in workload_sequence if w.get("type") == last.workload_type), None
    )
    if not gate or any(d.gate_name == gate for d in last.gate_decisions):
        return None
    return WaitingGate(cycle_id, last.run_id, str(gate), last.finished_at)


def plan_gate_overdue_transitions(
    campaign: Campaign,
    log: Sequence[ControlLogEntry],
    waiting: WaitingGate | None,
    now: datetime,
) -> list[CampaignTransition]:
    """The ``ruling_overdue`` row a cycle's plan gate is owed at ``now`` (#1708, §24al): one, once
    the supervisor's bound has passed since the gate opened, written once per run and gate.

    The same bound the increment gate has (§24ae), applied to the gate a framing stops at when its
    plan asks a design question. The row keeps the campaign in the state it is in, and nothing
    decides the gate: the supervisor's answer still resolves it, and nothing is approved by the
    bound. Pure, so the sweep writes exactly what this decides.
    """
    if waiting is None or waiting.gate_name == INCREMENT_RULING_GATE:
        return []
    if campaign.state not in _GATE_WAITING_STATES:
        return []
    written = {e.idempotency_key for e in log if e.outcome is ControlOutcome.APPLIED}
    bound = campaign.policy.ruling_bound_s
    key = f"gate_overdue:{waiting.run_id}:{waiting.gate_name}"
    if (now - waiting.opened_at).total_seconds() < bound or key in written:
        return []
    return [
        CampaignTransition(
            operation=ControlOperation.RULING_OVERDUE,
            actor="squadops",
            actor_role=SWEEP_ROLE,
            reason=(
                f"the {waiting.gate_name} gate on run {waiting.run_id} opened at "
                f"{waiting.opened_at.isoformat()} and its ruling bound of {bound}s has passed; it "
                f"waits on an answer and nothing proceeds without one"
            ),
            idempotency_key=key,
            expected_state=campaign.state,
            next_state=campaign.state,
            target=waiting.run_id,
            binding={
                "gate": waiting.gate_name,
                "cycle_id": waiting.cycle_id,
                "opened_at": waiting.opened_at.isoformat(),
                "bound_s": bound,
            },
        )
    ]


#: The states in which a campaign's cycle can wait at a gate after framing: the calibration, an
#: increment's build, and its repair or retry. The increment gate's own waiting state is
#: ``awaiting_ruling``, bounded by ``ruling_overdue_transitions``.
_GATE_WAITING_STATES = frozenset(
    {
        CampaignState.CALIBRATING,
        CampaignState.BUILDING,
        CampaignState.REPAIRING,
        CampaignState.RETRYING,
    }
)
