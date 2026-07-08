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
        squad_profile_id="full",
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
def executor(mock_registry, mock_event_bus, reply_router):
    from adapters.cycles.dispatched_flow_executor import DispatchedFlowExecutor

    exec_ = DispatchedFlowExecutor(
        cycle_registry=mock_registry,
        artifact_vault=AsyncMock(),
        queue=AsyncMock(),
        squad_profile=AsyncMock(),
        task_timeout=5.0,
        reply_router=reply_router,
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
        mock_registry.get_run.return_value = _run_with_gate_decision(GateDecisionValue.APPROVED)
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

    async def test_rejected_raises_execution_error(self, executor, mock_registry, cycle):
        """rejected → raises _ExecutionError."""
        from adapters.cycles.dispatched_flow_executor import _ExecutionError

        mock_registry.get_run.return_value = _run_with_gate_decision(
            GateDecisionValue.REJECTED, notes="not ready"
        )

        with pytest.raises(_ExecutionError, match="rejected"):
            await executor._handle_gate("run_001", cycle, "plan_tasks")

    async def test_returned_for_revision_raises_execution_error(
        self, executor, mock_registry, cycle
    ):
        """returned_for_revision → raises _ExecutionError explaining manual retry is needed."""
        from adapters.cycles.dispatched_flow_executor import _ExecutionError

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


# ---------------------------------------------------------------------------
# #295 (SIP-0097 slice 6): plan↔squad mismatch rejected at the plan-review gate
# ---------------------------------------------------------------------------

_PLAN_YAML_WITH_BUILDER_ROLE = """\
version: 1
project_id: proj_001
cycle_id: cyc_001
prd_hash: abc123
summary:
  total_dev_tasks: 0
  total_qa_tasks: 0
  total_tasks: 1
tasks:
  - task_index: 1
    task_type: builder.assemble
    role: builder
    focus: packaging
    description: Assemble the app for handoff
"""

_PLAN_YAML_DEV_ONLY = _PLAN_YAML_WITH_BUILDER_ROLE.replace(
    "task_type: builder.assemble", "task_type: development.develop"
).replace("role: builder", "role: dev")


def _profile_without_builder():
    """A 2-role squad profile (no builder) for mismatch tests."""
    from squadops.cycles.models import AgentProfileEntry, SquadProfile

    return SquadProfile(
        profile_id="smoke",
        name="Smoke",
        description="No builder",
        version=1,
        agents=(
            AgentProfileEntry(agent_id="neo", role="dev", model="m", enabled=True),
            AgentProfileEntry(agent_id="eve", role="qa", model="m", enabled=True),
        ),
        created_at=NOW,
    )


def _plan_cycle(cycle):
    """The gate-fixture cycle with the implementation-plan path enabled."""
    import dataclasses

    return dataclasses.replace(cycle, applied_defaults={"implementation_plan": True})


def _plan_artifact(vault, artifact_id: str, yaml_text: str, *, filename="implementation_plan.yaml"):
    """Register a plan artifact on the mock vault; returns (artifact_id, ref)."""
    ref = MagicMock()
    ref.filename = filename
    ref.artifact_type = "control_implementation_plan"
    vault.retrieve = AsyncMock(return_value=(ref, yaml_text.encode()))
    return (artifact_id, ref)


class TestPlanReviewGateCheck:
    """#295: _handle_gate rejects an unsatisfiable materialized plan BEFORE
    pausing for operator review; satisfiable/absent/unreadable plans leave
    gate behavior exactly as it was (dispatch-time net retained)."""

    async def test_unsatisfiable_plan_rejected_before_pause(
        self, executor, mock_registry, mock_event_bus, cycle
    ):
        """Bug class: a plan naming a role the squad lacks used to sail through
        the gate and abort ~9 min later at implementation dispatch (#172). It
        must now fail AT the gate, with the role, profile, and gate named —
        and the run must never pause (the operator is not asked to review a
        doomed plan)."""
        from adapters.cycles.execution_errors import _ExecutionError

        stored = [
            _plan_artifact(executor._artifact_vault, "art_plan", _PLAN_YAML_WITH_BUILDER_ROLE)
        ]

        with pytest.raises(_ExecutionError) as exc_info:
            await executor._handle_gate(
                "run_001",
                _plan_cycle(cycle),
                "plan_tasks",
                stored_artifacts=stored,
                profile=_profile_without_builder(),
            )

        msg = str(exc_info.value)
        assert "'builder' not in profile" in msg
        assert "'smoke'" in msg
        assert "progress_plan_review" in msg
        # Never paused: no status write, no RUN_PAUSED.
        mock_registry.update_run_status.assert_not_awaited()
        emit_types = [c[0][0] for c in mock_event_bus.emit.call_args_list]
        assert EventType.RUN_PAUSED not in emit_types

    async def test_satisfiable_plan_gates_normally(
        self, executor, mock_registry, mock_event_bus, cycle
    ):
        """A plan the squad CAN satisfy must not trip the check — the gate
        pauses and an approved decision resumes the run, exactly as before."""
        mock_registry.get_run.return_value = _run_with_gate_decision(GateDecisionValue.APPROVED)
        stored = [_plan_artifact(executor._artifact_vault, "art_plan", _PLAN_YAML_DEV_ONLY)]

        await executor._handle_gate(
            "run_001",
            _plan_cycle(cycle),
            "plan_tasks",
            stored_artifacts=stored,
            profile=_profile_without_builder(),
        )

        status_calls = mock_registry.update_run_status.call_args_list
        assert status_calls[-1] == ((("run_001", RunStatus.RUNNING),))

    async def test_no_plan_artifact_skips_check(
        self, executor, mock_registry, mock_event_bus, cycle
    ):
        """No materialized plan among the run's artifacts → the check is inert
        (vault never read past the scan) and the gate pauses as before."""
        mock_registry.get_run.return_value = _run_with_gate_decision(GateDecisionValue.APPROVED)
        other_ref = MagicMock()
        other_ref.filename = "strategy_analysis.md"
        other_ref.artifact_type = "document"

        await executor._handle_gate(
            "run_001",
            _plan_cycle(cycle),
            "plan_tasks",
            stored_artifacts=[("art_doc", other_ref)],
            profile=_profile_without_builder(),
        )

        executor._artifact_vault.retrieve.assert_not_awaited()
        status_calls = mock_registry.update_run_status.call_args_list
        assert status_calls[-1] == ((("run_001", RunStatus.RUNNING),))

    async def test_implementation_plan_disabled_skips_check(
        self, executor, mock_registry, mock_event_bus, cycle
    ):
        """Cycles without the implementation-plan path (e.g. smoke/selftest)
        must be untouched — even if an artifact matches the plan filename."""
        mock_registry.get_run.return_value = _run_with_gate_decision(GateDecisionValue.APPROVED)
        stored = [
            _plan_artifact(executor._artifact_vault, "art_plan", _PLAN_YAML_WITH_BUILDER_ROLE)
        ]

        await executor._handle_gate(
            "run_001",
            cycle,  # applied_defaults lacks implementation_plan
            "plan_tasks",
            stored_artifacts=stored,
            profile=_profile_without_builder(),
        )

        executor._artifact_vault.retrieve.assert_not_awaited()
        status_calls = mock_registry.update_run_status.call_args_list
        assert status_calls[-1] == ((("run_001", RunStatus.RUNNING),))

    async def test_unreadable_plan_defers_to_dispatch_net(
        self, executor, mock_registry, mock_event_bus, cycle
    ):
        """A plan artifact that fails to parse must NOT fail the gate — the
        check only adds earlier rejections; malformed plans stay the
        dispatch-time net's problem (same graceful path as _load_plan_for_run)."""
        mock_registry.get_run.return_value = _run_with_gate_decision(GateDecisionValue.APPROVED)
        stored = [_plan_artifact(executor._artifact_vault, "art_plan", "not: [valid, plan yaml")]

        await executor._handle_gate(
            "run_001",
            _plan_cycle(cycle),
            "plan_tasks",
            stored_artifacts=stored,
            profile=_profile_without_builder(),
        )

        status_calls = mock_registry.update_run_status.call_args_list
        assert status_calls[-1] == ((("run_001", RunStatus.RUNNING),))

    async def test_gate_without_threaded_context_behaves_as_before(
        self, executor, mock_registry, mock_event_bus, cycle
    ):
        """Callers that don't thread stored_artifacts/profile (defaults None)
        get pre-#295 behavior — the check never runs."""
        mock_registry.get_run.return_value = _run_with_gate_decision(GateDecisionValue.APPROVED)

        await executor._handle_gate("run_001", _plan_cycle(cycle), "plan_tasks")

        status_calls = mock_registry.update_run_status.call_args_list
        assert status_calls[-1] == ((("run_001", RunStatus.RUNNING),))
