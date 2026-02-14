"""Tests for DistributedFlowExecutor (adapters/cycles/distributed_flow_executor.py).

Covers dispatch via RabbitMQ publish/consume, sequential happy path,
fail-fast, cancellation, artifact storage, output chaining, and timeout.

Mirrors test_flow_executor.py structure but with mocked QueuePort instead
of mocked AgentOrchestrator.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest

from squadops.comms.queue_message import QueueMessage
from squadops.cycles.models import (
    AgentProfileEntry,
    ArtifactRef,
    Cycle,
    Run,
    RunStatus,
    SquadProfile,
    TaskFlowPolicy,
)
from squadops.tasks.models import TaskEnvelope, TaskResult


NOW = datetime(2026, 1, 15, 12, 0, 0, tzinfo=timezone.utc)

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
    """Build a QueueMessage containing a TaskResult."""
    result = TaskResult(
        task_id=task_id,
        status=status,
        outputs=outputs,
        error=error,
    )
    payload = json.dumps({
        "action": "comms.task.result",
        "metadata": {"correlation_id": "corr"},
        "payload": result.to_dict(),
    })
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
    return mock


@pytest.fixture
def mock_vault():
    mock = AsyncMock()
    mock.store.side_effect = lambda ref, content: ref
    return mock


@pytest.fixture
def mock_queue():
    """Mock QueuePort that succeeds on publish and returns results on consume."""
    mock = AsyncMock()
    mock.publish.return_value = None
    mock.ack.return_value = None
    # Default: consume returns empty (override per-test)
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
def executor(mock_registry, mock_vault, mock_queue, mock_squad_profile, cycle, run):
    from adapters.cycles.distributed_flow_executor import DistributedFlowExecutor

    mock_registry.get_cycle.return_value = cycle
    mock_registry.get_run.return_value = run
    return DistributedFlowExecutor(
        cycle_registry=mock_registry,
        artifact_vault=mock_vault,
        queue=mock_queue,
        squad_profile=mock_squad_profile,
        task_timeout=5.0,  # Short timeout for tests
    )


# ---------------------------------------------------------------------------
# Dispatch mechanics
# ---------------------------------------------------------------------------


class TestDispatchTask:
    """Verify publish/consume mechanics of _dispatch_task."""

    async def test_publishes_to_agent_comms_queue(
        self, executor, mock_queue, mock_registry, cycle
    ) -> None:
        """Task is published to {agent_id}_comms with comms.task action."""
        # Make consume return a result for the first task
        call_count = 0

        async def consume_side_effect(queue_name, max_messages=1):
            nonlocal call_count
            call_count += 1
            if call_count == 1 and queue_name.startswith("cycle_results_"):
                # Return result for whatever was last published
                last_publish_call = mock_queue.publish.call_args
                if last_publish_call:
                    msg_data = json.loads(last_publish_call.args[1])
                    task_id = msg_data["payload"]["task_id"]
                    return [_make_result_message(
                        task_id=task_id,
                        outputs={"summary": "ok", "artifacts": []},
                        queue_name=queue_name,
                    )]
            return []

        mock_queue.consume.side_effect = consume_side_effect

        envelope = TaskEnvelope(
            task_id="task_abc",
            agent_id="neo",
            cycle_id="cyc_001",
            pulse_id="p1",
            project_id="proj_001",
            task_type="development.implement",
            correlation_id="corr",
            causation_id="cause",
            trace_id="trace",
            span_id="span",
            metadata={"role": "dev"},
        )

        with patch(
            "adapters.cycles.distributed_flow_executor.asyncio.sleep",
            new_callable=AsyncMock,
        ):
            result = await executor._dispatch_task(envelope, "run_001")

        # Verify publish to correct queue
        mock_queue.publish.assert_awaited_once()
        pub_args = mock_queue.publish.call_args
        assert pub_args.args[0] == "neo_comms"

        published = json.loads(pub_args.args[1])
        assert published["action"] == "comms.task"
        assert published["metadata"]["reply_queue"] == "cycle_results_run_001"
        assert published["payload"]["task_id"] == "task_abc"

    async def test_consumes_result_from_reply_queue(
        self, executor, mock_queue
    ) -> None:
        """Result is consumed from cycle_results_{run_id}."""
        result_msg = _make_result_message(
            task_id="task_abc",
            outputs={"summary": "implemented"},
            queue_name="cycle_results_run_001",
        )
        mock_queue.consume.return_value = [result_msg]

        envelope = TaskEnvelope(
            task_id="task_abc",
            agent_id="neo",
            cycle_id="cyc_001",
            pulse_id="p1",
            project_id="proj_001",
            task_type="development.implement",
            correlation_id="corr",
            causation_id="cause",
            trace_id="trace",
            span_id="span",
            metadata={"role": "dev"},
        )

        result = await executor._dispatch_task(envelope, "run_001")

        assert result.task_id == "task_abc"
        assert result.status == "SUCCEEDED"
        assert result.outputs["summary"] == "implemented"
        mock_queue.ack.assert_awaited_once_with(result_msg)

    async def test_timeout_returns_failed(self, executor, mock_queue) -> None:
        """If no result arrives within timeout, returns FAILED TaskResult."""
        mock_queue.consume.return_value = []  # Always empty
        executor._task_timeout = 0.1  # Very short

        envelope = TaskEnvelope(
            task_id="task_abc",
            agent_id="neo",
            cycle_id="cyc_001",
            pulse_id="p1",
            project_id="proj_001",
            task_type="development.implement",
            correlation_id="corr",
            causation_id="cause",
            trace_id="trace",
            span_id="span",
            metadata={"role": "dev"},
        )

        with patch(
            "adapters.cycles.distributed_flow_executor.asyncio.sleep",
            new_callable=AsyncMock,
        ):
            result = await executor._dispatch_task(envelope, "run_001")

        assert result.status == "FAILED"
        assert "Timed out" in result.error


# ---------------------------------------------------------------------------
# Sequential happy path
# ---------------------------------------------------------------------------


class TestSequentialHappyPath:
    """Sequential mode: 5 tasks dispatched via queue, run completes."""

    @staticmethod
    def _make_queue_side_effects(mock_queue):
        """Build a consume side_effect that returns matching results."""
        async def consume_side_effect(queue_name, max_messages=1):
            if not queue_name.startswith("cycle_results_"):
                return []
            # Return result matching the most recent publish
            last_call = mock_queue.publish.call_args
            if last_call:
                msg_data = json.loads(last_call.args[1])
                task_id = msg_data["payload"]["task_id"]
                return [_make_result_message(
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
                )]
            return []

        return consume_side_effect

    async def test_run_completes(self, executor, mock_registry, mock_queue) -> None:
        """5 tasks dispatched; run transitions queued -> running -> completed."""
        mock_queue.consume.side_effect = self._make_queue_side_effects(mock_queue)

        with patch(
            "adapters.cycles.distributed_flow_executor.asyncio.sleep",
            new_callable=AsyncMock,
        ):
            await executor.execute_run(cycle_id="cyc_001", run_id="run_001")

        status_calls = mock_registry.update_run_status.call_args_list
        statuses = [c.args[1] for c in status_calls]
        assert statuses[0] == RunStatus.RUNNING
        assert statuses[-1] == RunStatus.COMPLETED

    async def test_publish_called_5_times(self, executor, mock_queue) -> None:
        """queue.publish called once per pipeline step (5 total)."""
        mock_queue.consume.side_effect = self._make_queue_side_effects(mock_queue)

        with patch(
            "adapters.cycles.distributed_flow_executor.asyncio.sleep",
            new_callable=AsyncMock,
        ):
            await executor.execute_run(cycle_id="cyc_001", run_id="run_001")

        assert mock_queue.publish.call_count == 5

    async def test_publishes_to_correct_agent_queues(self, executor, mock_queue) -> None:
        """Each task published to the correct agent's comms queue."""
        mock_queue.consume.side_effect = self._make_queue_side_effects(mock_queue)

        with patch(
            "adapters.cycles.distributed_flow_executor.asyncio.sleep",
            new_callable=AsyncMock,
        ):
            await executor.execute_run(cycle_id="cyc_001", run_id="run_001")

        published_queues = [
            call.args[0] for call in mock_queue.publish.call_args_list
        ]
        assert published_queues == [
            "nat_comms",     # strategy.analyze_prd -> strat -> nat
            "neo_comms",     # development.implement -> dev -> neo
            "eve_comms",     # qa.validate -> qa -> eve
            "data-agent_comms",  # data.report -> data -> data-agent
            "max_comms",     # governance.review -> lead -> max
        ]

    async def test_artifacts_stored(self, executor, mock_vault, mock_queue) -> None:
        """vault.store called for each task's artifacts."""
        mock_queue.consume.side_effect = self._make_queue_side_effects(mock_queue)

        with patch(
            "adapters.cycles.distributed_flow_executor.asyncio.sleep",
            new_callable=AsyncMock,
        ):
            await executor.execute_run(cycle_id="cyc_001", run_id="run_001")

        # 5 task artifacts + 1 run report = 6
        assert mock_vault.store.call_count == 6


