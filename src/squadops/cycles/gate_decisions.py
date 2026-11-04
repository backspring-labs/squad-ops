"""Recording a gate decision: one function for every decider (#1986).

A decision is three things in order: the row on the run, the promotion an approval implies,
and one ``gate.decided`` event. Three paths assembled that sequence by hand: the HTTP gate
route, the executor's pass-through when the design asks no question, and the workload gate's
plan-validation rejection. They had already diverged twice:

- **#854:** the pass-through recorded an approval and promoted nothing, because promotion
  lived only in the route. The implementation run then refused for want of a plan.
- **The event's shape:** the route emitted it keyed on the gate (``entity_type="gate"``,
  SIP-0077 §7.3); the two machine paths keyed it on the run, without notes. The metrics
  bridge labels by ``entity_type``, so one kind of decision was counted under two labels.
- **Which decisions promote:** the gate proceeds on ``approved_with_refinements``
  (``squadops runs gate --with-refinements``), but the route promoted only on ``approved``.
  So a refinement approval forwarded nothing to the next workload. ``APPROVING_DECISIONS``
  is now the one answer for both.

The supervisor role (#1940) and the gate policy's auto tier (#1708) are the next deciders.
Each calls this, so neither is a fourth copy. ``decided_by`` is what tells a human decision
from a machine one, never the event's shape.

What stays with the caller, before the call: anything that decides *whether* the decision
may be recorded (the waiver's validation, the increment ruling's control-log row).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from squadops.cycles.gate_promotion import promote_run_artifacts
from squadops.cycles.lifecycle import GATE_REJECTED_STATES
from squadops.cycles.models import (
    APPROVING_DECISIONS,
    GateAlreadyDecidedError,
    GateDecision,
    Run,
    RunStatus,
    RunTerminalError,
    ValidationError,
)
from squadops.events.types import EventType

if TYPE_CHECKING:
    from squadops.ports.cycles.artifact_vault import ArtifactVaultPort
    from squadops.ports.cycles.cycle_registry import CycleRegistryPort
    from squadops.ports.events.cycle_event_bus import CycleEventBusPort


def gate_decided_payload(decision: GateDecision) -> dict[str, Any]:
    """The ``gate.decided`` payload: SIP-0077 §7.3's fields, and the waiver when there is one."""
    payload: dict[str, Any] = {
        "gate_name": decision.gate_name,
        "decision": decision.decision,
        "decided_by": decision.decided_by,
        "decided_at": decision.decided_at.isoformat(),
        "notes": decision.notes,
    }
    if decision.waived_checks:
        payload["waived_checks"] = list(decision.waived_checks)
    return payload


async def refuse_undecidable(
    registry: CycleRegistryPort, run_id: str, decision: GateDecision
) -> None:
    """Raise what ``CycleRegistryPort.record_gate_decision`` would raise for ``decision``, without
    recording it: for a caller that must write something else first and can't write it for a
    decision the registry would refuse (SIP-0109 §24da: a delegated answer's audit row). The same
    decision again passes, as the registry's no-op does. A read, so a decision that lands between
    this and the record can still refuse it. The registry stays the one enforcement point (T11),
    and ``test_gate_decision_preflight.py`` holds the two to the same answers."""
    run = await registry.get_run(run_id)
    status = RunStatus(run.status)
    if status in GATE_REJECTED_STATES:
        raise RunTerminalError(
            f"Cannot record gate decision on gate-rejected run (status={status.value})"
        )
    cycle = await registry.get_cycle(run.cycle_id)
    if decision.gate_name not in {g.name for g in cycle.task_flow_policy.gates}:
        raise ValidationError(f"Gate {decision.gate_name!r} not found in TaskFlowPolicy")
    for existing in run.gate_decisions:
        if existing.gate_name == decision.gate_name and existing.decision != decision.decision:
            raise GateAlreadyDecidedError(
                f"Gate {decision.gate_name!r} already decided as {existing.decision!r}"
            )


async def record_gate_decision(
    registry: CycleRegistryPort,
    vault: ArtifactVaultPort | None,
    bus: CycleEventBusPort,
    *,
    project_id: str,
    cycle_id: str,
    run_id: str,
    decision: GateDecision,
) -> Run:
    """Record ``decision`` on the run, promote its artifacts if it approves, emit ``gate.decided``.

    Returns the run as the registry recorded it. A registry failure raises before anything
    is promoted or emitted. Promotion never raises (``promote_run_artifacts``): the decision
    is already recorded, and a promotion that did not happen surfaces as #424's refusal.
    ``vault`` may be ``None`` where none is wired; promotion is then skipped with a warning.
    """
    updated = await registry.record_gate_decision(run_id, decision)
    if decision.decision in APPROVING_DECISIONS:
        await promote_run_artifacts(vault, run_id)
    bus.emit(
        EventType.GATE_DECIDED,
        entity_type="gate",
        entity_id=decision.gate_name,
        context={"cycle_id": cycle_id, "run_id": run_id, "project_id": project_id},
        payload=gate_decided_payload(decision),
    )
    return updated
