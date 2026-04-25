"""Tests for observability wiring in DistributedFlowExecutor.

Covers LangFuse cycle lifecycle events and Prefect flow/task run
creation in execute_run().
"""

from __future__ import annotations

import json
import logging
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
from squadops.tasks.models import TaskResult

pytestmark = [pytest.mark.domain_orchestration]

NOW = datetime(2026, 1, 15, 12, 0, 0, tzinfo=UTC)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_result_message(
    task_id: str,
    status: str = "SUCCEEDED",
    outputs: dict | None = None,
    queue_name: str = "cycle_results_run_001",
) -> QueueMessage:
    result = TaskResult(task_id=task_id, status=status, outputs=outputs)
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


def _make_queue_side_effects(mock_queue):
    """Build a consume side_effect that returns matching results."""

    async def consume_side_effect(queue_name, max_messages=1):
        if not queue_name.startswith("cycle_results_"):
            return []
        last_call = mock_queue.publish.call_args
        if last_call:
            msg_data = json.loads(last_call.args[1])
            task_id = msg_data["payload"]["task_id"]
            return [
                _make_result_message(
                    task_id=task_id,
                    outputs={
                        "summary": "stub output",
                        "role": "strat",
                        "artifacts": [
                            {
                                "name": "output.md",
                                "content": "# Output",
                                "media_type": "text/markdown",
                                "type": "document",
                            }
                        ],
                    },
                    queue_name=queue_name,
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
            AgentProfileEntry(agent_id="data-agent", role="data", model="gpt-4", enabled=True),
            AgentProfileEntry(agent_id="max", role="lead", model="gpt-4", enabled=True),
        ),
        created_at=NOW,
    )
    mock.resolve_snapshot.return_value = (profile, "sha256:abc")
    return mock


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
def mock_llm_obs():
    return MagicMock()


@pytest.fixture
def mock_prefect():
    mock = AsyncMock()
    mock.ensure_flow.return_value = "flow-abc"
    mock.create_flow_run.return_value = "flowrun-123"
    mock.create_task_run.return_value = "taskrun-xyz"
    return mock


@pytest.fixture
def executor(
    mock_registry,
    mock_vault,
    mock_queue,
    mock_squad_profile,
    cycle,
    mock_llm_obs,
    mock_prefect,
):
    from adapters.cycles.distributed_flow_executor import DistributedFlowExecutor

    mock_registry.get_cycle.return_value = cycle
    return DistributedFlowExecutor(
        cycle_registry=mock_registry,
        artifact_vault=mock_vault,
        queue=mock_queue,
        squad_profile=mock_squad_profile,
        task_timeout=5.0,
        llm_observability=mock_llm_obs,
        workflow_tracker=mock_prefect,
    )


@pytest.fixture
def executor_no_obs(mock_registry, mock_vault, mock_queue, mock_squad_profile, cycle):
    from adapters.cycles.distributed_flow_executor import DistributedFlowExecutor

    mock_registry.get_cycle.return_value = cycle
    return DistributedFlowExecutor(
        cycle_registry=mock_registry,
        artifact_vault=mock_vault,
        queue=mock_queue,
        squad_profile=mock_squad_profile,
        task_timeout=5.0,
    )


# ---------------------------------------------------------------------------
# LangFuse lifecycle
# ---------------------------------------------------------------------------


class TestLangFuseCycleEvents:
    """Verify start_cycle_trace + end_cycle_trace called around execute_run."""

    async def test_emits_langfuse_cycle_events(self, executor, mock_queue, mock_llm_obs):
        mock_queue.consume.side_effect = _make_queue_side_effects(mock_queue)

        with patch(
            "adapters.cycles.distributed_flow_executor.asyncio.sleep",
            new_callable=AsyncMock,
        ):
            await executor.execute_run(cycle_id="cyc_001", run_id="run_001")

        mock_llm_obs.start_cycle_trace.assert_called_once()
        mock_llm_obs.end_cycle_trace.assert_called_once()
        mock_llm_obs.flush.assert_called_once()

        # record_event called twice (started + completed)
        assert mock_llm_obs.record_event.call_count == 2
        event_names = [call.args[1].name for call in mock_llm_obs.record_event.call_args_list]
        assert "cycle.started" in event_names
        assert "cycle.completed" in event_names

    async def test_langfuse_context_has_trace_id(self, executor, mock_queue, mock_llm_obs):
        mock_queue.consume.side_effect = _make_queue_side_effects(mock_queue)

        with patch(
            "adapters.cycles.distributed_flow_executor.asyncio.sleep",
            new_callable=AsyncMock,
        ):
            await executor.execute_run(cycle_id="cyc_001", run_id="run_001")

        ctx = mock_llm_obs.start_cycle_trace.call_args[0][0]
        assert ctx.cycle_id == "cyc_001"
        # trace_id comes from the task plan
        assert ctx.trace_id is not None


class TestWithoutObservability:
    """Existing behavior unaffected when observability ports are None."""

    async def test_no_langfuse_no_prefect_no_error(
        self, executor_no_obs, mock_queue, mock_registry
    ):
        mock_queue.consume.side_effect = _make_queue_side_effects(mock_queue)

        with patch(
            "adapters.cycles.distributed_flow_executor.asyncio.sleep",
            new_callable=AsyncMock,
        ):
            await executor_no_obs.execute_run(cycle_id="cyc_001", run_id="run_001")

        status_calls = mock_registry.update_run_status.call_args_list
        statuses = [c.args[1] for c in status_calls]
        assert statuses[0] == RunStatus.RUNNING
        assert statuses[-1] == RunStatus.COMPLETED