# ---------------------------------------------------------------------------
# Fail-fast
# ---------------------------------------------------------------------------


class TestFailFast:
    """Sequential fail-fast: first failure stops the pipeline."""

    async def test_first_failure_stops_pipeline(
        self, executor, mock_queue, mock_registry
    ) -> None:
        """First task FAILED -> run transitions to FAILED, remaining skipped."""
        async def consume_side_effect(queue_name, max_messages=1):
            if not queue_name.startswith("cycle_results_"):
                return []
            last_call = mock_queue.publish.call_args
            if last_call:
                msg_data = json.loads(last_call.args[1])
                task_id = msg_data["payload"]["task_id"]
                return [_make_result_message(
                    task_id=task_id, status="FAILED", error="boom",
                    queue_name=queue_name,
                )]
            return []

        mock_queue.consume.side_effect = consume_side_effect

        with patch(
            "adapters.cycles.distributed_flow_executor.asyncio.sleep",
            new_callable=AsyncMock,
        ):
            await executor.execute_run(cycle_id="cyc_001", run_id="run_001")

        # Only 1 publish (fail-fast on first task)
        assert mock_queue.publish.call_count == 1

        status_calls = mock_registry.update_run_status.call_args_list
        terminal_statuses = [c.args[1] for c in status_calls]
        assert RunStatus.FAILED in terminal_statuses


