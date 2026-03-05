"""Tests for SIP-0079 executor checkpoint, resume, and time budget.

Covers:
- Checkpoint saved after each successful task
- Checkpoint NOT saved after failed task
- Resume: skip completed tasks from checkpoint
- Resume: prior_outputs and artifact_refs restored
- CHECKPOINT_CREATED / CHECKPOINT_RESTORED events emitted
- Time budget enforcement
- RUN_RESUMED event emitted on resume
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from squadops.comms.queue_message import QueueMessage
from squadops.cycles.checkpoint import RunCheckpoint
from squadops.cycles.models import (
    AgentProfileEntry,
    ArtifactRef,
    Cycle,
    Run,
    RunStatus,
    SquadProfile,
    TaskFlowPolicy,
    WorkloadType,
)
from squadops.events.types import EventType
from squadops.tasks.models import TaskResult

NOW = datetime(2026, 3, 1, 12, 0, 0, tzinfo=UTC)

pytestmark = [pytest.mark.domain_orchestration]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_result_message(
    task_id: str,
    status: str = "SUCCEEDED",
    outputs: dict | None = None,
    error: str | None = None,
    queue_name: str = "cycle_results_run_impl",
) -> QueueMessage:
    result = TaskResult(task_id=task_id, status=status, outputs=outputs, error=error)
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


def _make_queue_side_effects(mock_queue, queue_name="cycle_results_run_impl"):
    """Build consume side_effect that returns matching results."""

    async def consume_side_effect(qn, max_messages=1):
        if not qn.startswith("cycle_results_"):
            return []
        last_call = mock_queue.publish.call_args
        if last_call:
            msg_data = json.loads(last_call.args[1])
            task_id = msg_data["payload"]["task_id"]
            return [
                _make_result_message(
                    task_id=task_id,
                    outputs={"summary": "ok", "artifacts": []},
                    queue_name=qn,
                )
            ]
        return []

    return consume_side_effect


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_registry():
    mock = AsyncMock()
    mock.get_run.return_value = Run(
        run_id="run_impl",
        cycle_id="cyc_impl",
        run_number=1,
        status="queued",
        initiated_by="api",
        resolved_config_hash="hash",
        workload_type=WorkloadType.IMPLEMENTATION,
    )
    mock.update_run_status.side_effect = lambda run_id, status: Run(
        run_id=run_id,
        cycle_id="cyc_impl",
        run_number=1,
        status=status.value,
        initiated_by="api",
        resolved_config_hash="hash",
        workload_type=WorkloadType.IMPLEMENTATION,
    )
    mock.append_artifact_refs.return_value = mock.get_run.return_value
    mock.get_latest_checkpoint.return_value = None
    mock.save_checkpoint.return_value = None
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
    mock.consume.return_value = []
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
                agent_id="data-agent", role="data", model="gpt-4", enabled=True
            ),
            AgentProfileEntry(agent_id="max", role="lead", model="gpt-4", enabled=True),
        ),
        created_at=NOW,
    )
    mock.resolve_snapshot.return_value = (profile, "sha256:abc")
    return mock


@pytest.fixture
def impl_cycle():
    return Cycle(
        cycle_id="cyc_impl",
        project_id="proj_001",
        created_at=NOW,
        created_by="system",
        prd_ref="Build a CLI tool",
        squad_profile_id="full-squad",
        squad_profile_snapshot_ref="sha256:abc",
        task_flow_policy=TaskFlowPolicy(mode="sequential"),
        build_strategy="fresh",
        applied_defaults={},
        execution_overrides={},
    )


@pytest.fixture
def mock_event_bus():
    return MagicMock()


@pytest.fixture
def executor(mock_registry, mock_vault, mock_queue, mock_squad_profile, impl_cycle, mock_event_bus):
    from adapters.cycles.distributed_flow_executor import DistributedFlowExecutor

    mock_registry.get_cycle.return_value = impl_cycle
    return DistributedFlowExecutor(
        cycle_registry=mock_registry,
        artifact_vault=mock_vault,
        queue=mock_queue,
        squad_profile=mock_squad_profile,
        task_timeout=5.0,
        event_bus=mock_event_bus,
    )


# ---------------------------------------------------------------------------
# Checkpoint on success
# ---------------------------------------------------------------------------


class TestCheckpointOnSuccess:
    """Checkpoint saved after each successful task."""

    async def test_checkpoint_saved_per_task(
        self, executor, mock_registry, mock_queue
    ) -> None:
        """save_checkpoint called once per successful task (3 for implementation)."""
        mock_queue.consume.side_effect = _make_queue_side_effects(mock_queue)

        with patch(
            "adapters.cycles.distributed_flow_executor.asyncio.sleep",
            new_callable=AsyncMock,
        ):
            await executor.execute_run(cycle_id="cyc_impl", run_id="run_impl")

        assert mock_registry.save_checkpoint.call_count == 3

    async def test_checkpoint_indices_increment(
        self, executor, mock_registry, mock_queue
    ) -> None:
        """Each checkpoint has sequential checkpoint_index."""
        mock_queue.consume.side_effect = _make_queue_side_effects(mock_queue)

        with patch(
            "adapters.cycles.distributed_flow_executor.asyncio.sleep",
            new_callable=AsyncMock,
        ):
            await executor.execute_run(cycle_id="cyc_impl", run_id="run_impl")

        calls = mock_registry.save_checkpoint.call_args_list
        indices = [c.args[0].checkpoint_index for c in calls]
        assert indices == [1, 2, 3]

    async def test_checkpoint_completed_task_ids_grow(
        self, executor, mock_registry, mock_queue
    ) -> None:
        """Each checkpoint records all completed tasks so far."""
        mock_queue.consume.side_effect = _make_queue_side_effects(mock_queue)

        with patch(
            "adapters.cycles.distributed_flow_executor.asyncio.sleep",
            new_callable=AsyncMock,
        ):
            await executor.execute_run(cycle_id="cyc_impl", run_id="run_impl")

        calls = mock_registry.save_checkpoint.call_args_list
        counts = [len(c.args[0].completed_task_ids) for c in calls]
        assert counts == [1, 2, 3]

    async def test_checkpoint_not_saved_after_failure(
        self, executor, mock_registry, mock_queue
    ) -> None:
        """No checkpoint saved when a task fails."""

        async def fail_second(qn, max_messages=1):
            if not qn.startswith("cycle_results_"):
                return []
            last_call = mock_queue.publish.call_args
            if last_call:
                msg_data = json.loads(last_call.args[1])
                task_id = msg_data["payload"]["task_id"]
                # First task succeeds, second fails
                if mock_queue.publish.call_count <= 1:
                    return [
                        _make_result_message(
                            task_id=task_id,
                            outputs={"summary": "ok", "artifacts": []},
                            queue_name=qn,
                        )
                    ]
                else:
                    return [
                        _make_result_message(
                            task_id=task_id,
                            status="FAILED",
                            error="build error",
                            queue_name=qn,
                        )
                    ]
            return []

        mock_queue.consume.side_effect = fail_second

        with patch(
            "adapters.cycles.distributed_flow_executor.asyncio.sleep",
            new_callable=AsyncMock,
        ):
            await executor.execute_run(cycle_id="cyc_impl", run_id="run_impl")

        # Only 1 checkpoint (first task succeeded), none for the failure
        assert mock_registry.save_checkpoint.call_count == 1


# ---------------------------------------------------------------------------
# Checkpoint events
# ---------------------------------------------------------------------------


class TestCheckpointEvents:
    """CHECKPOINT_CREATED event emitted after each save."""

    async def test_checkpoint_created_event(
        self, executor, mock_event_bus, mock_queue
    ) -> None:
        mock_queue.consume.side_effect = _make_queue_side_effects(mock_queue)

        with patch(
            "adapters.cycles.distributed_flow_executor.asyncio.sleep",
            new_callable=AsyncMock,
        ):
            await executor.execute_run(cycle_id="cyc_impl", run_id="run_impl")

        checkpoint_events = [
            c
            for c in mock_event_bus.emit.call_args_list
            if c.args[0] == EventType.CHECKPOINT_CREATED
        ]
        assert len(checkpoint_events) == 3

    async def test_checkpoint_created_payload(
        self, executor, mock_event_bus, mock_queue
    ) -> None:
        mock_queue.consume.side_effect = _make_queue_side_effects(mock_queue)

        with patch(
            "adapters.cycles.distributed_flow_executor.asyncio.sleep",
            new_callable=AsyncMock,
        ):
            await executor.execute_run(cycle_id="cyc_impl", run_id="run_impl")

        checkpoint_events = [
            c
            for c in mock_event_bus.emit.call_args_list
            if c.args[0] == EventType.CHECKPOINT_CREATED
        ]
        first_payload = checkpoint_events[0].kwargs.get("payload") or checkpoint_events[0][1].get(
            "payload", {}
        )
        assert first_payload["checkpoint_index"] == 1


# ---------------------------------------------------------------------------
# Resume from checkpoint
# ---------------------------------------------------------------------------


class TestResumeFromCheckpoint:
    """Resume skips completed tasks from checkpoint."""

    async def test_skip_completed_tasks(
        self, executor, mock_registry, mock_queue, mock_event_bus
    ) -> None:
        """When checkpoint has 1 completed task, only 2 are dispatched."""
        # Set up checkpoint with first task completed
        mock_registry.get_latest_checkpoint.return_value = RunCheckpoint(
            run_id="run_impl",
            checkpoint_index=1,
            completed_task_ids=("task-run_impl-000-governance.establish_contract",),
            prior_outputs={"lead": {"summary": "contract established"}},
            artifact_refs=(),
            plan_delta_refs=(),
            created_at=NOW,
        )
        mock_queue.consume.side_effect = _make_queue_side_effects(mock_queue)

        with patch(
            "adapters.cycles.distributed_flow_executor.asyncio.sleep",
            new_callable=AsyncMock,
        ):
            await executor.execute_run(cycle_id="cyc_impl", run_id="run_impl")

        # Only 2 tasks dispatched (skipped the first)
        assert mock_queue.publish.call_count == 2

    async def test_prior_outputs_restored(
        self, executor, mock_registry, mock_queue
    ) -> None:
        """Prior outputs from checkpoint are available to subsequent tasks."""
        prior = {"lead": {"contract": "established"}}
        mock_registry.get_latest_checkpoint.return_value = RunCheckpoint(
            run_id="run_impl",
            checkpoint_index=1,
            completed_task_ids=("task-run_impl-000-governance.establish_contract",),
            prior_outputs=prior,
            artifact_refs=(),
            plan_delta_refs=(),
            created_at=NOW,
        )
        mock_queue.consume.side_effect = _make_queue_side_effects(mock_queue)

        with patch(
            "adapters.cycles.distributed_flow_executor.asyncio.sleep",
            new_callable=AsyncMock,
        ):
            await executor.execute_run(cycle_id="cyc_impl", run_id="run_impl")

        # Verify the dispatched task includes prior_outputs from checkpoint
        first_publish = mock_queue.publish.call_args_list[0]
        msg_data = json.loads(first_publish.args[1])
        task_inputs = msg_data["payload"]["inputs"]
        assert task_inputs["prior_outputs"]["lead"]["contract"] == "established"

    async def test_artifact_refs_restored(
        self, executor, mock_registry, mock_vault, mock_queue
    ) -> None:
        """Artifact refs from checkpoint are restored."""
        art_ref = ArtifactRef(
            artifact_id="art_001",
            project_id="proj_001",
            filename="contract.md",
            media_type="text/markdown",
            artifact_type="document",
            content_hash="sha256:abc",
            size_bytes=100,
            created_at=NOW,
        )
        mock_vault.retrieve.return_value = (art_ref, b"# Contract")
        mock_registry.get_latest_checkpoint.return_value = RunCheckpoint(
            run_id="run_impl",
            checkpoint_index=1,
            completed_task_ids=("task-run_impl-000-governance.establish_contract",),
            prior_outputs={},
            artifact_refs=("art_001",),
            plan_delta_refs=(),
            created_at=NOW,
        )
        mock_queue.consume.side_effect = _make_queue_side_effects(mock_queue)

        with patch(
            "adapters.cycles.distributed_flow_executor.asyncio.sleep",
            new_callable=AsyncMock,
        ):
            await executor.execute_run(cycle_id="cyc_impl", run_id="run_impl")

        # Verify artifact_refs in dispatched task inputs include restored ref
        first_publish = mock_queue.publish.call_args_list[0]
        msg_data = json.loads(first_publish.args[1])
        task_inputs = msg_data["payload"]["inputs"]
        assert "art_001" in task_inputs["artifact_refs"]

    async def test_checkpoint_restored_event(
        self, executor, mock_registry, mock_queue, mock_event_bus
    ) -> None:
        """CHECKPOINT_RESTORED event emitted on resume."""
        mock_registry.get_latest_checkpoint.return_value = RunCheckpoint(
            run_id="run_impl",
            checkpoint_index=2,
            completed_task_ids=(
                "task-run_impl-000-governance.establish_contract",
                "task-run_impl-001-development.develop",
            ),
            prior_outputs={},
            artifact_refs=(),
            plan_delta_refs=(),
            created_at=NOW,
        )
        mock_queue.consume.side_effect = _make_queue_side_effects(mock_queue)

        with patch(
            "adapters.cycles.distributed_flow_executor.asyncio.sleep",
            new_callable=AsyncMock,
        ):
            await executor.execute_run(cycle_id="cyc_impl", run_id="run_impl")

        restored_events = [
            c
            for c in mock_event_bus.emit.call_args_list
            if c.args[0] == EventType.CHECKPOINT_RESTORED
        ]
        # Two emissions: one in execute_run, one in _execute_sequential
        assert len(restored_events) >= 1

    async def test_run_resumed_event_on_checkpoint_resume(
        self, executor, mock_registry, mock_queue, mock_event_bus
    ) -> None:
        """RUN_RESUMED event (not RUN_STARTED) emitted when checkpoint exists."""
        mock_registry.get_latest_checkpoint.return_value = RunCheckpoint(
            run_id="run_impl",
            checkpoint_index=1,
            completed_task_ids=("task-run_impl-000-governance.establish_contract",),
            prior_outputs={},
            artifact_refs=(),
            plan_delta_refs=(),
            created_at=NOW,
        )
        mock_queue.consume.side_effect = _make_queue_side_effects(mock_queue)

        with patch(
            "adapters.cycles.distributed_flow_executor.asyncio.sleep",
            new_callable=AsyncMock,
        ):
            await executor.execute_run(cycle_id="cyc_impl", run_id="run_impl")

        event_types = [c.args[0] for c in mock_event_bus.emit.call_args_list]
        assert EventType.RUN_RESUMED in event_types
        assert EventType.RUN_STARTED not in event_types

    async def test_fresh_run_emits_started_not_resumed(
        self, executor, mock_registry, mock_queue, mock_event_bus
    ) -> None:
        """Fresh run (no checkpoint) emits RUN_STARTED, not RUN_RESUMED."""
        mock_queue.consume.side_effect = _make_queue_side_effects(mock_queue)

        with patch(
            "adapters.cycles.distributed_flow_executor.asyncio.sleep",
            new_callable=AsyncMock,
        ):
            await executor.execute_run(cycle_id="cyc_impl", run_id="run_impl")

        event_types = [c.args[0] for c in mock_event_bus.emit.call_args_list]
        assert EventType.RUN_STARTED in event_types
        assert EventType.RUN_RESUMED not in event_types


# ---------------------------------------------------------------------------
# Time budget enforcement
# ---------------------------------------------------------------------------


class TestTimeBudget:
    """Time budget enforcement halts run when exhausted."""

    async def test_time_budget_exhausted(
        self, executor, mock_registry, mock_queue, impl_cycle, mock_event_bus
    ) -> None:
        """Run fails when time budget is exhausted."""
        import dataclasses

        budget_cycle = dataclasses.replace(
            impl_cycle, applied_defaults={"time_budget_seconds": 0}
        )
        mock_registry.get_cycle.return_value = budget_cycle
        mock_queue.consume.side_effect = _make_queue_side_effects(mock_queue)

        with patch(
            "adapters.cycles.distributed_flow_executor.asyncio.sleep",
            new_callable=AsyncMock,
        ):
            await executor.execute_run(cycle_id="cyc_impl", run_id="run_impl")

        # Run should fail due to time budget
        status_calls = mock_registry.update_run_status.call_args_list
        final_status = status_calls[-1].args[1]
        assert final_status == RunStatus.FAILED

    async def test_no_time_budget_no_enforcement(
        self, executor, mock_registry, mock_queue
    ) -> None:
        """When time_budget_seconds is not set, no enforcement."""
        mock_queue.consume.side_effect = _make_queue_side_effects(mock_queue)

        with patch(
            "adapters.cycles.distributed_flow_executor.asyncio.sleep",
            new_callable=AsyncMock,
        ):
            await executor.execute_run(cycle_id="cyc_impl", run_id="run_impl")

        status_calls = mock_registry.update_run_status.call_args_list
        final_status = status_calls[-1].args[1]
        assert final_status == RunStatus.COMPLETED

    async def test_time_budget_error_message(
        self, executor, mock_registry, mock_queue, impl_cycle, mock_event_bus
    ) -> None:
        """Error message includes time budget details."""
        import dataclasses

        budget_cycle = dataclasses.replace(
            impl_cycle, applied_defaults={"time_budget_seconds": 0}
        )
        mock_registry.get_cycle.return_value = budget_cycle
        mock_queue.consume.side_effect = _make_queue_side_effects(mock_queue)

        with patch(
            "adapters.cycles.distributed_flow_executor.asyncio.sleep",
            new_callable=AsyncMock,
        ):
            await executor.execute_run(cycle_id="cyc_impl", run_id="run_impl")

        fail_events = [
            c
            for c in mock_event_bus.emit.call_args_list
            if c.args[0] == EventType.RUN_FAILED
        ]
        assert len(fail_events) == 1
        error_msg = fail_events[0].kwargs.get("payload", {}).get("error", "")
        assert "Time budget exhausted" in error_msg


# ---------------------------------------------------------------------------
# Paused state (BLOCKED outcome — Phase 3 full routing, Phase 2 tests _PausedError)
# ---------------------------------------------------------------------------


class TestPausedHandler:
    """_PausedError transitions run to PAUSED."""

    async def test_paused_error_transitions_to_paused(
        self, executor, mock_registry, mock_queue, mock_event_bus
    ) -> None:
        """_PausedError in _execute_sequential → run PAUSED."""
        from adapters.cycles.distributed_flow_executor import _PausedError

        with (
            patch.object(
                executor, "_execute_sequential", side_effect=_PausedError("blocked")
            ),
            patch(
                "adapters.cycles.distributed_flow_executor.asyncio.sleep",
                new_callable=AsyncMock,
            ),
        ):
            await executor.execute_run(cycle_id="cyc_impl", run_id="run_impl")

        # Verify PAUSED status
        status_calls = mock_registry.update_run_status.call_args_list
        # First call: RUNNING, second call: safe_transition → PAUSED
        paused_calls = [c for c in status_calls if c.args[1] == RunStatus.PAUSED]
        assert len(paused_calls) >= 1

    async def test_paused_emits_run_paused_event(
        self, executor, mock_registry, mock_queue, mock_event_bus
    ) -> None:
        from adapters.cycles.distributed_flow_executor import _PausedError

        with (
            patch.object(
                executor, "_execute_sequential", side_effect=_PausedError("blocked")
            ),
            patch(
                "adapters.cycles.distributed_flow_executor.asyncio.sleep",
                new_callable=AsyncMock,
            ),
        ):
            await executor.execute_run(cycle_id="cyc_impl", run_id="run_impl")

        event_types = [c.args[0] for c in mock_event_bus.emit.call_args_list]
        assert EventType.RUN_PAUSED in event_types
