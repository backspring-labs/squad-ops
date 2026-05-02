"""Tests for SIP-0079 correction protocol in DistributedFlowExecutor.

Covers all 4 correction paths (continue, patch, rewind, abort),
plan delta storage, max_correction_attempts, correction task checkpointing,
and CORRECTION_INITIATED/DECIDED/COMPLETED event emission.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from squadops.comms.queue_message import QueueMessage
from squadops.cycles.models import (
    AgentProfileEntry,
    Cycle,
    Run,
    RunStatus,
    SquadProfile,
    TaskFlowPolicy,
)
from squadops.cycles.task_outcome import TaskOutcome
from squadops.events.types import EventType
from squadops.tasks.models import TaskResult

NOW = datetime(2026, 1, 15, 12, 0, 0, tzinfo=UTC)

pytestmark = [pytest.mark.domain_orchestration]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_result_message(
    task_id: str,
    status: str = "SUCCEEDED",
    outputs: dict | None = None,
    error: str | None = None,
    queue_name: str = "cycle_results_run_001",
) -> QueueMessage:
    result = TaskResult(
        task_id=task_id,
        status=status,
        outputs=outputs,
        error=error,
    )
    payload = json.dumps(
        {
            "action": "comms.task.result",
            "metadata": {"correlation_id": "corr"},
            "payload": result.to_dict(),
        }
    )
    return QueueMessage(
        message_id=f"msg_{task_id}",
        queue_name=queue_name,
        payload=payload,
        receipt_handle=f"rh_{task_id}",
        attributes={},
    )


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_registry():
    mock = AsyncMock()
    mock.get_run.return_value = Run(
        run_id="run_001",
        cycle_id="cyc_001",
        run_number=1,
        status="queued",
        initiated_by="api",
        resolved_config_hash="hash",
    )
    mock.update_run_status.side_effect = lambda run_id, status: Run(
        run_id=run_id,
        cycle_id="cyc_001",
        run_number=1,
        status=status.value,
        initiated_by="api",
        resolved_config_hash="hash",
    )
    mock.append_artifact_refs.return_value = mock.get_run.return_value
    mock.get_latest_checkpoint.return_value = None
    return mock


@pytest.fixture
def mock_vault():
    mock = AsyncMock()
    mock.store.side_effect = lambda ref, content: ref
    return mock


@pytest.fixture
def mock_queue():
    mock = AsyncMock()
    mock.publish.return_value = None
    mock.ack.return_value = None
    mock.invalidate_queue.return_value = None
    mock.consume.return_value = []

    async def _consume_blocking(queue_name, timeout, max_messages=1):
        return await mock.consume(queue_name, max_messages=max_messages)

    mock.consume_blocking.side_effect = _consume_blocking
    return mock


@pytest.fixture
def mock_squad_profile():
    mock = AsyncMock()
    profile = SquadProfile(
        profile_id="full-squad",
        name="Full Squad",
        description="All",
        version=1,
        agents=(
            AgentProfileEntry(agent_id="nat", role="strat", model="gpt-4", enabled=True),
            AgentProfileEntry(agent_id="neo", role="dev", model="gpt-4", enabled=True),
            AgentProfileEntry(agent_id="eve", role="qa", model="gpt-4", enabled=True),
            AgentProfileEntry(
                agent_id="data-agent",
                role="data",
                model="gpt-4",
                enabled=True,
            ),
            AgentProfileEntry(agent_id="max", role="lead", model="gpt-4", enabled=True),
        ),
        created_at=NOW,
    )
    mock.resolve_snapshot.return_value = (profile, "sha256:abc")
    return mock


@pytest.fixture
def mock_event_bus():
    return MagicMock()


@pytest.fixture
def cycle():
    return Cycle(
        cycle_id="cyc_001",
        project_id="hello_squad",
        created_at=NOW,
        created_by="system",
        prd_ref="prd_ref_123",
        squad_profile_id="full-squad",
        squad_profile_snapshot_ref="sha256:abc",
        task_flow_policy=TaskFlowPolicy(mode="sequential"),
        build_strategy="fresh",
    )


@pytest.fixture
def run():
    return Run(
        run_id="run_001",
        cycle_id="cyc_001",
        run_number=1,
        status="queued",
        initiated_by="api",
        resolved_config_hash="hash",
    )


@pytest.fixture
def executor(
    mock_registry,
    mock_vault,
    mock_queue,
    mock_squad_profile,
    mock_event_bus,
    cycle,
    run,
):
    from adapters.cycles.distributed_flow_executor import DistributedFlowExecutor

    mock_registry.get_cycle.return_value = cycle
    mock_registry.get_run.return_value = run
    ex = DistributedFlowExecutor(
        cycle_registry=mock_registry,
        artifact_vault=mock_vault,
        queue=mock_queue,
        squad_profile=mock_squad_profile,
        task_timeout=5.0,
    )
    ex._cycle_event_bus = mock_event_bus
    return ex


def _build_scripted_consume(mock_queue, script):
    """Build consume side_effect from a list of (status, outputs, error) tuples.

    Each publish gets the next response from the script. After the script
    is exhausted, returns SUCCEEDED with default outputs.
    """
    idx = {"n": 0}

    async def consume_side_effect(queue_name, max_messages=1):
        if not queue_name.startswith("cycle_results_"):
            return []
        last_call = mock_queue.publish.call_args
        if not last_call:
            return []
        msg_data = json.loads(last_call.args[1])
        task_id = msg_data["payload"]["task_id"]

        i = idx["n"]
        idx["n"] += 1

        if i < len(script):
            status, outputs, error = script[i]
        else:
            status, outputs, error = (
                "SUCCEEDED",
                {"summary": "ok", "role": "strat"},
                None,
            )
        return [
            _make_result_message(
                task_id=task_id,
                status=status,
                outputs=outputs,
                error=error,
                queue_name=queue_name,
            )
        ]

    return consume_side_effect


# ---------------------------------------------------------------------------
# Correction protocol: continue path
# ---------------------------------------------------------------------------


class TestCorrectionContinue:
    """Correction path 'continue': reset failures, proceed to next task."""

    async def test_continue_path_allows_remaining_tasks(
        self, executor, mock_queue, mock_registry, mock_event_bus
    ):
        """Semantic failure -> correction decides 'continue' -> remaining tasks run."""
        semantic_outputs = {
            "outcome_class": TaskOutcome.SEMANTIC_FAILURE,
            "role": "strat",
        }
        correction_decision = {
            "summary": "continue",
            "role": "lead",
            "correction_path": "continue",
            "decision_rationale": "Non-critical failure",
            "affected_task_types": [],
            "classification": "execution",
            "analysis_summary": "Transient issue",
        }
        script = [
            # Task 1: semantic failure
            ("FAILED", semantic_outputs, "bad output"),
            # Correction: analyze_failure succeeds
            (
                "SUCCEEDED",
                {
                    "classification": "execution",
                    "analysis_summary": "ok",
                    "role": "data",
                },
                None,
            ),
            # Correction: correction_decision succeeds with "continue"
            ("SUCCEEDED", correction_decision, None),
            # Tasks 2-5: succeed
            ("SUCCEEDED", {"summary": "ok", "role": "dev"}, None),
            ("SUCCEEDED", {"summary": "ok", "role": "dev"}, None),
            ("SUCCEEDED", {"summary": "ok", "role": "qa"}, None),
            ("SUCCEEDED", {"summary": "ok", "role": "data"}, None),
        ]
        mock_queue.consume.side_effect = _build_scripted_consume(mock_queue, script)

        with patch(
            "adapters.cycles.distributed_flow_executor.asyncio.sleep",
            new_callable=AsyncMock,
        ):
            await executor.execute_run(cycle_id="cyc_001", run_id="run_001")

        # 1 (failed) + 2 (correction) + 4 (remaining) = 7
        assert mock_queue.publish.call_count == 7

        status_calls = mock_registry.update_run_status.call_args_list
        terminal_statuses = [c.args[1] for c in status_calls]
        assert RunStatus.COMPLETED in terminal_statuses


# ---------------------------------------------------------------------------
# Correction protocol: patch path
# ---------------------------------------------------------------------------


class TestCorrectionPatch:
    """Correction path 'patch': dispatch repair tasks, then proceed."""

    async def test_patch_dispatches_repair_tasks(
        self, executor, mock_queue, mock_registry, mock_event_bus
    ):
        """Patch path -> repair tasks dispatched, then remaining tasks proceed."""
        semantic_outputs = {
            "outcome_class": TaskOutcome.SEMANTIC_FAILURE,
            "role": "strat",
        }
        correction_decision = {
            "summary": "patch",
            "role": "lead",
            "correction_path": "patch",
            "decision_rationale": "Fix is localized",
            "affected_task_types": ["development.develop"],
            "classification": "work_product",
            "analysis_summary": "Output quality issue",
        }
        script = [
            # Task 1: semantic failure
            ("FAILED", semantic_outputs, "bad output"),
            # Correction: analyze_failure
            (
                "SUCCEEDED",
                {
                    "classification": "work_product",
                    "analysis_summary": "quality",
                    "role": "data",
                },
                None,
            ),
            # Correction: correction_decision -> patch
            ("SUCCEEDED", correction_decision, None),
            # Repair: development.repair
            ("SUCCEEDED", {"summary": "repaired", "role": "dev"}, None),
            # Repair: qa.validate_repair
            ("SUCCEEDED", {"summary": "validated", "role": "qa"}, None),
            # Tasks 2-5: succeed
            ("SUCCEEDED", {"summary": "ok", "role": "dev"}, None),
            ("SUCCEEDED", {"summary": "ok", "role": "dev"}, None),
            ("SUCCEEDED", {"summary": "ok", "role": "qa"}, None),
            ("SUCCEEDED", {"summary": "ok", "role": "data"}, None),
        ]
        mock_queue.consume.side_effect = _build_scripted_consume(mock_queue, script)

        with patch(
            "adapters.cycles.distributed_flow_executor.asyncio.sleep",
            new_callable=AsyncMock,
        ):
            await executor.execute_run(cycle_id="cyc_001", run_id="run_001")

        # 1 (failed) + 2 (correction) + 2 (repair) + 4 (remaining) = 9
        assert mock_queue.publish.call_count == 9

        status_calls = mock_registry.update_run_status.call_args_list
        terminal_statuses = [c.args[1] for c in status_calls]
        assert RunStatus.COMPLETED in terminal_statuses


# ---------------------------------------------------------------------------
# Correction protocol: abort and rewind paths
# ---------------------------------------------------------------------------


class TestCorrectionTerminalPaths:
    """Abort and rewind paths both terminate the run as FAILED."""

    @pytest.mark.parametrize(
        "correction_path,rationale",
        [
            ("abort", "Unrecoverable"),
            ("rewind", "Need to go back"),
        ],
    )
    async def test_terminal_path_fails_run(
        self,
        executor,
        mock_queue,
        mock_registry,
        mock_event_bus,
        correction_path,
        rationale,
    ):
        """Both abort and rewind -> run transitions to FAILED."""
        semantic_outputs = {
            "outcome_class": TaskOutcome.SEMANTIC_FAILURE,
            "role": "strat",
        }
        correction_decision = {
            "summary": correction_path,
            "role": "lead",
            "correction_path": correction_path,
            "decision_rationale": rationale,
            "affected_task_types": [],
            "classification": "execution",
            "analysis_summary": "Issue found",
        }
        script = [
            ("FAILED", semantic_outputs, "bad"),
            (
                "SUCCEEDED",
                {
                    "classification": "execution",
                    "analysis_summary": "issue",
                    "role": "data",
                },
                None,
            ),
            ("SUCCEEDED", correction_decision, None),
        ]
        mock_queue.consume.side_effect = _build_scripted_consume(mock_queue, script)

        with patch(
            "adapters.cycles.distributed_flow_executor.asyncio.sleep",
            new_callable=AsyncMock,
        ):
            await executor.execute_run(cycle_id="cyc_001", run_id="run_001")

        # 1 (task) + 2 (correction) = 3
        assert mock_queue.publish.call_count == 3

        status_calls = mock_registry.update_run_status.call_args_list
        terminal_statuses = [c.args[1] for c in status_calls]
        assert RunStatus.FAILED in terminal_statuses


# ---------------------------------------------------------------------------
# max_correction_attempts
# ---------------------------------------------------------------------------


class TestMaxCorrectionAttempts:
    """max_correction_attempts enforced."""

    async def test_max_corrections_exhausted(self, executor, mock_queue, mock_registry, cycle):
        import dataclasses

        cycle_1 = dataclasses.replace(cycle, applied_defaults={"max_correction_attempts": 1})
        mock_registry.get_cycle.return_value = cycle_1

        semantic_outputs = {
            "outcome_class": TaskOutcome.SEMANTIC_FAILURE,
            "role": "strat",
        }
        correction_decision = {
            "summary": "continue",
            "role": "lead",
            "correction_path": "continue",
            "decision_rationale": "Try again",
            "affected_task_types": [],
            "classification": "execution",
            "analysis_summary": "transient",
        }
        semantic_outputs_2 = {
            "outcome_class": TaskOutcome.SEMANTIC_FAILURE,
            "role": "dev",
        }
        script = [
            # Task 1: semantic failure
            ("FAILED", semantic_outputs, "bad"),
            # Correction 1: analyze + decide -> continue
            (
                "SUCCEEDED",
                {
                    "classification": "execution",
                    "analysis_summary": "ok",
                    "role": "data",
                },
                None,
            ),
            ("SUCCEEDED", correction_decision, None),
            # Task 2: also semantic failure
            ("FAILED", semantic_outputs_2, "bad again"),
            # max_correction_attempts=1 exhausted -> abort
        ]
        mock_queue.consume.side_effect = _build_scripted_consume(mock_queue, script)

        with patch(
            "adapters.cycles.distributed_flow_executor.asyncio.sleep",
            new_callable=AsyncMock,
        ):
            await executor.execute_run(cycle_id="cyc_001", run_id="run_001")

        # 1 (fail) + 2 (correction) + 1 (task 2 fail) = 4
        assert mock_queue.publish.call_count == 4

        status_calls = mock_registry.update_run_status.call_args_list
        terminal_statuses = [c.args[1] for c in status_calls]
        assert RunStatus.FAILED in terminal_statuses


# ---------------------------------------------------------------------------
# Plan delta stored as artifact
# ---------------------------------------------------------------------------


class TestPlanDelta:
    """Plan delta stored as artifact after correction."""

    async def test_plan_delta_stored(
        self, executor, mock_queue, mock_registry, mock_vault, mock_event_bus
    ):
        """Correction protocol stores a plan_delta artifact."""
        semantic_outputs = {
            "outcome_class": TaskOutcome.SEMANTIC_FAILURE,
            "role": "strat",
        }
        correction_decision = {
            "summary": "abort",
            "role": "lead",
            "correction_path": "abort",
            "decision_rationale": "Cannot fix",
            "affected_task_types": [],
            "classification": "execution",
            "analysis_summary": "Something broke",
        }
        script = [
            ("FAILED", semantic_outputs, "bad"),
            (
                "SUCCEEDED",
                {
                    "classification": "execution",
                    "analysis_summary": "broke",
                    "role": "data",
                },
                None,
            ),
            ("SUCCEEDED", correction_decision, None),
        ]
        mock_queue.consume.side_effect = _build_scripted_consume(mock_queue, script)

        with patch(
            "adapters.cycles.distributed_flow_executor.asyncio.sleep",
            new_callable=AsyncMock,
        ):
            await executor.execute_run(cycle_id="cyc_001", run_id="run_001")

        # Check that a plan_delta artifact was stored
        store_calls = mock_vault.store.call_args_list
        delta_stores = [c for c in store_calls if c.args[0].artifact_type == "plan_delta"]
        assert len(delta_stores) == 1

        delta_ref = delta_stores[0].args[0]
        assert delta_ref.artifact_type == "plan_delta"
        assert "plan_delta" in delta_ref.filename


# ---------------------------------------------------------------------------
# Correction tasks checkpoint on success
# ---------------------------------------------------------------------------


class TestCorrectionCheckpoints:
    """Correction tasks checkpoint on success."""

    async def test_successful_correction_tasks_checkpointed(
        self, executor, mock_queue, mock_registry, mock_event_bus
    ):
        """Successful correction tasks trigger checkpoint saves."""
        semantic_outputs = {
            "outcome_class": TaskOutcome.SEMANTIC_FAILURE,
            "role": "strat",
        }
        correction_decision = {
            "summary": "abort",
            "role": "lead",
            "correction_path": "abort",
            "decision_rationale": "Done",
            "affected_task_types": [],
            "classification": "execution",
            "analysis_summary": "N/A",
        }
        script = [
            ("FAILED", semantic_outputs, "bad"),
            # analyze_failure succeeds -> checkpoint
            (
                "SUCCEEDED",
                {
                    "classification": "execution",
                    "analysis_summary": "ok",
                    "role": "data",
                },
                None,
            ),
            # correction_decision succeeds -> checkpoint
            ("SUCCEEDED", correction_decision, None),
        ]
        mock_queue.consume.side_effect = _build_scripted_consume(mock_queue, script)

        with patch(
            "adapters.cycles.distributed_flow_executor.asyncio.sleep",
            new_callable=AsyncMock,
        ):
            await executor.execute_run(cycle_id="cyc_001", run_id="run_001")

        # 2 successful correction tasks -> 2 checkpoint saves
        assert mock_registry.save_checkpoint.call_count == 2

    async def test_failed_correction_task_not_checkpointed(
        self, executor, mock_queue, mock_registry, mock_event_bus
    ):
        """Failed correction tasks do NOT trigger checkpoint saves."""
        semantic_outputs = {
            "outcome_class": TaskOutcome.SEMANTIC_FAILURE,
            "role": "strat",
        }
        script = [
            ("FAILED", semantic_outputs, "bad"),
            # analyze_failure fails
            ("FAILED", None, "corr fail"),
            # correction_decision fails
            ("FAILED", None, "corr fail"),
        ]
        mock_queue.consume.side_effect = _build_scripted_consume(mock_queue, script)

        with patch(
            "adapters.cycles.distributed_flow_executor.asyncio.sleep",
            new_callable=AsyncMock,
        ):
            await executor.execute_run(cycle_id="cyc_001", run_id="run_001")

        # 0 successful tasks -> 0 checkpoints
        assert mock_registry.save_checkpoint.call_count == 0


# ---------------------------------------------------------------------------
# Correction events
# ---------------------------------------------------------------------------


class TestCorrectionEvents:
    """CORRECTION_INITIATED/DECIDED/COMPLETED events emitted."""

    async def test_correction_events_emitted_in_order(
        self, executor, mock_queue, mock_registry, mock_event_bus
    ):
        """All 3 correction events emitted in INITIATED < DECIDED < COMPLETED order."""
        semantic_outputs = {
            "outcome_class": TaskOutcome.SEMANTIC_FAILURE,
            "role": "strat",
        }
        correction_decision = {
            "summary": "abort",
            "role": "lead",
            "correction_path": "abort",
            "decision_rationale": "Done",
            "affected_task_types": [],
            "classification": "execution",
            "analysis_summary": "N/A",
        }
        script = [
            ("FAILED", semantic_outputs, "bad"),
            (
                "SUCCEEDED",
                {
                    "classification": "execution",
                    "analysis_summary": "ok",
                    "role": "data",
                },
                None,
            ),
            ("SUCCEEDED", correction_decision, None),
        ]
        mock_queue.consume.side_effect = _build_scripted_consume(mock_queue, script)

        with patch(
            "adapters.cycles.distributed_flow_executor.asyncio.sleep",
            new_callable=AsyncMock,
        ):
            await executor.execute_run(cycle_id="cyc_001", run_id="run_001")

        emit_calls = mock_event_bus.emit.call_args_list
        event_types = [c.args[0] for c in emit_calls]

        assert EventType.CORRECTION_INITIATED in event_types
        assert EventType.CORRECTION_DECIDED in event_types
        assert EventType.CORRECTION_COMPLETED in event_types

        # Verify order: INITIATED before DECIDED before COMPLETED
        init_idx = event_types.index(EventType.CORRECTION_INITIATED)
        decided_idx = event_types.index(EventType.CORRECTION_DECIDED)
        completed_idx = event_types.index(EventType.CORRECTION_COMPLETED)
        assert init_idx < decided_idx < completed_idx

    async def test_correction_decided_carries_path(
        self, executor, mock_queue, mock_registry, mock_event_bus
    ):
        """CORRECTION_DECIDED event payload contains correction_path."""
        semantic_outputs = {
            "outcome_class": TaskOutcome.SEMANTIC_FAILURE,
            "role": "strat",
        }
        correction_decision = {
            "summary": "continue",
            "role": "lead",
            "correction_path": "continue",
            "decision_rationale": "OK",
            "affected_task_types": [],
            "classification": "execution",
            "analysis_summary": "Fine",
        }
        script = [
            ("FAILED", semantic_outputs, "bad"),
            (
                "SUCCEEDED",
                {
                    "classification": "execution",
                    "analysis_summary": "ok",
                    "role": "data",
                },
                None,
            ),
            ("SUCCEEDED", correction_decision, None),
            # Remaining 4 tasks succeed
            ("SUCCEEDED", {"summary": "ok", "role": "dev"}, None),
            ("SUCCEEDED", {"summary": "ok", "role": "dev"}, None),
            ("SUCCEEDED", {"summary": "ok", "role": "qa"}, None),
            ("SUCCEEDED", {"summary": "ok", "role": "data"}, None),
        ]
        mock_queue.consume.side_effect = _build_scripted_consume(mock_queue, script)

        with patch(
            "adapters.cycles.distributed_flow_executor.asyncio.sleep",
            new_callable=AsyncMock,
        ):
            await executor.execute_run(cycle_id="cyc_001", run_id="run_001")

        # Find CORRECTION_DECIDED emit
        decided_calls = [
            c
            for c in mock_event_bus.emit.call_args_list
            if c.args[0] == EventType.CORRECTION_DECIDED
        ]
        assert len(decided_calls) == 1
        payload = decided_calls[0].kwargs.get("payload", {})
        assert payload["correction_path"] == "continue"
