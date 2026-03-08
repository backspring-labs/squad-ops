"""Tests for execute_cycle() multi-workload orchestration (SIP-0083 Phase 2).

Covers the orchestration loop, gate polling, run creation, duplicate guard,
and event emission for multi-workload cycle execution.

Test strategy: mock _cycle_registry and _cycle_event_bus. Patch execute_run
on the executor instance to track calls without dispatching real tasks.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from squadops.cycles.models import (
    Cycle,
    GateDecision,
    GateDecisionValue,
    Run,
    RunStatus,
    TaskFlowPolicy,
)
from squadops.events.types import EventType

pytestmark = [pytest.mark.domain_orchestration]

NOW = datetime(2026, 1, 15, 12, 0, 0, tzinfo=UTC)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_cycle(workload_sequence: list[dict] | None = None, **kwargs) -> Cycle:
    """Build a Cycle with optional workload_sequence in applied_defaults."""
    applied_defaults = {}
    if workload_sequence is not None:
        applied_defaults["workload_sequence"] = workload_sequence
    return Cycle(
        cycle_id=kwargs.get("cycle_id", "cyc_001"),
        project_id="proj_001",
        created_at=NOW,
        created_by="system",
        prd_ref=None,
        squad_profile_id="full-squad",
        squad_profile_snapshot_ref="sha256:abc",
        task_flow_policy=TaskFlowPolicy(mode="sequential"),
        build_strategy="fresh",
        applied_defaults=applied_defaults,
        execution_overrides=kwargs.get("execution_overrides", {}),
    )


def _make_run(
    run_id: str = "run_001",
    run_number: int = 1,
    status: str = "completed",
    workload_type: str | None = None,
    gate_decisions: tuple = (),
) -> Run:
    return Run(
        run_id=run_id,
        cycle_id="cyc_001",
        run_number=run_number,
        status=status,
        initiated_by="api",
        resolved_config_hash="hash_abc",
        workload_type=workload_type,
        gate_decisions=gate_decisions,
    )


def _gate_decision(
    gate_name: str, decision: str, notes: str | None = None
) -> GateDecision:
    return GateDecision(
        gate_name=gate_name,
        decision=decision,
        decided_by="user",
        decided_at=NOW,
        notes=notes,
    )


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_registry():
    return AsyncMock()


@pytest.fixture
def mock_event_bus():
    return MagicMock()


@pytest.fixture
def executor(mock_registry, mock_event_bus):
    from adapters.cycles.distributed_flow_executor import DistributedFlowExecutor

    exec_ = DistributedFlowExecutor(
        cycle_registry=mock_registry,
        artifact_vault=AsyncMock(),
        queue=AsyncMock(),
        squad_profile=AsyncMock(),
        task_timeout=5.0,
    )
    exec_._cycle_event_bus = mock_event_bus
    # Patch execute_run to track calls without real dispatch
    exec_.execute_run = AsyncMock()
    return exec_


def _emit_types(mock_event_bus: MagicMock) -> list[str]:
    """Extract event types from all emit() calls."""
    return [c[0][0] for c in mock_event_bus.emit.call_args_list]


# ---------------------------------------------------------------------------
# Single-workload fast path
# ---------------------------------------------------------------------------


class TestSingleWorkloadFastPath:
    """D7: single-workload or missing sequence delegates to execute_run()."""

    async def test_missing_workload_sequence_delegates(
        self, executor, mock_registry
    ):
        """No workload_sequence key → delegates to execute_run()."""
        cycle = _make_cycle(workload_sequence=None)
        mock_registry.get_cycle.return_value = cycle

        await executor.execute_cycle("cyc_001", "run_001", "profile_1")

        executor.execute_run.assert_awaited_once_with("cyc_001", "run_001", "profile_1")

    async def test_empty_workload_sequence_delegates(
        self, executor, mock_registry
    ):
        """Empty workload_sequence list → delegates to execute_run()."""
        cycle = _make_cycle(workload_sequence=[])
        mock_registry.get_cycle.return_value = cycle

        await executor.execute_cycle("cyc_001", "run_001")

        executor.execute_run.assert_awaited_once_with("cyc_001", "run_001", None)

    async def test_single_entry_delegates(
        self, executor, mock_registry
    ):
        """Single-entry workload_sequence → delegates to execute_run()."""
        cycle = _make_cycle(workload_sequence=[{"type": "planning"}])
        mock_registry.get_cycle.return_value = cycle

        await executor.execute_cycle("cyc_001", "run_001")

        executor.execute_run.assert_awaited_once_with("cyc_001", "run_001", None)


# ---------------------------------------------------------------------------
# Multi-workload orchestration
# ---------------------------------------------------------------------------


class TestMultiWorkloadOrchestration:
    """Multi-workload cycle creates Runs sequentially."""

    async def test_two_workloads_creates_second_run(
        self, executor, mock_registry, mock_event_bus
    ):
        """2-entry sequence: first run completes, second run created and executed."""
        cycle = _make_cycle(workload_sequence=[
            {"type": "planning"},
            {"type": "implementation"},
        ])
        mock_registry.get_cycle.return_value = cycle

        run1 = _make_run("run_001", 1, "completed", "planning")
        run2 = _make_run("run_002", 2, "completed", "implementation")

        mock_registry.get_run.side_effect = [run1, run2]
        mock_registry.list_runs.return_value = [run1]
        mock_registry.create_run.side_effect = lambda r: r

        await executor.execute_cycle("cyc_001", "run_001")

        assert executor.execute_run.await_count == 2
        mock_registry.create_run.assert_called_once()
        created = mock_registry.create_run.call_args[0][0]
        assert created.workload_type == "implementation"
        assert created.run_number == 2
        assert created.status == RunStatus.QUEUED.value
        assert created.initiated_by == "system"

    async def test_three_workloads_creates_all_runs(
        self, executor, mock_registry, mock_event_bus
    ):
        """3-entry sequence creates all Runs sequentially."""
        cycle = _make_cycle(workload_sequence=[
            {"type": "planning"},
            {"type": "implementation"},
            {"type": "wrapup"},
        ])
        mock_registry.get_cycle.return_value = cycle

        run1 = _make_run("run_001", 1, "completed", "planning")
        run2 = _make_run("run_002", 2, "completed", "implementation")
        run3 = _make_run("run_003", 3, "completed", "wrapup")

        mock_registry.get_run.side_effect = [run1, run2, run3]
        # list_runs called twice per advancement: once in execute_cycle
        # duplicate guard, once inside _create_next_workload_run
        mock_registry.list_runs.side_effect = [
            [run1],          # duplicate guard after workload 0
            [run1],          # _create_next_workload_run for run2
            [run1, run2],    # duplicate guard after workload 1
            [run1, run2],    # _create_next_workload_run for run3
        ]
        mock_registry.create_run.side_effect = lambda r: r

        await executor.execute_cycle("cyc_001", "run_001")

        assert executor.execute_run.await_count == 3
        assert mock_registry.create_run.call_count == 2


# ---------------------------------------------------------------------------
# Failed/cancelled run stops orchestration
# ---------------------------------------------------------------------------


class TestOrchestrationStopping:
    """Failed or cancelled run stops the orchestration loop."""

    @pytest.mark.parametrize("terminal_status", ["failed", "cancelled"])
    async def test_terminal_run_stops_orchestration(
        self, executor, mock_registry, mock_event_bus, terminal_status
    ):
        """Failed or cancelled first run → no second run created."""
        cycle = _make_cycle(workload_sequence=[
            {"type": "planning"},
            {"type": "implementation"},
        ])
        mock_registry.get_cycle.return_value = cycle

        run1 = _make_run("run_001", 1, terminal_status, "planning")
        mock_registry.get_run.return_value = run1

        await executor.execute_cycle("cyc_001", "run_001")

        executor.execute_run.assert_awaited_once()
        mock_registry.create_run.assert_not_called()
        # WORKLOAD_COMPLETED emitted with correct terminal_status
        emit_call = mock_event_bus.emit.call_args
        assert emit_call[0][0] == EventType.WORKLOAD_COMPLETED
        payload = emit_call[1]["payload"]
        assert payload["terminal_status"] == terminal_status
        assert payload["workload_type"] == "planning"


# ---------------------------------------------------------------------------
# Inter-workload gates
# ---------------------------------------------------------------------------


class TestInterWorkloadGates:
    """Gate decisions control workload advancement."""

    async def test_approved_gate_advances_to_next_workload(
        self, executor, mock_registry, mock_event_bus
    ):
        """approved gate decision → next workload Run created and executed."""
        cycle = _make_cycle(workload_sequence=[
            {"type": "planning", "gate": "progress_plan_review"},
            {"type": "implementation"},
        ])
        mock_registry.get_cycle.return_value = cycle

        run1_no_decision = _make_run("run_001", 1, "completed", "planning")
        run1_with_decision = _make_run(
            "run_001", 1, "completed", "planning",
            gate_decisions=(_gate_decision("progress_plan_review", GateDecisionValue.APPROVED),),
        )
        run2 = _make_run("run_002", 2, "completed", "implementation")

        # get_run calls: status check, _is_cancelled inside poll, poll get_run,
        # then status check after second execute_run
        mock_registry.get_run.side_effect = [
            run1_no_decision,     # status check after execute_run
            run1_no_decision,     # _is_cancelled in _poll (not cancelled)
            run1_with_decision,   # _poll finds decision
            run2,                 # status check after second execute_run
        ]
        # list_runs: duplicate guard + _create_next_workload_run
        mock_registry.list_runs.side_effect = [
            [run1_with_decision],
            [run1_with_decision],
        ]
        mock_registry.create_run.side_effect = lambda r: r

        with patch.object(asyncio, "sleep", new_callable=AsyncMock):
            await executor.execute_cycle("cyc_001", "run_001")

        assert executor.execute_run.await_count == 2
        mock_registry.create_run.assert_called_once()

    async def test_rejected_gate_stops_orchestration(
        self, executor, mock_registry, mock_event_bus
    ):
        """rejected gate → no next workload Run created."""
        cycle = _make_cycle(workload_sequence=[
            {"type": "planning", "gate": "progress_plan_review"},
            {"type": "implementation"},
        ])
        mock_registry.get_cycle.return_value = cycle

        run1 = _make_run("run_001", 1, "completed", "planning")
        run1_with_rejection = _make_run(
            "run_001", 1, "completed", "planning",
            gate_decisions=(_gate_decision("progress_plan_review", GateDecisionValue.REJECTED),),
        )

        # get_run: status check, _is_cancelled in poll, poll get_run
        mock_registry.get_run.side_effect = [
            run1,                  # status check after execute_run
            run1,                  # _is_cancelled in _poll (not cancelled)
            run1_with_rejection,   # _poll finds rejection
        ]

        with patch.object(asyncio, "sleep", new_callable=AsyncMock):
            await executor.execute_cycle("cyc_001", "run_001")

        executor.execute_run.assert_awaited_once()
        mock_registry.create_run.assert_not_called()

    async def test_no_gate_skips_polling(
        self, executor, mock_registry, mock_event_bus
    ):
        """No gate on workload entry → advances without polling."""
        cycle = _make_cycle(workload_sequence=[
            {"type": "planning"},  # No gate key
            {"type": "implementation"},
        ])
        mock_registry.get_cycle.return_value = cycle

        run1 = _make_run("run_001", 1, "completed", "planning")
        run2 = _make_run("run_002", 2, "completed", "implementation")

        mock_registry.get_run.side_effect = [run1, run2]
        mock_registry.list_runs.return_value = [run1]
        mock_registry.create_run.side_effect = lambda r: r

        await executor.execute_cycle("cyc_001", "run_001")

        assert executor.execute_run.await_count == 2
        # No GATE_AWAITING event emitted
        assert EventType.WORKLOAD_GATE_AWAITING not in _emit_types(mock_event_bus)


# ---------------------------------------------------------------------------
# Positional duplicate guard
# ---------------------------------------------------------------------------


class TestDuplicateRunGuard:
    """D14: existing next run is reused, not re-created."""

    async def test_existing_next_run_reused(
        self, executor, mock_registry, mock_event_bus
    ):
        """If a non-cancelled run already exists at position i+1, reuse it."""
        cycle = _make_cycle(workload_sequence=[
            {"type": "planning"},
            {"type": "implementation"},
        ])
        mock_registry.get_cycle.return_value = cycle

        run1 = _make_run("run_001", 1, "completed", "planning")
        existing_run2 = _make_run("run_existing", 2, "queued", "implementation")
        run2_completed = _make_run("run_existing", 2, "completed", "implementation")

        mock_registry.get_run.side_effect = [run1, run2_completed]
        # list_runs returns both runs — run2 already exists
        mock_registry.list_runs.return_value = [run1, existing_run2]

        await executor.execute_cycle("cyc_001", "run_001")

        # No new run created — existing one reused
        mock_registry.create_run.assert_not_called()
        # execute_run called with existing run's ID
        second_call = executor.execute_run.call_args_list[1]
        assert second_call[0][1] == "run_existing"


# ---------------------------------------------------------------------------
# Event emission
# ---------------------------------------------------------------------------


class TestEventEmission:
    """Correct events emitted at each orchestration point."""

    async def test_completed_workload_emits_workload_completed(
        self, executor, mock_registry, mock_event_bus
    ):
        """Each completed workload emits WORKLOAD_COMPLETED with terminal_status."""
        cycle = _make_cycle(workload_sequence=[
            {"type": "planning"},
            {"type": "implementation"},
        ])
        mock_registry.get_cycle.return_value = cycle

        run1 = _make_run("run_001", 1, "completed", "planning")
        run2 = _make_run("run_002", 2, "completed", "implementation")

        mock_registry.get_run.side_effect = [run1, run2]
        mock_registry.list_runs.return_value = [run1]
        mock_registry.create_run.side_effect = lambda r: r

        await executor.execute_cycle("cyc_001", "run_001")

        types = _emit_types(mock_event_bus)
        assert types.count(EventType.WORKLOAD_COMPLETED) == 2
        # First WORKLOAD_COMPLETED payload
        first_completed = [
            c for c in mock_event_bus.emit.call_args_list
            if c[0][0] == EventType.WORKLOAD_COMPLETED
        ][0]
        assert first_completed[1]["payload"]["terminal_status"] == "completed"

    async def test_gate_emits_gate_awaiting(
        self, executor, mock_registry, mock_event_bus
    ):
        """Gate polling emits WORKLOAD_GATE_AWAITING before polling."""
        cycle = _make_cycle(workload_sequence=[
            {"type": "planning", "gate": "progress_plan_review"},
            {"type": "implementation"},
        ])
        mock_registry.get_cycle.return_value = cycle

        run1 = _make_run("run_001", 1, "completed", "planning")
        run1_decided = _make_run(
            "run_001", 1, "completed", "planning",
            gate_decisions=(_gate_decision("progress_plan_review", GateDecisionValue.APPROVED),),
        )
        run2 = _make_run("run_002", 2, "completed", "implementation")

        # get_run: status check, _is_cancelled, poll finds decision, status check run2
        mock_registry.get_run.side_effect = [run1, run1, run1_decided, run2]
        mock_registry.list_runs.side_effect = [[run1_decided], [run1_decided]]
        mock_registry.create_run.side_effect = lambda r: r

        with patch.object(asyncio, "sleep", new_callable=AsyncMock):
            await executor.execute_cycle("cyc_001", "run_001")

        types = _emit_types(mock_event_bus)
        assert EventType.WORKLOAD_GATE_AWAITING in types
        gate_call = [
            c for c in mock_event_bus.emit.call_args_list
            if c[0][0] == EventType.WORKLOAD_GATE_AWAITING
        ][0]
        assert gate_call[1]["payload"]["gate_name"] == "progress_plan_review"

    async def test_advancement_emits_workload_advanced(
        self, executor, mock_registry, mock_event_bus
    ):
        """Creating next run emits WORKLOAD_ADVANCED with next workload_type."""
        cycle = _make_cycle(workload_sequence=[
            {"type": "planning"},
            {"type": "implementation"},
        ])
        mock_registry.get_cycle.return_value = cycle

        run1 = _make_run("run_001", 1, "completed", "planning")
        run2 = _make_run("run_002", 2, "completed", "implementation")

        mock_registry.get_run.side_effect = [run1, run2]
        mock_registry.list_runs.return_value = [run1]
        mock_registry.create_run.side_effect = lambda r: r

        await executor.execute_cycle("cyc_001", "run_001")

        types = _emit_types(mock_event_bus)
        assert EventType.WORKLOAD_ADVANCED in types
        advanced_call = [
            c for c in mock_event_bus.emit.call_args_list
            if c[0][0] == EventType.WORKLOAD_ADVANCED
        ][0]
        assert advanced_call[1]["payload"]["workload_type"] == "implementation"

    async def test_full_event_sequence_for_two_workloads(
        self, executor, mock_registry, mock_event_bus
    ):
        """2-workload no-gate cycle emits: COMPLETED, ADVANCED, COMPLETED."""
        cycle = _make_cycle(workload_sequence=[
            {"type": "planning"},
            {"type": "implementation"},
        ])
        mock_registry.get_cycle.return_value = cycle

        run1 = _make_run("run_001", 1, "completed", "planning")
        run2 = _make_run("run_002", 2, "completed", "implementation")

        mock_registry.get_run.side_effect = [run1, run2]
        mock_registry.list_runs.return_value = [run1]
        mock_registry.create_run.side_effect = lambda r: r

        await executor.execute_cycle("cyc_001", "run_001")

        types = _emit_types(mock_event_bus)
        assert types == [
            EventType.WORKLOAD_COMPLETED,
            EventType.WORKLOAD_ADVANCED,
            EventType.WORKLOAD_COMPLETED,
        ]


# ---------------------------------------------------------------------------
# _poll_inter_workload_gate
# ---------------------------------------------------------------------------


class TestPollInterWorkloadGate:
    """_poll_inter_workload_gate polls until decision appears."""

    async def test_returns_decision_when_found(
        self, executor, mock_registry
    ):
        """Returns the GateDecision when gate_name matches."""
        cycle = _make_cycle()
        decision = _gate_decision("progress_plan_review", GateDecisionValue.APPROVED)
        run_with_decision = _make_run(
            gate_decisions=(decision,),
        )
        mock_registry.get_run.return_value = run_with_decision

        result = await executor._poll_inter_workload_gate(
            "run_001", cycle, "progress_plan_review"
        )

        assert result.gate_name == "progress_plan_review"
        assert result.decision == GateDecisionValue.APPROVED

    async def test_polls_until_decision_arrives(
        self, executor, mock_registry
    ):
        """Polls repeatedly until a decision for the gate appears."""
        cycle = _make_cycle()
        run_no_decision = _make_run(gate_decisions=())
        decision = _gate_decision("progress_plan_review", GateDecisionValue.APPROVED)
        run_with_decision = _make_run(gate_decisions=(decision,))

        # Each poll iteration: _is_cancelled→get_run, then explicit get_run
        # 2 iterations without decision, 1 iteration finds it = 6 get_run calls
        mock_registry.get_run.side_effect = [
            run_no_decision,     # _is_cancelled iter 1
            run_no_decision,     # poll get_run iter 1
            run_no_decision,     # _is_cancelled iter 2
            run_no_decision,     # poll get_run iter 2
            run_no_decision,     # _is_cancelled iter 3
            run_with_decision,   # poll get_run iter 3 — found
        ]

        with patch.object(asyncio, "sleep", new_callable=AsyncMock):
            result = await executor._poll_inter_workload_gate(
                "run_001", cycle, "progress_plan_review"
            )

        assert result.decision == GateDecisionValue.APPROVED
        assert mock_registry.get_run.call_count == 6

    async def test_cancellation_during_poll_raises(
        self, executor, mock_registry
    ):
        """Cancellation check during polling raises _CancellationError."""
        from adapters.cycles.distributed_flow_executor import _CancellationError

        cycle = _make_cycle()
        # _is_cancelled returns True
        executor._cancelled.add("run_001")

        with pytest.raises(_CancellationError):
            await executor._poll_inter_workload_gate(
                "run_001", cycle, "progress_plan_review"
            )


# ---------------------------------------------------------------------------
# _create_next_workload_run
# ---------------------------------------------------------------------------


class TestCreateNextWorkloadRun:
    """_create_next_workload_run creates a properly formed Run."""

    async def test_creates_run_with_correct_fields(
        self, executor, mock_registry
    ):
        """New Run has correct run_number, status, workload_type, initiated_by."""
        cycle = _make_cycle()
        completed = _make_run("run_001", 1, "completed", "planning")
        mock_registry.list_runs.return_value = [completed]
        mock_registry.create_run.side_effect = lambda r: r

        result = await executor._create_next_workload_run(
            cycle, completed, {"type": "implementation"}, config_hash="hash_abc"
        )

        assert result.run_number == 2
        assert result.status == RunStatus.QUEUED.value
        assert result.workload_type == "implementation"
        assert result.initiated_by == "system"
        assert result.cycle_id == "cyc_001"
        assert result.resolved_config_hash == "hash_abc"
        assert result.run_id.startswith("run_")

    async def test_run_number_increments_from_max(
        self, executor, mock_registry
    ):
        """run_number is max(existing) + 1, even with gaps."""
        cycle = _make_cycle()
        completed = _make_run("run_001", 1, "completed")
        run3 = _make_run("run_003", 3, "cancelled")  # Gap: no run 2
        mock_registry.list_runs.return_value = [completed, run3]
        mock_registry.create_run.side_effect = lambda r: r

        result = await executor._create_next_workload_run(
            cycle, completed, {"type": "implementation"}, config_hash="hash"
        )

        assert result.run_number == 4  # max(1,3) + 1
