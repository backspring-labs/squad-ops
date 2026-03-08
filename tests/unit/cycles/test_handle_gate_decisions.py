"""Tests for _handle_gate() decision handling (SIP-0083 prerequisite fix).

Verifies all 4 GateDecisionValue values are handled correctly:
- approved → resumes run
- approved_with_refinements → resumes run
- rejected → raises _ExecutionError
- returned_for_revision → raises _ExecutionError with descriptive message
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from squadops.cycles.models import (
    Cycle,
    Gate,
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
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def cycle():
    return Cycle(
        cycle_id="cyc_001",
        project_id="proj_001",
        created_at=NOW,
        created_by="system",
        prd_ref=None,
        squad_profile_id="full-squad",
        squad_profile_snapshot_ref="sha256:abc",
        task_flow_policy=TaskFlowPolicy(
            mode="fan_out_soft_gates",
            gates=(
                Gate(
                    name="progress_plan_review",
                    description="Review plan",
                    after_task_types=("plan_tasks",),
                ),
            ),
        ),
        build_strategy="fresh",
    )


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
    return exec_


def _run_with_gate_decision(decision_value: str, notes: str | None = None) -> Run:
    """Build a Run with a single gate decision."""
    return Run(
        run_id="run_001",
        cycle_id="cyc_001",
        run_number=1,
        status=RunStatus.PAUSED.value,
        initiated_by="api",
        resolved_config_hash="hash",
        gate_decisions=(
            GateDecision(
                gate_name="progress_plan_review",
                decision=decision_value,
                decided_by="user",
                decided_at=NOW,
                notes=notes,
            ),
        ),
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestHandleGateDecisions:
    """_handle_gate() handles all 4 GateDecisionValue values."""

    async def test_approved_resumes_run(self, executor, mock_registry, mock_event_bus, cycle):
        """approved → update status to RUNNING, emit RUN_RESUMED."""
        mock_registry.get_run.return_value = _run_with_gate_decision(
            GateDecisionValue.APPROVED
        )
        mock_registry.update_run_status.return_value = None

        await executor._handle_gate("run_001", cycle, "plan_tasks")

        # _handle_gate first pauses, then resumes — check last call is RUNNING
        status_calls = mock_registry.update_run_status.call_args_list
        assert status_calls[-1] == ((("run_001", RunStatus.RUNNING),))
        # RUN_PAUSED + RUN_RESUMED emitted
        emit_calls = mock_event_bus.emit.call_args_list
        emit_types = [c[0][0] for c in emit_calls]
        assert EventType.RUN_RESUMED in emit_types

    async def test_approved_with_refinements_resumes_run(
        self, executor, mock_registry, mock_event_bus, cycle
    ):
        """approved_with_refinements → same resume behavior as approved."""
        mock_registry.get_run.return_value = _run_with_gate_decision(
            GateDecisionValue.APPROVED_WITH_REFINEMENTS, notes="minor tweaks"
        )
        mock_registry.update_run_status.return_value = None

        await executor._handle_gate("run_001", cycle, "plan_tasks")

        # _handle_gate first pauses, then resumes — check last call is RUNNING
        status_calls = mock_registry.update_run_status.call_args_list
        assert status_calls[-1] == ((("run_001", RunStatus.RUNNING),))
        emit_calls = mock_event_bus.emit.call_args_list
        emit_types = [c[0][0] for c in emit_calls]
        assert EventType.RUN_RESUMED in emit_types

    async def test_rejected_raises_execution_error(
        self, executor, mock_registry, cycle
    ):
        """rejected → raises _ExecutionError."""
        from adapters.cycles.distributed_flow_executor import _ExecutionError

        mock_registry.get_run.return_value = _run_with_gate_decision(
            GateDecisionValue.REJECTED, notes="not ready"
        )

        with pytest.raises(_ExecutionError, match="rejected"):
            await executor._handle_gate("run_001", cycle, "plan_tasks")

    async def test_returned_for_revision_raises_execution_error(
        self, executor, mock_registry, cycle
    ):
        """returned_for_revision → raises _ExecutionError explaining manual retry is needed."""
        from adapters.cycles.distributed_flow_executor import _ExecutionError

        mock_registry.get_run.return_value = _run_with_gate_decision(
            GateDecisionValue.RETURNED_FOR_REVISION, notes="needs more detail"
        )

        with pytest.raises(_ExecutionError, match="manual retry-run creation"):
            await executor._handle_gate("run_001", cycle, "plan_tasks")

    async def test_no_decision_polls_until_decision_arrives(
        self, executor, mock_registry, mock_event_bus, cycle
    ):
        """No decision → polls; when decision arrives, handles it."""
        # First call: no decision. Second call: approved.
        run_no_decision = Run(
            run_id="run_001",
            cycle_id="cyc_001",
            run_number=1,
            status=RunStatus.PAUSED.value,
            initiated_by="api",
            resolved_config_hash="hash",
            gate_decisions=(),
        )
        run_with_decision = _run_with_gate_decision(GateDecisionValue.APPROVED)
        mock_registry.get_run.side_effect = [run_no_decision, run_with_decision]
        mock_registry.update_run_status.return_value = None

        # Patch sleep to avoid real delays
        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(asyncio, "sleep", AsyncMock())
            await executor._handle_gate("run_001", cycle, "plan_tasks")

        assert mock_registry.get_run.call_count == 2
        status_calls = mock_registry.update_run_status.call_args_list
        assert status_calls[-1] == ((("run_001", RunStatus.RUNNING),))