# ---------------------------------------------------------------------------
# Prefect flow/task reporting
# ---------------------------------------------------------------------------


class TestFlowLevelCorrelationScope:
    """SIP-0087 B4: orchestrator-level logs emitted between dispatches must
    carry flow_run_id (and no task_run_id) so they land in the flow-run pane,
    not in any task pane (acceptance criterion §7.2)."""

    async def test_executor_run_log_carries_flow_run_id_only(
        self, executor, mock_queue, mock_prefect, caplog
    ):
        """The "Executing run ..." line and the "Run %s completed" line are
        emitted from execute_run between dispatches. They must reach a
        PrefectLogHandler with flow_run_id set and task_run_id unset."""
        from adapters.cycles.prefect_log_forwarder import (
            LogHandlerFilters,
            PrefectLogHandler,
        )

        mock_queue.consume.side_effect = _make_queue_side_effects(mock_queue)

        forwarder = MagicMock(enqueue=MagicMock())
        handler = PrefectLogHandler(
            forwarder, filters=LogHandlerFilters(min_level=logging.INFO)
        )
        logging.getLogger().addHandler(handler)
        prior_levels = {n: logging.getLogger(n).level for n in ("squadops", "adapters")}
        logging.getLogger("squadops").setLevel(logging.INFO)
        logging.getLogger("adapters").setLevel(logging.INFO)

        try:
            with patch(
                "adapters.cycles.distributed_flow_executor.asyncio.sleep",
                new_callable=AsyncMock,
            ):
                await executor.execute_run(cycle_id="cyc_001", run_id="run_001")
        finally:
            logging.getLogger().removeHandler(handler)
            for name, level in prior_levels.items():
                logging.getLogger(name).setLevel(level)

        # Filter for orchestrator-level enqueues — flow_run_id set, task_run_id empty.
        flow_only = [
            c.args[0]
            for c in forwarder.enqueue.call_args_list
            if c.args[0].get("flow_run_id") and not c.args[0].get("task_run_id")
        ]
        assert flow_only, (
            "no flow-only log records reached the forwarder — "
            "execute_run must wrap orchestrator work in use_correlation_context"
        )

        # The two canonical orchestrator log lines must both be present.
        messages = " | ".join(p["message"] for p in flow_only)
        assert "Executing run run_001" in messages
        assert "Run run_001 completed successfully" in messages


class TestPrefectFlowRun:
    """Verify Prefect flow run created at start."""

    async def test_creates_prefect_flow_run(self, executor, mock_queue, mock_prefect):
        mock_queue.consume.side_effect = _make_queue_side_effects(mock_queue)

        with patch(
            "adapters.cycles.distributed_flow_executor.asyncio.sleep",
            new_callable=AsyncMock,
        ):
            await executor.execute_run(cycle_id="cyc_001", run_id="run_001")

        mock_prefect.ensure_flow.assert_awaited_once()
        mock_prefect.create_flow_run.assert_awaited_once()

        # Terminal state set
        mock_prefect.set_flow_run_state.assert_awaited()
        # Last call should be terminal
        terminal_call = mock_prefect.set_flow_run_state.call_args_list[-1]
        assert terminal_call.args[1] == "COMPLETED"


class TestPrefectTaskRuns:
    """Verify task lifecycle handled in executor (SIP-0087: task_run_id needed
    before dispatch for log-streaming correlation context)."""

    async def test_executor_creates_task_runs_and_sets_running(
        self, executor, mock_queue, mock_prefect
    ):
        """Executor creates task runs + transitions to RUNNING directly so the
        ``task_run_id`` is available for the per-task log forwarder."""
        mock_queue.consume.side_effect = _make_queue_side_effects(mock_queue)

        with patch(
            "adapters.cycles.distributed_flow_executor.asyncio.sleep",
            new_callable=AsyncMock,
        ):
            await executor.execute_run(cycle_id="cyc_001", run_id="run_001")

        # 5 sequential tasks → 5 create_task_run + 5 set_task_run_state(RUNNING)
        assert mock_prefect.create_task_run.await_count == 5
        running_calls = [
            c
            for c in mock_prefect.set_task_run_state.await_args_list
            if c.args[1] == "RUNNING"
        ]
        assert len(running_calls) == 5
        # Terminal task states come through PrefectBridge events, not direct
        # executor calls — the executor only emits RUNNING directly.
        terminal_calls = [
            c
            for c in mock_prefect.set_task_run_state.await_args_list
            if c.args[1] in ("COMPLETED", "FAILED")
        ]
        assert terminal_calls == []

    async def test_emits_task_dispatched_events(self, executor, mock_queue, mock_prefect):
        """Executor emits TASK_DISPATCHED for each of the 5 sequential tasks."""
        from squadops.events.types import EventType

        mock_queue.consume.side_effect = _make_queue_side_effects(mock_queue)

        emitted: list[str] = []
        original_emit = executor._cycle_event_bus.emit

        def capture_emit(event_type, **kwargs):
            emitted.append(event_type)
            return original_emit(event_type, **kwargs)

        executor._cycle_event_bus.emit = capture_emit

        with patch(
            "adapters.cycles.distributed_flow_executor.asyncio.sleep",
            new_callable=AsyncMock,
        ):
            await executor.execute_run(cycle_id="cyc_001", run_id="run_001")

        dispatched = [e for e in emitted if e == EventType.TASK_DISPATCHED]
        succeeded = [e for e in emitted if e == EventType.TASK_SUCCEEDED]
        assert len(dispatched) == 5
        assert len(succeeded) == 5
