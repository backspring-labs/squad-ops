"""
In-memory cycle registry adapter (SIP-0064, T1: memory-only for v0.9.3).

Stores mutable internal records, returns frozen snapshots via dataclasses.replace (T10).
"""

from __future__ import annotations

import dataclasses

from squadops.cycles.lifecycle import TERMINAL_STATES, validate_run_transition
from squadops.cycles.models import (
    Cycle,
    CycleNotFoundError,
    CycleStatus,
    GateAlreadyDecidedError,
    GateDecision,
    IllegalStateTransitionError,
    Run,
    RunNotFoundError,
    RunStatus,
    RunTerminalError,
    ValidationError,
)
from squadops.ports.cycles.cycle_registry import CycleRegistryPort


class MemoryCycleRegistry(CycleRegistryPort):
    """In-memory cycle and run store for v0.9.3."""

    def __init__(self) -> None:
        # Mutable internal records
        self._cycles: dict[str, dict] = {}
        self._runs: dict[str, dict] = {}
        self._cancelled_cycles: set[str] = set()

    # --- Cycle CRUD ---

    async def create_cycle(self, cycle: Cycle) -> Cycle:
        self._cycles[cycle.cycle_id] = dataclasses.asdict(cycle)
        # Store the TaskFlowPolicy object for gate validation
        self._cycles[cycle.cycle_id]["_policy_obj"] = cycle.task_flow_policy
        return cycle

    async def get_cycle(self, cycle_id: str) -> Cycle:
        if cycle_id not in self._cycles:
            raise CycleNotFoundError(f"Cycle not found: {cycle_id}")
        return self._to_cycle(self._cycles[cycle_id])

    async def list_cycles(
        self, project_id: str, *, status: CycleStatus | None = None
    ) -> list[Cycle]:
        from squadops.cycles.lifecycle import derive_cycle_status

        results = []
        for data in self._cycles.values():
            if data["project_id"] != project_id:
                continue
            cycle = self._to_cycle(data)
            if status is not None:
                runs = [
                    self._to_run(r)
                    for r in self._runs.values()
                    if r["cycle_id"] == cycle.cycle_id
                ]
                derived = derive_cycle_status(
                    runs, cycle.cycle_id in self._cancelled_cycles
                )
                if derived != status:
                    continue
            results.append(cycle)
        return results

    async def cancel_cycle(self, cycle_id: str) -> None:
        if cycle_id not in self._cycles:
            raise CycleNotFoundError(f"Cycle not found: {cycle_id}")
        self._cancelled_cycles.add(cycle_id)

    # --- Run CRUD ---

    async def create_run(self, run: Run) -> Run:
        if run.cycle_id in self._cancelled_cycles:
            raise IllegalStateTransitionError(
                f"Cannot create run on cancelled cycle: {run.cycle_id}"
            )
        self._runs[run.run_id] = dataclasses.asdict(run)
        return run

    async def get_run(self, run_id: str) -> Run:
        if run_id not in self._runs:
            raise RunNotFoundError(f"Run not found: {run_id}")
        return self._to_run(self._runs[run_id])

    async def list_runs(self, cycle_id: str) -> list[Run]:
        return [
            self._to_run(data)
            for data in self._runs.values()
            if data["cycle_id"] == cycle_id
        ]

    async def update_run_status(self, run_id: str, status: RunStatus) -> Run:
        if run_id not in self._runs:
            raise RunNotFoundError(f"Run not found: {run_id}")
        data = self._runs[run_id]
        validate_run_transition(RunStatus(data["status"]), status)
        data["status"] = status.value
        return self._to_run(data)

    async def cancel_run(self, run_id: str) -> None:
        if run_id not in self._runs:
            raise RunNotFoundError(f"Run not found: {run_id}")
        data = self._runs[run_id]
        validate_run_transition(RunStatus(data["status"]), RunStatus.CANCELLED)
        data["status"] = RunStatus.CANCELLED.value

    async def record_gate_decision(self, run_id: str, decision: GateDecision) -> Run:
        """Record a gate decision (T11: single enforcement point)."""
        if run_id not in self._runs:
            raise RunNotFoundError(f"Run not found: {run_id}")

        run_data = self._runs[run_id]
        cycle_id = run_data["cycle_id"]

        # Check terminal state
        current_status = RunStatus(run_data["status"])
        if current_status in TERMINAL_STATES:
            raise RunTerminalError(
                f"Cannot record gate decision on terminal run (status={current_status.value})"
            )

        # Check gate_name exists in policy
        if cycle_id not in self._cycles:
            raise CycleNotFoundError(f"Cycle not found: {cycle_id}")
        policy = self._cycles[cycle_id]["_policy_obj"]
        gate_names = {g.name for g in policy.gates}
        if decision.gate_name not in gate_names:
            raise ValidationError(
                f"Gate {decision.gate_name!r} not found in TaskFlowPolicy"
            )

        # Check existing decisions
        existing = list(run_data.get("gate_decisions", ()))
        for existing_dec in existing:
            if existing_dec["gate_name"] == decision.gate_name:
                if existing_dec["decision"] == decision.decision:
                    # Idempotent — same decision is a no-op
                    return self._to_run(run_data)
                else:
                    raise GateAlreadyDecidedError(
                        f"Gate {decision.gate_name!r} already decided as "
                        f"{existing_dec['decision']!r}"
                    )

        # Record the decision
        existing.append(dataclasses.asdict(decision))
        run_data["gate_decisions"] = existing
        return self._to_run(run_data)

    # --- Internal helpers ---

    def _to_cycle(self, data: dict) -> Cycle:
        """Convert internal dict to frozen Cycle."""
        from squadops.cycles.models import Gate, TaskFlowPolicy

        d = {k: v for k, v in data.items() if not k.startswith("_")}
        # Reconstruct nested frozen dataclasses
        tfp = d["task_flow_policy"]
        if isinstance(tfp, dict):
            gates = tuple(
                Gate(
                    name=g["name"],
                    description=g["description"],
                    after_task_types=tuple(g["after_task_types"]),
                )
                for g in tfp.get("gates", ())
            )
            d["task_flow_policy"] = TaskFlowPolicy(mode=tfp["mode"], gates=gates)
        d["expected_artifact_types"] = tuple(d.get("expected_artifact_types", ()))
        return Cycle(**d)

    def _to_run(self, data: dict) -> Run:
        """Convert internal dict to frozen Run."""
        d = dict(data)
        # Reconstruct gate decisions as tuples
        gds = d.get("gate_decisions", [])
        d["gate_decisions"] = tuple(
            GateDecision(
                gate_name=g["gate_name"],
                decision=g["decision"],
                decided_by=g["decided_by"],
                decided_at=g["decided_at"],
                notes=g.get("notes"),
            )
            for g in gds
        )
        d["artifact_refs"] = tuple(d.get("artifact_refs", ()))
        return Run(**d)