# ---------------------------------------------------------------------------
# Cancellation
# ---------------------------------------------------------------------------


class TestCancellation:
    """Run cancellation via local set and registry polling."""

    async def test_cancel_run_sets_local_and_registry(self, executor, mock_registry) -> None:
        await executor.cancel_run("run_001")
        assert "run_001" in executor._cancelled
        mock_registry.cancel_run.assert_awaited_once_with("run_001")

    async def test_cancel_before_first_task(
        self, executor, mock_registry, mock_queue
    ) -> None:
        """If registry returns cancelled, no tasks published."""
        mock_registry.get_run.return_value = Run(
            run_id="run_001",
            cycle_id="cyc_001",
            run_number=1,
            status="cancelled",
            initiated_by="api",
            resolved_config_hash="hash",
        )

        await executor.execute_run(cycle_id="cyc_001", run_id="run_001")

        mock_queue.publish.assert_not_awaited()
        status_calls = mock_registry.update_run_status.call_args_list
        terminal_statuses = [c.args[1] for c in status_calls]
        assert RunStatus.CANCELLED in terminal_statuses


# ---------------------------------------------------------------------------
# Artifact storage
# ---------------------------------------------------------------------------


class TestArtifactStorage:
    """Artifact ref creation from distributed results."""

    async def test_artifact_ref_has_metadata(
        self, executor, mock_vault, mock_queue
    ) -> None:
        """ArtifactRef passed to vault.store has task_id and role in metadata."""
        async def consume_side_effect(queue_name, max_messages=1):
            if not queue_name.startswith("cycle_results_"):
                return []
            last_call = mock_queue.publish.call_args
            if last_call:
                msg_data = json.loads(last_call.args[1])
                task_id = msg_data["payload"]["task_id"]
                return [_make_result_message(
                    task_id=task_id,
                    outputs={
                        "summary": "ok",
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
                )]
            return []

        mock_queue.consume.side_effect = consume_side_effect

        with patch(
            "adapters.cycles.distributed_flow_executor.asyncio.sleep",
            new_callable=AsyncMock,
        ):
            await executor.execute_run(cycle_id="cyc_001", run_id="run_001")

        for call_item in mock_vault.store.call_args_list:
            ref = call_item.args[0]
            assert isinstance(ref, ArtifactRef)
            # Skip run_report.md — it has report_type metadata, not task_id
            if ref.filename == "run_report.md":
                assert "report_type" in ref.metadata
                continue
            assert "task_id" in ref.metadata
            assert "role" in ref.metadata
