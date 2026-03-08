"""Tests for execute_cycle() multi-workload orchestration (SIP-0083 Phases 2-3).

Covers the orchestration loop, gate polling, run creation, duplicate guard,
event emission, refinement artifact writing, and artifact forwarding.

Test strategy: mock _cycle_registry and _cycle_event_bus. Patch execute_run
on the executor instance to track calls without dispatching real tasks.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from squadops.cycles.models import (
    ArtifactRef,
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

    vault = AsyncMock()
    vault.list_artifacts.return_value = []  # Default: no promoted artifacts
    exec_ = DistributedFlowExecutor(
        cycle_registry=mock_registry,
        artifact_vault=vault,
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

    async def test_auto_gate_skips_polling(
        self, executor, mock_registry, mock_event_bus
    ):
        """gate: "auto" advances without polling — no GATE_AWAITING emitted."""
        cycle = _make_cycle(workload_sequence=[
            {"type": "implementation", "gate": "auto"},
            {"type": "wrapup"},
        ])
        mock_registry.get_cycle.return_value = cycle

        run1 = _make_run("run_001", 1, "completed", "implementation")
        run2 = _make_run("run_002", 2, "completed", "wrapup")

        mock_registry.get_run.side_effect = [run1, run2]
        mock_registry.list_runs.return_value = [run1]
        mock_registry.create_run.side_effect = lambda r: r

        await executor.execute_cycle("cyc_001", "run_001")

        assert executor.execute_run.await_count == 2
        assert EventType.WORKLOAD_GATE_AWAITING not in _emit_types(mock_event_bus)

    async def test_mixed_named_and_auto_gates(
        self, executor, mock_registry, mock_event_bus
    ):
        """Named gate polls, auto gate auto-progresses in same cycle."""
        cycle = _make_cycle(workload_sequence=[
            {"type": "planning", "gate": "progress_approval_required"},
            {"type": "implementation", "gate": "auto"},
            {"type": "wrapup"},
        ])
        mock_registry.get_cycle.return_value = cycle

        run1 = _make_run("run_001", 1, "completed", "planning")
        run1_decided = _make_run(
            "run_001", 1, "completed", "planning",
            gate_decisions=(_gate_decision(
                "progress_approval_required", GateDecisionValue.APPROVED
            ),),
        )
        run2 = _make_run("run_002", 2, "completed", "implementation")
        run3 = _make_run("run_003", 3, "completed", "wrapup")

        # get_run calls:
        # 1. status check after run1 execute_run
        # 2. _is_cancelled in poll
        # 3. poll finds decision
        # 4. status check after run2 execute_run
        # 5. status check after run3 execute_run
        mock_registry.get_run.side_effect = [
            run1,              # status check
            run1,              # _is_cancelled
            run1_decided,      # poll finds decision
            run2,              # status check
            run3,              # status check
        ]
        mock_registry.list_runs.side_effect = [
            [run1_decided],    # dup guard after workload 0
            [run1_decided],    # create run for workload 1
            [run1_decided, run2],  # dup guard after workload 1
            [run1_decided, run2],  # create run for workload 2
        ]
        mock_registry.create_run.side_effect = lambda r: r

        with patch.object(asyncio, "sleep", new_callable=AsyncMock):
            await executor.execute_cycle("cyc_001", "run_001")

        assert executor.execute_run.await_count == 3
        types = _emit_types(mock_event_bus)
        # Named gate emits GATE_AWAITING, auto gate does not
        assert types.count(EventType.WORKLOAD_GATE_AWAITING) == 1
        assert types.count(EventType.WORKLOAD_COMPLETED) == 3


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


# ---------------------------------------------------------------------------
# Helpers for Phase 3 (artifact forwarding)
# ---------------------------------------------------------------------------

T1 = datetime(2026, 1, 15, 10, 0, 0, tzinfo=UTC)
T2 = datetime(2026, 1, 15, 11, 0, 0, tzinfo=UTC)
T3 = datetime(2026, 1, 15, 12, 0, 0, tzinfo=UTC)


def _make_artifact_ref(
    artifact_id: str,
    run_id: str = "run_001",
    artifact_type: str = "code",
    promotion_status: str = "promoted",
    created_at: datetime = T1,
) -> ArtifactRef:
    return ArtifactRef(
        artifact_id=artifact_id,
        project_id="proj_001",
        artifact_type=artifact_type,
        filename=f"{artifact_id}.txt",
        content_hash="abc",
        size_bytes=100,
        media_type="text/plain",
        created_at=created_at,
        cycle_id="cyc_001",
        run_id=run_id,
        promotion_status=promotion_status,
    )


# ---------------------------------------------------------------------------
# Refinement artifact writing (Phase 3a)
# ---------------------------------------------------------------------------


class TestRefinementArtifactWriting:
    """approved_with_refinements writes refinement_notes.md artifact."""

    async def test_approved_with_refinements_writes_artifact(
        self, executor, mock_registry, mock_event_bus
    ):
        """approved_with_refinements with notes writes refinement_notes.md."""
        cycle = _make_cycle(workload_sequence=[
            {"type": "planning", "gate": "progress_plan_review"},
            {"type": "implementation"},
        ])
        mock_registry.get_cycle.return_value = cycle

        run1 = _make_run("run_001", 1, "completed", "planning")
        run1_decided = _make_run(
            "run_001", 1, "completed", "planning",
            gate_decisions=(_gate_decision(
                "progress_plan_review",
                GateDecisionValue.APPROVED_WITH_REFINEMENTS,
                notes="Add error handling to the parser",
            ),),
        )
        run2 = _make_run("run_002", 2, "completed", "implementation")

        # get_run: status check, _is_cancelled, poll finds decision, status check run2
        mock_registry.get_run.side_effect = [run1, run1, run1_decided, run2]
        mock_registry.list_runs.side_effect = [[run1_decided], [run1_decided]]
        mock_registry.create_run.side_effect = lambda r: r
        # Vault returns empty for forwarding overrides
        executor._artifact_vault.list_artifacts.return_value = []

        with patch.object(asyncio, "sleep", new_callable=AsyncMock):
            await executor.execute_cycle("cyc_001", "run_001")

        # store() called with a refinement artifact
        vault = executor._artifact_vault
        vault.store.assert_called_once()
        stored_ref = vault.store.call_args[0][0]
        stored_content = vault.store.call_args[0][1]
        assert stored_ref.filename == "refinement_notes.md"
        assert stored_ref.artifact_type == "document"
        assert stored_ref.run_id == "run_001"
        assert stored_ref.media_type == "text/markdown"
        assert stored_ref.metadata == {"producing_task_type": "gate.refinement_notes"}
        assert b"Add error handling to the parser" in stored_content

        # append_artifact_refs called to register on run
        mock_registry.append_artifact_refs.assert_called_once()
        call_args = mock_registry.append_artifact_refs.call_args
        assert call_args[0][0] == "run_001"
        assert stored_ref.artifact_id in call_args[0][1]

    @pytest.mark.parametrize("notes", [None, ""])
    async def test_empty_notes_does_not_write_artifact(
        self, executor, mock_registry, mock_event_bus, notes
    ):
        """approved_with_refinements with empty/None notes skips artifact."""
        cycle = _make_cycle(workload_sequence=[
            {"type": "planning", "gate": "progress_plan_review"},
            {"type": "implementation"},
        ])
        mock_registry.get_cycle.return_value = cycle

        run1 = _make_run("run_001", 1, "completed", "planning")
        run1_decided = _make_run(
            "run_001", 1, "completed", "planning",
            gate_decisions=(_gate_decision(
                "progress_plan_review",
                GateDecisionValue.APPROVED_WITH_REFINEMENTS,
                notes=notes,
            ),),
        )
        run2 = _make_run("run_002", 2, "completed", "implementation")

        mock_registry.get_run.side_effect = [run1, run1, run1_decided, run2]
        mock_registry.list_runs.side_effect = [[run1_decided], [run1_decided]]
        mock_registry.create_run.side_effect = lambda r: r
        executor._artifact_vault.list_artifacts.return_value = []

        with patch.object(asyncio, "sleep", new_callable=AsyncMock):
            await executor.execute_cycle("cyc_001", "run_001")

        # No artifact stored
        executor._artifact_vault.store.assert_not_called()

    async def test_refinement_still_advances_to_next_workload(
        self, executor, mock_registry, mock_event_bus
    ):
        """approved_with_refinements proceeds to next workload (not blocked)."""
        cycle = _make_cycle(workload_sequence=[
            {"type": "planning", "gate": "progress_plan_review"},
            {"type": "implementation"},
        ])
        mock_registry.get_cycle.return_value = cycle

        run1 = _make_run("run_001", 1, "completed", "planning")
        run1_decided = _make_run(
            "run_001", 1, "completed", "planning",
            gate_decisions=(_gate_decision(
                "progress_plan_review",
                GateDecisionValue.APPROVED_WITH_REFINEMENTS,
                notes="Minor fix needed",
            ),),
        )
        run2 = _make_run("run_002", 2, "completed", "implementation")

        mock_registry.get_run.side_effect = [run1, run1, run1_decided, run2]
        mock_registry.list_runs.side_effect = [[run1_decided], [run1_decided]]
        mock_registry.create_run.side_effect = lambda r: r
        executor._artifact_vault.list_artifacts.return_value = []

        with patch.object(asyncio, "sleep", new_callable=AsyncMock):
            await executor.execute_cycle("cyc_001", "run_001")

        # Both workloads executed
        assert executor.execute_run.await_count == 2
        mock_registry.create_run.assert_called_once()


# ---------------------------------------------------------------------------
# Artifact forwarding (Phase 3b)
# ---------------------------------------------------------------------------


class TestBuildForwardingOverrides:
    """_build_forwarding_overrides builds correct overrides dict."""

    async def test_promoted_artifacts_forwarded_as_prior_workload_refs(
        self, executor
    ):
        """Promoted artifacts become prior_workload_artifact_refs."""
        cycle = _make_cycle()
        completed = _make_run("run_001", 1, "completed", "implementation")
        art1 = _make_artifact_ref("art_001", created_at=T2)
        art2 = _make_artifact_ref("art_002", created_at=T1)

        executor._artifact_vault.list_artifacts.return_value = [art1, art2]

        result = await executor._build_forwarding_overrides(cycle, completed)

        # Sorted by created_at: art_002 (T1) before art_001 (T2)
        assert result["prior_workload_artifact_refs"] == ["art_002", "art_001"]

    async def test_no_promoted_artifacts_returns_empty_list(
        self, executor
    ):
        """No promoted artifacts → empty prior_workload_artifact_refs."""
        cycle = _make_cycle()
        completed = _make_run("run_001", 1, "completed", "planning")

        executor._artifact_vault.list_artifacts.return_value = []

        result = await executor._build_forwarding_overrides(cycle, completed)

        assert result["prior_workload_artifact_refs"] == []

    async def test_planning_run_forwards_plan_artifact_refs(
        self, executor
    ):
        """Planning workload forwards promoted documents as plan_artifact_refs."""
        cycle = _make_cycle()
        completed = _make_run("run_001", 1, "completed", "planning")
        doc1 = _make_artifact_ref("art_plan_01", artifact_type="document", created_at=T2)
        doc2 = _make_artifact_ref("art_plan_02", artifact_type="document", created_at=T1)

        # First call: promoted artifacts (all types), second: promoted documents
        executor._artifact_vault.list_artifacts.side_effect = [
            [doc1, doc2],  # all promoted
            [doc1, doc2],  # promoted documents
        ]

        result = await executor._build_forwarding_overrides(cycle, completed)

        assert result["plan_artifact_refs"] == ["art_plan_02", "art_plan_01"]
        assert "impl_run_id" not in result

    async def test_implementation_run_forwards_impl_run_id(
        self, executor
    ):
        """Implementation workload sets impl_run_id."""
        cycle = _make_cycle()
        completed = _make_run("run_001", 1, "completed", "implementation")

        executor._artifact_vault.list_artifacts.return_value = []

        result = await executor._build_forwarding_overrides(cycle, completed)

        assert result["impl_run_id"] == "run_001"
        assert "plan_artifact_refs" not in result

    async def test_scalar_override_not_overwritten(
        self, executor
    ):
        """Operator override for impl_run_id takes precedence."""
        cycle = _make_cycle(execution_overrides={"impl_run_id": "run_operator"})
        completed = _make_run("run_001", 1, "completed", "implementation")

        executor._artifact_vault.list_artifacts.return_value = []

        result = await executor._build_forwarding_overrides(cycle, completed)

        assert result["impl_run_id"] == "run_operator"

    async def test_list_override_merged_and_deduped(
        self, executor
    ):
        """Operator list overrides merge with forwarded refs, no duplicates."""
        cycle = _make_cycle(
            execution_overrides={"prior_workload_artifact_refs": ["art_existing", "art_001"]}
        )
        completed = _make_run("run_001", 1, "completed", "planning")
        art1 = _make_artifact_ref("art_001", created_at=T1)
        art2 = _make_artifact_ref("art_new", created_at=T2)

        executor._artifact_vault.list_artifacts.return_value = [art1, art2]

        result = await executor._build_forwarding_overrides(cycle, completed)

        refs = result["prior_workload_artifact_refs"]
        # Operator values first, then new ones (deduped: art_001 already present)
        assert refs == ["art_existing", "art_001", "art_new"]

    async def test_forwarded_refs_sorted_by_creation_time(
        self, executor
    ):
        """Forwarded artifact refs are deterministically sorted by created_at."""
        cycle = _make_cycle()
        completed = _make_run("run_001", 1, "completed", "planning")
        # Out of order by creation time
        art_late = _make_artifact_ref("art_late", created_at=T3)
        art_early = _make_artifact_ref("art_early", created_at=T1)
        art_mid = _make_artifact_ref("art_mid", created_at=T2)

        executor._artifact_vault.list_artifacts.return_value = [art_late, art_early, art_mid]

        result = await executor._build_forwarding_overrides(cycle, completed)

        assert result["prior_workload_artifact_refs"] == [
            "art_early", "art_mid", "art_late"
        ]
