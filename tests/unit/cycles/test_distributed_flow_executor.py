"""Tests for DistributedFlowExecutor (adapters/cycles/distributed_flow_executor.py).

Covers dispatch via RabbitMQ publish/consume, sequential happy path,
fail-fast, cancellation, artifact storage, output chaining, and timeout.

Mirrors test_flow_executor.py structure but with mocked QueuePort instead
of mocked AgentOrchestrator.
"""

from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

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
from squadops.cycles.pulse_models import CADENCE_BOUNDARY_ID, SuiteOutcome
from squadops.tasks.models import TaskEnvelope, TaskResult

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
    """Build a QueueMessage containing a TaskResult."""
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
    # SIP-0079: No checkpoint by default (fresh run)
    mock.get_latest_checkpoint.return_value = None
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
                    return [
                        _make_result_message(
                            task_id=task_id,
                            outputs={"summary": "ok", "artifacts": []},
                            queue_name=queue_name,
                        )
                    ]
            return []

        mock_queue.consume.side_effect = consume_side_effect

        envelope = TaskEnvelope(
            task_id="task_abc",
            agent_id="neo",
            cycle_id="cyc_001",
            pulse_id="p1",
            project_id="proj_001",
            task_type="development.design",
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
            await executor._dispatch_task(envelope, "run_001")

        # Verify publish to correct queue
        mock_queue.publish.assert_awaited_once()
        pub_args = mock_queue.publish.call_args
        assert pub_args.args[0] == "neo_comms"

        published = json.loads(pub_args.args[1])
        assert published["action"] == "comms.task"
        assert published["metadata"]["reply_queue"] == "cycle_results_run_001"
        assert published["payload"]["task_id"] == "task_abc"

    async def test_consumes_result_from_reply_queue(self, executor, mock_queue) -> None:
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
            task_type="development.design",
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
            task_type="development.design",
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

        published_queues = [call.args[0] for call in mock_queue.publish.call_args_list]
        assert published_queues == [
            "nat_comms",  # strategy.analyze_prd -> strat -> nat
            "neo_comms",  # development.design -> dev -> neo
            "eve_comms",  # qa.validate -> qa -> eve
            "data-agent_comms",  # data.report -> data -> data-agent
            "max_comms",  # governance.review -> lead -> max
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
    """Outcome routing: persistent failures retry, trigger correction, then abort."""

    async def test_persistent_failure_retries_then_aborts(
        self, executor, mock_queue, mock_registry
    ) -> None:
        """All dispatches FAILED → retry + correction protocol → run FAILED.

        With outcome routing (SIP-0079):
        1. First dispatch: FAILED → RETRYABLE_FAILURE (attempt 1 < max_retries 2)
        2. Retry same task: FAILED → SEMANTIC_FAILURE (attempt 2 >= max_retries 2)
        3. Correction protocol: dispatches analyze_failure + correction_decision
        4. Both correction tasks also fail → correction_path defaults to "abort"
        Total publishes: 2 (task retries) + 2 (correction tasks) = 4
        """

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
                        status="FAILED",
                        error="boom",
                        queue_name=queue_name,
                    )
                ]
            return []

        mock_queue.consume.side_effect = consume_side_effect

        with patch(
            "adapters.cycles.distributed_flow_executor.asyncio.sleep",
            new_callable=AsyncMock,
        ):
            await executor.execute_run(cycle_id="cyc_001", run_id="run_001")

        # 2 (retry) + 2 (correction tasks) = 4 publishes
        assert mock_queue.publish.call_count == 4

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

    async def test_cancel_before_first_task(self, executor, mock_registry, mock_queue) -> None:
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

    async def test_artifact_ref_has_metadata(self, executor, mock_vault, mock_queue) -> None:
        """ArtifactRef passed to vault.store has task_id and role in metadata."""

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
                    )
                ]
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


# ---------------------------------------------------------------------------
# SIP-0070: Pulse verification integration
# ---------------------------------------------------------------------------


def _cycle_with_pulse_checks(
    pulse_checks: list[dict],
    cadence_policy: dict | None = None,
) -> Cycle:
    """Create a Cycle with pulse_checks in applied_defaults."""
    defaults: dict = {"pulse_checks": pulse_checks}
    if cadence_policy:
        defaults["cadence_policy"] = cadence_policy
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
        applied_defaults=defaults,
    )


class TestPulseVerificationBackwardCompat:
    """No pulse_checks = unchanged behavior."""

    async def test_no_pulse_checks_completes_normally(self, executor, mock_queue, mock_registry):
        """Run with no pulse_checks in applied_defaults completes as before."""

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
                        outputs={"summary": "ok", "artifacts": []},
                        queue_name=queue_name,
                    )
                ]
            return []

        mock_queue.consume.side_effect = consume_side_effect

        with patch(
            "adapters.cycles.distributed_flow_executor.asyncio.sleep",
            new_callable=AsyncMock,
        ):
            await executor.execute_run(cycle_id="cyc_001", run_id="run_001")

        statuses = [c.args[1] for c in mock_registry.update_run_status.call_args_list]
        assert statuses[-1] == RunStatus.COMPLETED


class TestPulseVerificationMilestone:
    """Milestone-bound suites fire at correct plan indices."""

    @staticmethod
    def _make_executor_with_pulse(
        mock_registry,
        mock_vault,
        mock_queue,
        mock_squad_profile,
        cycle,
    ):
        from adapters.cycles.distributed_flow_executor import DistributedFlowExecutor

        mock_registry.get_cycle.return_value = cycle
        mock_registry.record_pulse_verification.return_value = mock_registry.get_run.return_value
        return DistributedFlowExecutor(
            cycle_registry=mock_registry,
            artifact_vault=mock_vault,
            queue=mock_queue,
            squad_profile=mock_squad_profile,
            task_timeout=5.0,
        )

    async def test_milestone_pass_continues(
        self, mock_registry, mock_vault, mock_queue, mock_squad_profile
    ):
        """Milestone-bound suite PASS: run completes normally."""
        cycle = _cycle_with_pulse_checks(
            [
                {
                    "suite_id": "post_dev_check",
                    "boundary_id": "post_dev",
                    "after_task_types": ["development"],
                    "binding_mode": "milestone",
                    "checks": [
                        {"check_type": "file_exists", "target": "output.md"},
                    ],
                },
            ]
        )
        executor = self._make_executor_with_pulse(
            mock_registry,
            mock_vault,
            mock_queue,
            mock_squad_profile,
            cycle,
        )

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
                        outputs={"summary": "ok", "artifacts": []},
                        queue_name=queue_name,
                    )
                ]
            return []

        mock_queue.consume.side_effect = consume_side_effect

        # Mock the engine to return PASS
        with (
            patch(
                "adapters.cycles.distributed_flow_executor.asyncio.sleep",
                new_callable=AsyncMock,
            ),
            patch(
                "adapters.cycles.distributed_flow_executor.run_pulse_verification",
            ) as mock_run_pv,
        ):
            from squadops.cycles.pulse_models import PulseVerificationRecord

            mock_run_pv.return_value = [
                PulseVerificationRecord(
                    suite_id="post_dev_check",
                    boundary_id="post_dev",
                    cadence_interval_id=1,
                    run_id="run_001",
                    suite_outcome=SuiteOutcome.PASS,
                ),
            ]
            await executor.execute_run(cycle_id="cyc_001", run_id="run_001")

        statuses = [c.args[1] for c in mock_registry.update_run_status.call_args_list]
        assert statuses[-1] == RunStatus.COMPLETED

    async def test_milestone_fail_stops_run(
        self, mock_registry, mock_vault, mock_queue, mock_squad_profile
    ):
        """Milestone-bound suite FAIL: run transitions to FAILED."""
        cycle = _cycle_with_pulse_checks(
            [
                {
                    "suite_id": "post_dev_check",
                    "boundary_id": "post_dev",
                    "after_task_types": ["development"],
                    "binding_mode": "milestone",
                    "checks": [
                        {"check_type": "file_exists", "target": "output.md"},
                    ],
                },
            ]
        )
        executor = self._make_executor_with_pulse(
            mock_registry,
            mock_vault,
            mock_queue,
            mock_squad_profile,
            cycle,
        )

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
                        outputs={"summary": "ok", "artifacts": []},
                        queue_name=queue_name,
                    )
                ]
            return []

        mock_queue.consume.side_effect = consume_side_effect

        with (
            patch(
                "adapters.cycles.distributed_flow_executor.asyncio.sleep",
                new_callable=AsyncMock,
            ),
            patch(
                "adapters.cycles.distributed_flow_executor.run_pulse_verification",
            ) as mock_run_pv,
        ):
            from squadops.cycles.pulse_models import PulseVerificationRecord

            mock_run_pv.return_value = [
                PulseVerificationRecord(
                    suite_id="post_dev_check",
                    boundary_id="post_dev",
                    cadence_interval_id=1,
                    run_id="run_001",
                    suite_outcome=SuiteOutcome.FAIL,
                ),
            ]
            await executor.execute_run(cycle_id="cyc_001", run_id="run_001")

        statuses = [c.args[1] for c in mock_registry.update_run_status.call_args_list]
        assert RunStatus.FAILED in statuses


class TestPulseVerificationCadence:
    """Cadence-bound suites fire based on task count."""

    @staticmethod
    def _make_executor_with_pulse(
        mock_registry,
        mock_vault,
        mock_queue,
        mock_squad_profile,
        cycle,
    ):
        from adapters.cycles.distributed_flow_executor import DistributedFlowExecutor

        mock_registry.get_cycle.return_value = cycle
        mock_registry.record_pulse_verification.return_value = mock_registry.get_run.return_value
        return DistributedFlowExecutor(
            cycle_registry=mock_registry,
            artifact_vault=mock_vault,
            queue=mock_queue,
            squad_profile=mock_squad_profile,
            task_timeout=5.0,
        )

    async def test_cadence_close_by_task_count(
        self, mock_registry, mock_vault, mock_queue, mock_squad_profile
    ):
        """Cadence suite runs when max_tasks_per_pulse reached."""
        cycle = _cycle_with_pulse_checks(
            pulse_checks=[
                {
                    "suite_id": "heartbeat",
                    "boundary_id": CADENCE_BOUNDARY_ID,
                    "binding_mode": "cadence",
                    "checks": [
                        {"check_type": "file_exists", "target": "output.md"},
                    ],
                },
            ],
            cadence_policy={"max_tasks_per_pulse": 2, "max_pulse_seconds": 9999},
        )
        executor = self._make_executor_with_pulse(
            mock_registry,
            mock_vault,
            mock_queue,
            mock_squad_profile,
            cycle,
        )

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
                        outputs={"summary": "ok", "artifacts": []},
                        queue_name=queue_name,
                    )
                ]
            return []

        mock_queue.consume.side_effect = consume_side_effect

        with (
            patch(
                "adapters.cycles.distributed_flow_executor.asyncio.sleep",
                new_callable=AsyncMock,
            ),
            patch(
                "adapters.cycles.distributed_flow_executor.run_pulse_verification",
            ) as mock_run_pv,
        ):
            from squadops.cycles.pulse_models import PulseVerificationRecord

            mock_run_pv.return_value = [
                PulseVerificationRecord(
                    suite_id="heartbeat",
                    boundary_id=CADENCE_BOUNDARY_ID,
                    cadence_interval_id=1,
                    run_id="run_001",
                    suite_outcome=SuiteOutcome.PASS,
                ),
            ]
            await executor.execute_run(cycle_id="cyc_001", run_id="run_001")

        # With 5 tasks and max_tasks_per_pulse=2:
        # cadence closes at index 1 (count=2), 3 (count=2), 4 (last task)
        # So run_pulse_verification should be called 3 times for cadence
        assert mock_run_pv.call_count == 3

    async def test_cadence_fail_stops_run(
        self, mock_registry, mock_vault, mock_queue, mock_squad_profile
    ):
        """Cadence suite FAIL: run transitions to FAILED."""
        cycle = _cycle_with_pulse_checks(
            pulse_checks=[
                {
                    "suite_id": "heartbeat",
                    "boundary_id": CADENCE_BOUNDARY_ID,
                    "binding_mode": "cadence",
                    "checks": [
                        {"check_type": "file_exists", "target": "output.md"},
                    ],
                },
            ],
            cadence_policy={"max_tasks_per_pulse": 2, "max_pulse_seconds": 9999},
        )
        executor = self._make_executor_with_pulse(
            mock_registry,
            mock_vault,
            mock_queue,
            mock_squad_profile,
            cycle,
        )

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
                        outputs={"summary": "ok", "artifacts": []},
                        queue_name=queue_name,
                    )
                ]
            return []

        mock_queue.consume.side_effect = consume_side_effect

        with (
            patch(
                "adapters.cycles.distributed_flow_executor.asyncio.sleep",
                new_callable=AsyncMock,
            ),
            patch(
                "adapters.cycles.distributed_flow_executor.run_pulse_verification",
            ) as mock_run_pv,
        ):
            from squadops.cycles.pulse_models import PulseVerificationRecord

            mock_run_pv.return_value = [
                PulseVerificationRecord(
                    suite_id="heartbeat",
                    boundary_id=CADENCE_BOUNDARY_ID,
                    cadence_interval_id=1,
                    run_id="run_001",
                    suite_outcome=SuiteOutcome.FAIL,
                ),
            ]
            await executor.execute_run(cycle_id="cyc_001", run_id="run_001")

        statuses = [c.args[1] for c in mock_registry.update_run_status.call_args_list]
        assert RunStatus.FAILED in statuses

    async def test_cadence_close_by_wall_clock_time(
        self, mock_registry, mock_vault, mock_queue, mock_squad_profile
    ):
        """Cadence suite runs when max_pulse_seconds elapsed (non-preemptive).

        Mocks _dispatch_task directly to avoid time.monotonic interference
        with the dispatch timeout loop, then mocks time.monotonic to
        simulate wall-clock advancement beyond max_pulse_seconds.
        """
        cycle = _cycle_with_pulse_checks(
            pulse_checks=[
                {
                    "suite_id": "heartbeat",
                    "boundary_id": CADENCE_BOUNDARY_ID,
                    "binding_mode": "cadence",
                    "checks": [
                        {"check_type": "file_exists", "target": "output.md"},
                    ],
                },
            ],
            # High task count so only wall-clock triggers cadence close
            cadence_policy={"max_tasks_per_pulse": 999, "max_pulse_seconds": 10},
        )
        executor = self._make_executor_with_pulse(
            mock_registry,
            mock_vault,
            mock_queue,
            mock_squad_profile,
            cycle,
        )

        # Mock _dispatch_task to return success instantly (bypasses time.monotonic
        # in the dispatch polling loop)
        async def fake_dispatch(envelope, run_id, **kwargs):
            return TaskResult(
                task_id=envelope.task_id,
                status="SUCCEEDED",
                outputs={"summary": "ok", "artifacts": []},
            )

        executor._dispatch_task = fake_dispatch

        # Simulate time advancing 15s between each monotonic() call.
        # cadence tracking calls monotonic() twice per task iteration:
        #   1. cadence_start_time = time.monotonic() (at reset)
        #   2. elapsed = time.monotonic() - cadence_start_time (in loop)
        # With 15s jumps and max_pulse_seconds=10, elapsed is always > 10.
        mono_counter = [0.0]

        def fake_monotonic():
            val = mono_counter[0]
            mono_counter[0] += 15.0
            return val

        with (
            patch(
                "adapters.cycles.distributed_flow_executor.time.monotonic",
                side_effect=fake_monotonic,
            ),
            patch(
                "adapters.cycles.distributed_flow_executor.run_pulse_verification",
            ) as mock_run_pv,
        ):
            from squadops.cycles.pulse_models import PulseVerificationRecord

            mock_run_pv.return_value = [
                PulseVerificationRecord(
                    suite_id="heartbeat",
                    boundary_id=CADENCE_BOUNDARY_ID,
                    cadence_interval_id=1,
                    run_id="run_001",
                    suite_outcome=SuiteOutcome.PASS,
                ),
            ]
            await executor.execute_run(cycle_id="cyc_001", run_id="run_001")

        # With 5 tasks and simulated 15s between monotonic() calls
        # (> 10s max_pulse_seconds), every task triggers cadence close.
        assert mock_run_pv.call_count == 5

        statuses = [c.args[1] for c in mock_registry.update_run_status.call_args_list]
        assert statuses[-1] == RunStatus.COMPLETED


class TestPulseVerificationTelemetry:
    """Telemetry events emitted for pulse check boundaries."""

    @staticmethod
    def _make_executor_with_obs(
        mock_registry,
        mock_vault,
        mock_queue,
        mock_squad_profile,
        cycle,
    ):
        from adapters.cycles.distributed_flow_executor import DistributedFlowExecutor

        mock_registry.get_cycle.return_value = cycle
        mock_registry.record_pulse_verification.return_value = mock_registry.get_run.return_value
        obs = MagicMock()
        return DistributedFlowExecutor(
            cycle_registry=mock_registry,
            artifact_vault=mock_vault,
            queue=mock_queue,
            squad_profile=mock_squad_profile,
            task_timeout=5.0,
            llm_observability=obs,
        ), obs

    async def test_boundary_decision_event_emitted(
        self, mock_registry, mock_vault, mock_queue, mock_squad_profile
    ):
        """pulse_check.boundary_decision event emitted at milestone boundary."""
        cycle = _cycle_with_pulse_checks(
            [
                {
                    "suite_id": "post_dev_check",
                    "boundary_id": "post_dev",
                    "after_task_types": ["development"],
                    "binding_mode": "milestone",
                    "checks": [
                        {"check_type": "file_exists", "target": "output.md"},
                    ],
                },
            ]
        )
        executor, obs = self._make_executor_with_obs(
            mock_registry,
            mock_vault,
            mock_queue,
            mock_squad_profile,
            cycle,
        )

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
                        outputs={"summary": "ok", "artifacts": []},
                        queue_name=queue_name,
                    )
                ]
            return []

        mock_queue.consume.side_effect = consume_side_effect

        with (
            patch(
                "adapters.cycles.distributed_flow_executor.asyncio.sleep",
                new_callable=AsyncMock,
            ),
            patch(
                "adapters.cycles.distributed_flow_executor.run_pulse_verification",
            ) as mock_run_pv,
        ):
            from squadops.cycles.pulse_models import PulseVerificationRecord

            mock_run_pv.return_value = [
                PulseVerificationRecord(
                    suite_id="post_dev_check",
                    boundary_id="post_dev",
                    cadence_interval_id=1,
                    run_id="run_001",
                    suite_outcome=SuiteOutcome.PASS,
                ),
            ]
            await executor.execute_run(cycle_id="cyc_001", run_id="run_001")

        # Find pulse_check.boundary_decision events
        event_names = []
        for call in obs.record_event.call_args_list:
            event = call.args[1]
            event_names.append(event.name)

        assert "pulse_check.boundary_decision" in event_names

    async def test_suite_started_and_passed_events(
        self, mock_registry, mock_vault, mock_queue, mock_squad_profile
    ):
        """suite_started and suite_passed events emitted per suite."""
        cycle = _cycle_with_pulse_checks(
            [
                {
                    "suite_id": "post_dev_check",
                    "boundary_id": "post_dev",
                    "after_task_types": ["development"],
                    "binding_mode": "milestone",
                    "checks": [
                        {"check_type": "file_exists", "target": "output.md"},
                    ],
                },
            ]
        )
        executor, obs = self._make_executor_with_obs(
            mock_registry,
            mock_vault,
            mock_queue,
            mock_squad_profile,
            cycle,
        )

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
                        outputs={"summary": "ok", "artifacts": []},
                        queue_name=queue_name,
                    )
                ]
            return []

        mock_queue.consume.side_effect = consume_side_effect

        with (
            patch(
                "adapters.cycles.distributed_flow_executor.asyncio.sleep",
                new_callable=AsyncMock,
            ),
            patch(
                "adapters.cycles.distributed_flow_executor.run_pulse_verification",
            ) as mock_run_pv,
        ):
            from squadops.cycles.pulse_models import PulseVerificationRecord

            mock_run_pv.return_value = [
                PulseVerificationRecord(
                    suite_id="post_dev_check",
                    boundary_id="post_dev",
                    cadence_interval_id=1,
                    run_id="run_001",
                    suite_outcome=SuiteOutcome.PASS,
                ),
            ]
            await executor.execute_run(cycle_id="cyc_001", run_id="run_001")

        event_names = [call.args[1].name for call in obs.record_event.call_args_list]
        assert "pulse_check.suite_started" in event_names
        assert "pulse_check.suite_passed" in event_names

    async def test_suite_failed_event(
        self, mock_registry, mock_vault, mock_queue, mock_squad_profile
    ):
        """suite_failed event emitted when suite outcome is FAIL."""
        cycle = _cycle_with_pulse_checks(
            [
                {
                    "suite_id": "post_dev_check",
                    "boundary_id": "post_dev",
                    "after_task_types": ["development"],
                    "binding_mode": "milestone",
                    "checks": [
                        {"check_type": "file_exists", "target": "output.md"},
                    ],
                },
            ]
        )
        executor, obs = self._make_executor_with_obs(
            mock_registry,
            mock_vault,
            mock_queue,
            mock_squad_profile,
            cycle,
        )

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
                        outputs={"summary": "ok", "artifacts": []},
                        queue_name=queue_name,
                    )
                ]
            return []

        mock_queue.consume.side_effect = consume_side_effect

        with (
            patch(
                "adapters.cycles.distributed_flow_executor.asyncio.sleep",
                new_callable=AsyncMock,
            ),
            patch(
                "adapters.cycles.distributed_flow_executor.run_pulse_verification",
            ) as mock_run_pv,
        ):
            from squadops.cycles.pulse_models import PulseVerificationRecord

            mock_run_pv.return_value = [
                PulseVerificationRecord(
                    suite_id="post_dev_check",
                    boundary_id="post_dev",
                    cadence_interval_id=1,
                    run_id="run_001",
                    suite_outcome=SuiteOutcome.FAIL,
                ),
            ]
            await executor.execute_run(cycle_id="cyc_001", run_id="run_001")

        event_names = [call.args[1].name for call in obs.record_event.call_args_list]
        assert "pulse_check.suite_failed" in event_names

    async def test_binding_skipped_event_for_unmatched(
        self, mock_registry, mock_vault, mock_queue, mock_squad_profile
    ):
        """pulse_check.binding_skipped emitted for unmatched milestone suites."""
        cycle = _cycle_with_pulse_checks(
            [
                {
                    "suite_id": "post_deploy_check",
                    "boundary_id": "post_deploy",
                    "after_task_types": ["deploy"],  # no task matches this
                    "binding_mode": "milestone",
                    "checks": [
                        {"check_type": "file_exists", "target": "output.md"},
                    ],
                },
            ]
        )
        executor, obs = self._make_executor_with_obs(
            mock_registry,
            mock_vault,
            mock_queue,
            mock_squad_profile,
            cycle,
        )

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
                        outputs={"summary": "ok", "artifacts": []},
                        queue_name=queue_name,
                    )
                ]
            return []

        mock_queue.consume.side_effect = consume_side_effect

        with patch(
            "adapters.cycles.distributed_flow_executor.asyncio.sleep",
            new_callable=AsyncMock,
        ):
            await executor.execute_run(cycle_id="cyc_001", run_id="run_001")

        event_names = [call.args[1].name for call in obs.record_event.call_args_list]
        assert "pulse_check.binding_skipped" in event_names


class TestPulseVerificationCombined:
    """Both cadence and milestone suites at the same dispatch point."""

    @staticmethod
    def _make_executor_with_pulse(
        mock_registry,
        mock_vault,
        mock_queue,
        mock_squad_profile,
        cycle,
    ):
        from adapters.cycles.distributed_flow_executor import DistributedFlowExecutor

        mock_registry.get_cycle.return_value = cycle
        mock_registry.record_pulse_verification.return_value = mock_registry.get_run.return_value
        return DistributedFlowExecutor(
            cycle_registry=mock_registry,
            artifact_vault=mock_vault,
            queue=mock_queue,
            squad_profile=mock_squad_profile,
            task_timeout=5.0,
        )

    async def test_both_cadence_and_milestone_fire(
        self, mock_registry, mock_vault, mock_queue, mock_squad_profile
    ):
        """When milestone and cadence close coincide, both run with separate boundary_ids."""
        cycle = _cycle_with_pulse_checks(
            pulse_checks=[
                {
                    "suite_id": "post_dev_check",
                    "boundary_id": "post_dev",
                    "after_task_types": ["development"],
                    "binding_mode": "milestone",
                    "checks": [
                        {"check_type": "file_exists", "target": "output.md"},
                    ],
                },
                {
                    "suite_id": "heartbeat",
                    "boundary_id": CADENCE_BOUNDARY_ID,
                    "binding_mode": "cadence",
                    "checks": [
                        {"check_type": "file_exists", "target": "output.md"},
                    ],
                },
            ],
            cadence_policy={"max_tasks_per_pulse": 2, "max_pulse_seconds": 9999},
        )
        executor = self._make_executor_with_pulse(
            mock_registry,
            mock_vault,
            mock_queue,
            mock_squad_profile,
            cycle,
        )

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
                        outputs={"summary": "ok", "artifacts": []},
                        queue_name=queue_name,
                    )
                ]
            return []

        mock_queue.consume.side_effect = consume_side_effect

        with (
            patch(
                "adapters.cycles.distributed_flow_executor.asyncio.sleep",
                new_callable=AsyncMock,
            ),
            patch(
                "adapters.cycles.distributed_flow_executor.run_pulse_verification",
            ) as mock_run_pv,
        ):
            from squadops.cycles.pulse_models import PulseVerificationRecord

            mock_run_pv.return_value = [
                PulseVerificationRecord(
                    suite_id="any",
                    boundary_id="any",
                    cadence_interval_id=1,
                    run_id="run_001",
                    suite_outcome=SuiteOutcome.PASS,
                ),
            ]
            await executor.execute_run(cycle_id="cyc_001", run_id="run_001")

        # Verify both milestone and cadence boundary_ids appear in calls
        boundary_ids_seen = set()
        for call in mock_run_pv.call_args_list:
            boundary_ids_seen.add(
                call.kwargs.get("boundary_id", call.args[3] if len(call.args) > 3 else None)
            )

        assert "post_dev" in boundary_ids_seen
        assert CADENCE_BOUNDARY_ID in boundary_ids_seen


class TestPulseVerificationRecordPersistence:
    """Registry.record_pulse_verification called for each suite record."""

    @staticmethod
    def _make_executor_with_pulse(
        mock_registry,
        mock_vault,
        mock_queue,
        mock_squad_profile,
        cycle,
    ):
        from adapters.cycles.distributed_flow_executor import DistributedFlowExecutor

        mock_registry.get_cycle.return_value = cycle
        mock_registry.record_pulse_verification.return_value = mock_registry.get_run.return_value
        return DistributedFlowExecutor(
            cycle_registry=mock_registry,
            artifact_vault=mock_vault,
            queue=mock_queue,
            squad_profile=mock_squad_profile,
            task_timeout=5.0,
        )

    async def test_records_persisted_via_registry(
        self, mock_registry, mock_vault, mock_queue, mock_squad_profile
    ):
        """record_pulse_verification called for each suite at boundary."""
        cycle = _cycle_with_pulse_checks(
            [
                {
                    "suite_id": "post_dev_check",
                    "boundary_id": "post_dev",
                    "after_task_types": ["development"],
                    "binding_mode": "milestone",
                    "checks": [
                        {"check_type": "file_exists", "target": "output.md"},
                    ],
                },
            ]
        )
        executor = self._make_executor_with_pulse(
            mock_registry,
            mock_vault,
            mock_queue,
            mock_squad_profile,
            cycle,
        )

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
                        outputs={"summary": "ok", "artifacts": []},
                        queue_name=queue_name,
                    )
                ]
            return []

        mock_queue.consume.side_effect = consume_side_effect

        with (
            patch(
                "adapters.cycles.distributed_flow_executor.asyncio.sleep",
                new_callable=AsyncMock,
            ),
            patch(
                "adapters.cycles.distributed_flow_executor.run_pulse_verification",
            ) as mock_run_pv,
        ):
            from squadops.cycles.pulse_models import PulseVerificationRecord

            mock_run_pv.return_value = [
                PulseVerificationRecord(
                    suite_id="post_dev_check",
                    boundary_id="post_dev",
                    cadence_interval_id=1,
                    run_id="run_001",
                    suite_outcome=SuiteOutcome.PASS,
                ),
            ]
            await executor.execute_run(cycle_id="cyc_001", run_id="run_001")

        assert mock_registry.record_pulse_verification.call_count >= 1
        record_arg = mock_registry.record_pulse_verification.call_args_list[0].args[1]
        assert record_arg.suite_id == "post_dev_check"
        assert record_arg.boundary_id == "post_dev"


# ==========================================================================
# Phase 3: Repair Loop
# ==========================================================================


@pytest.mark.domain_pulse_checks
class TestPulseRepairLoop:
    """FAIL triggers bounded repair loop; PASS after repair resumes; EXHAUSTED stops."""

    @staticmethod
    def _make_executor_with_pulse(
        mock_registry,
        mock_vault,
        mock_queue,
        mock_squad_profile,
        cycle,
    ):
        from adapters.cycles.distributed_flow_executor import DistributedFlowExecutor

        mock_registry.get_cycle.return_value = cycle
        mock_registry.record_pulse_verification.return_value = mock_registry.get_run.return_value
        return DistributedFlowExecutor(
            cycle_registry=mock_registry,
            artifact_vault=mock_vault,
            queue=mock_queue,
            squad_profile=mock_squad_profile,
            task_timeout=5.0,
        )

    @staticmethod
    def _consume_side_effect(mock_queue):
        """Return success for every dispatched task (plan + repair)."""

        async def _side_effect(queue_name, max_messages=1):
            if not queue_name.startswith("cycle_results_"):
                return []
            last_call = mock_queue.publish.call_args
            if last_call:
                msg_data = json.loads(last_call.args[1])
                task_id = msg_data["payload"]["task_id"]
                return [
                    _make_result_message(
                        task_id=task_id,
                        outputs={"summary": "ok", "artifacts": []},
                        queue_name=queue_name,
                    )
                ]
            return []

        return _side_effect

    async def test_fail_repair_pass_continues(
        self,
        mock_registry,
        mock_vault,
        mock_queue,
        mock_squad_profile,
    ):
        """FAIL → repair chain dispatched → rerun PASS → run COMPLETED."""
        cycle = _cycle_with_pulse_checks(
            [
                {
                    "suite_id": "post_dev_check",
                    "boundary_id": "post_dev",
                    "after_task_types": ["development"],
                    "binding_mode": "milestone",
                    "checks": [{"check_type": "file_exists", "target": "output.md"}],
                }
            ]
        )
        executor = self._make_executor_with_pulse(
            mock_registry,
            mock_vault,
            mock_queue,
            mock_squad_profile,
            cycle,
        )
        mock_queue.consume.side_effect = self._consume_side_effect(mock_queue)

        # First call: FAIL; second call (after repair): PASS
        call_count = {"n": 0}

        from squadops.cycles.pulse_models import PulseVerificationRecord

        def run_pv_side_effect(*args, **kwargs):
            call_count["n"] += 1
            outcome = SuiteOutcome.FAIL if call_count["n"] == 1 else SuiteOutcome.PASS
            return [
                PulseVerificationRecord(
                    suite_id="post_dev_check",
                    boundary_id="post_dev",
                    cadence_interval_id=kwargs.get("cadence_interval_id", 1),
                    run_id=kwargs.get("run_id", "run_001"),
                    suite_outcome=outcome,
                )
            ]

        with (
            patch(
                "adapters.cycles.distributed_flow_executor.asyncio.sleep", new_callable=AsyncMock
            ),
            patch(
                "adapters.cycles.distributed_flow_executor.run_pulse_verification",
                side_effect=run_pv_side_effect,
            ),
        ):
            await executor.execute_run(cycle_id="cyc_001", run_id="run_001")

        statuses = [c.args[1] for c in mock_registry.update_run_status.call_args_list]
        assert statuses[-1] == RunStatus.COMPLETED

        # 2 plan tasks (strat + dev) before milestone, 4 repair, then 3 remaining = 9
        assert mock_queue.publish.call_count == 9

    async def test_fail_repair_fail_exhausted(
        self,
        mock_registry,
        mock_vault,
        mock_queue,
        mock_squad_profile,
    ):
        """FAIL → repair → still FAIL → repair → still FAIL → EXHAUSTED → FAILED."""
        cycle = _cycle_with_pulse_checks(
            [
                {
                    "suite_id": "post_dev_check",
                    "boundary_id": "post_dev",
                    "after_task_types": ["development"],
                    "binding_mode": "milestone",
                    "checks": [{"check_type": "file_exists", "target": "output.md"}],
                }
            ]
        )
        executor = self._make_executor_with_pulse(
            mock_registry,
            mock_vault,
            mock_queue,
            mock_squad_profile,
            cycle,
        )
        mock_queue.consume.side_effect = self._consume_side_effect(mock_queue)

        from squadops.cycles.pulse_models import PulseVerificationRecord

        def always_fail(*args, **kwargs):
            return [
                PulseVerificationRecord(
                    suite_id="post_dev_check",
                    boundary_id="post_dev",
                    cadence_interval_id=kwargs.get("cadence_interval_id", 1),
                    run_id=kwargs.get("run_id", "run_001"),
                    suite_outcome=SuiteOutcome.FAIL,
                )
            ]

        with (
            patch(
                "adapters.cycles.distributed_flow_executor.asyncio.sleep", new_callable=AsyncMock
            ),
            patch(
                "adapters.cycles.distributed_flow_executor.run_pulse_verification",
                side_effect=always_fail,
            ),
        ):
            await executor.execute_run(cycle_id="cyc_001", run_id="run_001")

        statuses = [c.args[1] for c in mock_registry.update_run_status.call_args_list]
        assert RunStatus.FAILED in statuses

        # 2 plan tasks (strat + dev) + 4 repair × 2 attempts = 10 publishes
        # (milestone fires after dev, before qa/data/lead)
        assert mock_queue.publish.call_count == 10

    async def test_exhausted_error_message_contains_verification_exhausted(
        self,
        mock_registry,
        mock_vault,
        mock_queue,
        mock_squad_profile,
    ):
        """Error message on EXHAUSTED should contain VERIFICATION_EXHAUSTED."""
        cycle = _cycle_with_pulse_checks(
            [
                {
                    "suite_id": "post_dev_check",
                    "boundary_id": "post_dev",
                    "after_task_types": ["development"],
                    "binding_mode": "milestone",
                    "checks": [{"check_type": "file_exists", "target": "output.md"}],
                }
            ]
        )
        executor = self._make_executor_with_pulse(
            mock_registry,
            mock_vault,
            mock_queue,
            mock_squad_profile,
            cycle,
        )
        mock_queue.consume.side_effect = self._consume_side_effect(mock_queue)

        from squadops.cycles.pulse_models import PulseVerificationRecord

        def always_fail(*args, **kwargs):
            return [
                PulseVerificationRecord(
                    suite_id="post_dev_check",
                    boundary_id="post_dev",
                    cadence_interval_id=kwargs.get("cadence_interval_id", 1),
                    run_id=kwargs.get("run_id", "run_001"),
                    suite_outcome=SuiteOutcome.FAIL,
                )
            ]

        with (
            patch(
                "adapters.cycles.distributed_flow_executor.asyncio.sleep", new_callable=AsyncMock
            ),
            patch(
                "adapters.cycles.distributed_flow_executor.run_pulse_verification",
                side_effect=always_fail,
            ),
        ):
            await executor.execute_run(cycle_id="cyc_001", run_id="run_001")

        statuses = [c.args[1] for c in mock_registry.update_run_status.call_args_list]
        assert RunStatus.FAILED in statuses

    async def test_repair_only_reruns_failed_suites(
        self,
        mock_registry,
        mock_vault,
        mock_queue,
        mock_squad_profile,
    ):
        """When one of two suites passes, only the failed one is rerun."""
        cycle = _cycle_with_pulse_checks(
            [
                {
                    "suite_id": "s1_passes",
                    "boundary_id": "post_dev",
                    "after_task_types": ["development"],
                    "binding_mode": "milestone",
                    "checks": [{"check_type": "file_exists", "target": "a.md"}],
                },
                {
                    "suite_id": "s2_fails",
                    "boundary_id": "post_dev",
                    "after_task_types": ["development"],
                    "binding_mode": "milestone",
                    "checks": [{"check_type": "file_exists", "target": "b.md"}],
                },
            ]
        )
        executor = self._make_executor_with_pulse(
            mock_registry,
            mock_vault,
            mock_queue,
            mock_squad_profile,
            cycle,
        )
        mock_queue.consume.side_effect = self._consume_side_effect(mock_queue)

        from squadops.cycles.pulse_models import PulseVerificationRecord

        call_count = {"n": 0}

        def mixed_pv(*args, **kwargs):
            call_count["n"] += 1
            suites = kwargs.get("suites") or args[0] if args else []
            records = []
            for suite in suites:
                if suite.suite_id == "s1_passes":
                    outcome = SuiteOutcome.PASS
                elif call_count["n"] <= 1:
                    outcome = SuiteOutcome.FAIL
                else:
                    outcome = SuiteOutcome.PASS
                records.append(
                    PulseVerificationRecord(
                        suite_id=suite.suite_id,
                        boundary_id="post_dev",
                        cadence_interval_id=kwargs.get("cadence_interval_id", 1),
                        run_id=kwargs.get("run_id", "run_001"),
                        suite_outcome=outcome,
                    )
                )
            return records

        with (
            patch(
                "adapters.cycles.distributed_flow_executor.asyncio.sleep", new_callable=AsyncMock
            ),
            patch(
                "adapters.cycles.distributed_flow_executor.run_pulse_verification",
                side_effect=mixed_pv,
            ),
        ):
            await executor.execute_run(cycle_id="cyc_001", run_id="run_001")

        statuses = [c.args[1] for c in mock_registry.update_run_status.call_args_list]
        assert statuses[-1] == RunStatus.COMPLETED

    async def test_max_repair_attempts_configurable(
        self,
        mock_registry,
        mock_vault,
        mock_queue,
        mock_squad_profile,
    ):
        """max_repair_attempts from applied_defaults controls exhaustion threshold."""
        cycle = _cycle_with_pulse_checks(
            pulse_checks=[
                {
                    "suite_id": "post_dev_check",
                    "boundary_id": "post_dev",
                    "after_task_types": ["development"],
                    "binding_mode": "milestone",
                    "checks": [{"check_type": "file_exists", "target": "output.md"}],
                }
            ],
        )
        # Override max_repair_attempts to 1
        import dataclasses

        cycle = dataclasses.replace(
            cycle,
            applied_defaults={**cycle.applied_defaults, "max_repair_attempts": 1},
        )
        mock_registry.get_cycle.return_value = cycle

        executor = self._make_executor_with_pulse(
            mock_registry,
            mock_vault,
            mock_queue,
            mock_squad_profile,
            cycle,
        )
        mock_queue.consume.side_effect = self._consume_side_effect(mock_queue)

        from squadops.cycles.pulse_models import PulseVerificationRecord

        def always_fail(*args, **kwargs):
            return [
                PulseVerificationRecord(
                    suite_id="post_dev_check",
                    boundary_id="post_dev",
                    cadence_interval_id=kwargs.get("cadence_interval_id", 1),
                    run_id=kwargs.get("run_id", "run_001"),
                    suite_outcome=SuiteOutcome.FAIL,
                )
            ]

        with (
            patch(
                "adapters.cycles.distributed_flow_executor.asyncio.sleep", new_callable=AsyncMock
            ),
            patch(
                "adapters.cycles.distributed_flow_executor.run_pulse_verification",
                side_effect=always_fail,
            ),
        ):
            await executor.execute_run(cycle_id="cyc_001", run_id="run_001")

        # 2 plan tasks + 4 repair × 1 attempt = 6 publishes (exhausted after 1 attempt)
        assert mock_queue.publish.call_count == 6

    async def test_cadence_fail_repair_pass(
        self,
        mock_registry,
        mock_vault,
        mock_queue,
        mock_squad_profile,
    ):
        """Cadence-bound FAIL triggers repair, then PASS → run COMPLETED."""
        cycle = _cycle_with_pulse_checks(
            pulse_checks=[
                {
                    "suite_id": "cadence_check",
                    "boundary_id": CADENCE_BOUNDARY_ID,
                    "binding_mode": "cadence",
                    "checks": [{"check_type": "file_exists", "target": "output.md"}],
                }
            ],
            cadence_policy={"max_tasks_per_pulse": 2},
        )
        executor = self._make_executor_with_pulse(
            mock_registry,
            mock_vault,
            mock_queue,
            mock_squad_profile,
            cycle,
        )
        mock_queue.consume.side_effect = self._consume_side_effect(mock_queue)

        from squadops.cycles.pulse_models import PulseVerificationRecord

        call_count = {"n": 0}

        def pv_side_effect(*args, **kwargs):
            call_count["n"] += 1
            outcome = SuiteOutcome.FAIL if call_count["n"] == 1 else SuiteOutcome.PASS
            return [
                PulseVerificationRecord(
                    suite_id="cadence_check",
                    boundary_id=CADENCE_BOUNDARY_ID,
                    cadence_interval_id=kwargs.get("cadence_interval_id", 1),
                    run_id=kwargs.get("run_id", "run_001"),
                    suite_outcome=outcome,
                )
            ]

        with (
            patch(
                "adapters.cycles.distributed_flow_executor.asyncio.sleep", new_callable=AsyncMock
            ),
            patch(
                "adapters.cycles.distributed_flow_executor.run_pulse_verification",
                side_effect=pv_side_effect,
            ),
        ):
            await executor.execute_run(cycle_id="cyc_001", run_id="run_001")

        statuses = [c.args[1] for c in mock_registry.update_run_status.call_args_list]
        assert statuses[-1] == RunStatus.COMPLETED

    async def test_repair_dispatches_four_task_types(
        self,
        mock_registry,
        mock_vault,
        mock_queue,
        mock_squad_profile,
    ):
        """Repair chain dispatches data.analyze_verification → ... → development.repair."""
        cycle = _cycle_with_pulse_checks(
            [
                {
                    "suite_id": "post_dev_check",
                    "boundary_id": "post_dev",
                    "after_task_types": ["development"],
                    "binding_mode": "milestone",
                    "checks": [{"check_type": "file_exists", "target": "output.md"}],
                }
            ]
        )
        executor = self._make_executor_with_pulse(
            mock_registry,
            mock_vault,
            mock_queue,
            mock_squad_profile,
            cycle,
        )
        mock_queue.consume.side_effect = self._consume_side_effect(mock_queue)

        from squadops.cycles.pulse_models import PulseVerificationRecord

        call_count = {"n": 0}

        def pv_side(*args, **kwargs):
            call_count["n"] += 1
            outcome = SuiteOutcome.FAIL if call_count["n"] == 1 else SuiteOutcome.PASS
            return [
                PulseVerificationRecord(
                    suite_id="post_dev_check",
                    boundary_id="post_dev",
                    cadence_interval_id=kwargs.get("cadence_interval_id", 1),
                    run_id=kwargs.get("run_id", "run_001"),
                    suite_outcome=outcome,
                )
            ]

        with (
            patch(
                "adapters.cycles.distributed_flow_executor.asyncio.sleep", new_callable=AsyncMock
            ),
            patch(
                "adapters.cycles.distributed_flow_executor.run_pulse_verification",
                side_effect=pv_side,
            ),
        ):
            await executor.execute_run(cycle_id="cyc_001", run_id="run_001")

        # Extract repair task types from published messages
        published_types = []
        for call in mock_queue.publish.call_args_list:
            msg_data = json.loads(call.args[1])
            published_types.append(msg_data["payload"]["task_type"])

        expected_repair_types = [
            "data.analyze_verification",
            "governance.root_cause_analysis",
            "strategy.corrective_plan",
            "development.repair",
        ]
        # Repair tasks appear after the 2 plan tasks
        repair_types = published_types[2:6]
        assert repair_types == expected_repair_types

    async def test_verification_context_injected_into_repair_inputs(
        self,
        mock_registry,
        mock_vault,
        mock_queue,
        mock_squad_profile,
    ):
        """Repair envelopes contain verification_context in their inputs."""
        cycle = _cycle_with_pulse_checks(
            [
                {
                    "suite_id": "post_dev_check",
                    "boundary_id": "post_dev",
                    "after_task_types": ["development"],
                    "binding_mode": "milestone",
                    "checks": [{"check_type": "file_exists", "target": "output.md"}],
                }
            ]
        )
        executor = self._make_executor_with_pulse(
            mock_registry,
            mock_vault,
            mock_queue,
            mock_squad_profile,
            cycle,
        )
        mock_queue.consume.side_effect = self._consume_side_effect(mock_queue)

        from squadops.cycles.pulse_models import PulseVerificationRecord

        call_count = {"n": 0}

        def pv_side(*args, **kwargs):
            call_count["n"] += 1
            outcome = SuiteOutcome.FAIL if call_count["n"] == 1 else SuiteOutcome.PASS
            return [
                PulseVerificationRecord(
                    suite_id="post_dev_check",
                    boundary_id="post_dev",
                    cadence_interval_id=kwargs.get("cadence_interval_id", 1),
                    run_id=kwargs.get("run_id", "run_001"),
                    suite_outcome=outcome,
                )
            ]

        with (
            patch(
                "adapters.cycles.distributed_flow_executor.asyncio.sleep", new_callable=AsyncMock
            ),
            patch(
                "adapters.cycles.distributed_flow_executor.run_pulse_verification",
                side_effect=pv_side,
            ),
        ):
            await executor.execute_run(cycle_id="cyc_001", run_id="run_001")

        # Check that the first repair task (index 2) has verification_context in inputs
        repair_call = mock_queue.publish.call_args_list[2]
        msg_data = json.loads(repair_call.args[1])
        inputs = msg_data["payload"]["inputs"]
        assert "prior_outputs" in inputs
        assert "verification_context" in inputs["prior_outputs"]
        assert "post_dev" in inputs["prior_outputs"]["verification_context"]

    async def test_repair_envelopes_carry_boundary_metadata(
        self,
        mock_registry,
        mock_vault,
        mock_queue,
        mock_squad_profile,
    ):
        """Repair envelopes include boundary_id and cadence_interval_id in metadata."""
        cycle = _cycle_with_pulse_checks(
            [
                {
                    "suite_id": "post_dev_check",
                    "boundary_id": "post_dev",
                    "after_task_types": ["development"],
                    "binding_mode": "milestone",
                    "checks": [{"check_type": "file_exists", "target": "output.md"}],
                }
            ]
        )
        executor = self._make_executor_with_pulse(
            mock_registry,
            mock_vault,
            mock_queue,
            mock_squad_profile,
            cycle,
        )
        mock_queue.consume.side_effect = self._consume_side_effect(mock_queue)

        from squadops.cycles.pulse_models import PulseVerificationRecord

        call_count = {"n": 0}

        def pv_side(*args, **kwargs):
            call_count["n"] += 1
            outcome = SuiteOutcome.FAIL if call_count["n"] == 1 else SuiteOutcome.PASS
            return [
                PulseVerificationRecord(
                    suite_id="post_dev_check",
                    boundary_id="post_dev",
                    cadence_interval_id=kwargs.get("cadence_interval_id", 1),
                    run_id=kwargs.get("run_id", "run_001"),
                    suite_outcome=outcome,
                )
            ]

        with (
            patch(
                "adapters.cycles.distributed_flow_executor.asyncio.sleep", new_callable=AsyncMock
            ),
            patch(
                "adapters.cycles.distributed_flow_executor.run_pulse_verification",
                side_effect=pv_side,
            ),
        ):
            await executor.execute_run(cycle_id="cyc_001", run_id="run_001")

        # Check metadata on a repair task envelope (index 2 is first repair task)
        repair_call = mock_queue.publish.call_args_list[2]
        msg_data = json.loads(repair_call.args[1])
        metadata = msg_data["payload"]["metadata"]
        assert metadata["boundary_id"] == "post_dev"
        assert metadata["repair_chain"] is True
        assert metadata["failed_suite_ids"] == ["post_dev_check"]


@pytest.mark.domain_pulse_checks
class TestPulseRepairTelemetry:
    """Telemetry events emitted during repair loop."""

    @staticmethod
    def _make_executor_with_obs(
        mock_registry,
        mock_vault,
        mock_queue,
        mock_squad_profile,
        cycle,
    ):
        from adapters.cycles.distributed_flow_executor import DistributedFlowExecutor

        mock_registry.get_cycle.return_value = cycle
        mock_registry.record_pulse_verification.return_value = mock_registry.get_run.return_value

        obs = MagicMock()
        return DistributedFlowExecutor(
            cycle_registry=mock_registry,
            artifact_vault=mock_vault,
            queue=mock_queue,
            squad_profile=mock_squad_profile,
            task_timeout=5.0,
            llm_observability=obs,
        ), obs

    @staticmethod
    def _consume_side_effect(mock_queue):
        async def _side_effect(queue_name, max_messages=1):
            if not queue_name.startswith("cycle_results_"):
                return []
            last_call = mock_queue.publish.call_args
            if last_call:
                msg_data = json.loads(last_call.args[1])
                task_id = msg_data["payload"]["task_id"]
                return [
                    _make_result_message(
                        task_id=task_id,
                        outputs={"summary": "ok", "artifacts": []},
                        queue_name=queue_name,
                    )
                ]
            return []

        return _side_effect

    async def test_repair_started_event(
        self,
        mock_registry,
        mock_vault,
        mock_queue,
        mock_squad_profile,
    ):
        """pulse_check.repair_started emitted when repair begins."""
        cycle = _cycle_with_pulse_checks(
            [
                {
                    "suite_id": "post_dev_check",
                    "boundary_id": "post_dev",
                    "after_task_types": ["development"],
                    "binding_mode": "milestone",
                    "checks": [{"check_type": "file_exists", "target": "output.md"}],
                }
            ]
        )
        executor, obs = self._make_executor_with_obs(
            mock_registry,
            mock_vault,
            mock_queue,
            mock_squad_profile,
            cycle,
        )
        mock_queue.consume.side_effect = self._consume_side_effect(mock_queue)

        from squadops.cycles.pulse_models import PulseVerificationRecord

        call_count = {"n": 0}

        def pv_side(*, suites, **kwargs):
            call_count["n"] += 1
            outcome = SuiteOutcome.FAIL if call_count["n"] == 1 else SuiteOutcome.PASS
            return [
                PulseVerificationRecord(
                    suite_id="post_dev_check",
                    boundary_id="post_dev",
                    cadence_interval_id=kwargs.get("cadence_interval_id", 1),
                    run_id=kwargs.get("run_id", "run_001"),
                    suite_outcome=outcome,
                )
            ]

        with (
            patch(
                "adapters.cycles.distributed_flow_executor.asyncio.sleep", new_callable=AsyncMock
            ),
            patch(
                "adapters.cycles.distributed_flow_executor.run_pulse_verification",
                side_effect=pv_side,
            ),
        ):
            await executor.execute_run(cycle_id="cyc_001", run_id="run_001")

        events = [call.args[1].name for call in obs.record_event.call_args_list]
        assert "pulse_check.repair_started" in events

    async def test_exhausted_event_emitted(
        self,
        mock_registry,
        mock_vault,
        mock_queue,
        mock_squad_profile,
    ):
        """pulse_check.boundary_decision with EXHAUSTED emitted on exhaustion."""
        cycle = _cycle_with_pulse_checks(
            [
                {
                    "suite_id": "post_dev_check",
                    "boundary_id": "post_dev",
                    "after_task_types": ["development"],
                    "binding_mode": "milestone",
                    "checks": [{"check_type": "file_exists", "target": "output.md"}],
                }
            ]
        )
        executor, obs = self._make_executor_with_obs(
            mock_registry,
            mock_vault,
            mock_queue,
            mock_squad_profile,
            cycle,
        )
        mock_queue.consume.side_effect = self._consume_side_effect(mock_queue)

        from squadops.cycles.pulse_models import PulseVerificationRecord

        def always_fail(*, suites, **kwargs):
            return [
                PulseVerificationRecord(
                    suite_id="post_dev_check",
                    boundary_id="post_dev",
                    cadence_interval_id=kwargs.get("cadence_interval_id", 1),
                    run_id=kwargs.get("run_id", "run_001"),
                    suite_outcome=SuiteOutcome.FAIL,
                )
            ]

        with (
            patch(
                "adapters.cycles.distributed_flow_executor.asyncio.sleep", new_callable=AsyncMock
            ),
            patch(
                "adapters.cycles.distributed_flow_executor.run_pulse_verification",
                side_effect=always_fail,
            ),
        ):
            await executor.execute_run(cycle_id="cyc_001", run_id="run_001")

        # Check for EXHAUSTED decision event
        decision_events = [
            call.args[1]
            for call in obs.record_event.call_args_list
            if call.args[1].name == "pulse_check.boundary_decision"
        ]
        decisions = []
        for evt in decision_events:
            for key, val in evt.attributes:
                if key == "decision":
                    decisions.append(val)
        assert "exhausted" in decisions

    async def test_repair_started_carries_attempt_number(
        self,
        mock_registry,
        mock_vault,
        mock_queue,
        mock_squad_profile,
    ):
        """repair_started event carries repair_attempt number in attributes."""
        cycle = _cycle_with_pulse_checks(
            [
                {
                    "suite_id": "post_dev_check",
                    "boundary_id": "post_dev",
                    "after_task_types": ["development"],
                    "binding_mode": "milestone",
                    "checks": [{"check_type": "file_exists", "target": "output.md"}],
                }
            ]
        )
        executor, obs = self._make_executor_with_obs(
            mock_registry,
            mock_vault,
            mock_queue,
            mock_squad_profile,
            cycle,
        )
        mock_queue.consume.side_effect = self._consume_side_effect(mock_queue)

        from squadops.cycles.pulse_models import PulseVerificationRecord

        def always_fail(*, suites, **kwargs):
            return [
                PulseVerificationRecord(
                    suite_id="post_dev_check",
                    boundary_id="post_dev",
                    cadence_interval_id=kwargs.get("cadence_interval_id", 1),
                    run_id=kwargs.get("run_id", "run_001"),
                    suite_outcome=SuiteOutcome.FAIL,
                )
            ]

        with (
            patch(
                "adapters.cycles.distributed_flow_executor.asyncio.sleep", new_callable=AsyncMock
            ),
            patch(
                "adapters.cycles.distributed_flow_executor.run_pulse_verification",
                side_effect=always_fail,
            ),
        ):
            await executor.execute_run(cycle_id="cyc_001", run_id="run_001")

        # Find repair_started events and check repair_attempt attrs
        repair_events = [
            call.args[1]
            for call in obs.record_event.call_args_list
            if call.args[1].name == "pulse_check.repair_started"
        ]
        assert len(repair_events) == 2  # 2 attempts
        attempts = []
        for evt in repair_events:
            for key, val in evt.attributes:
                if key == "repair_attempt":
                    attempts.append(val)
        assert attempts == [1, 2]

    async def test_repair_started_carries_failed_suite_ids(
        self,
        mock_registry,
        mock_vault,
        mock_queue,
        mock_squad_profile,
    ):
        """repair_started event carries failed_suite_ids in attributes."""
        cycle = _cycle_with_pulse_checks(
            [
                {
                    "suite_id": "post_dev_check",
                    "boundary_id": "post_dev",
                    "after_task_types": ["development"],
                    "binding_mode": "milestone",
                    "checks": [{"check_type": "file_exists", "target": "output.md"}],
                }
            ]
        )
        executor, obs = self._make_executor_with_obs(
            mock_registry,
            mock_vault,
            mock_queue,
            mock_squad_profile,
            cycle,
        )
        mock_queue.consume.side_effect = self._consume_side_effect(mock_queue)

        from squadops.cycles.pulse_models import PulseVerificationRecord

        call_count = {"n": 0}

        def pv_side(*, suites, **kwargs):
            call_count["n"] += 1
            outcome = SuiteOutcome.FAIL if call_count["n"] == 1 else SuiteOutcome.PASS
            return [
                PulseVerificationRecord(
                    suite_id="post_dev_check",
                    boundary_id="post_dev",
                    cadence_interval_id=kwargs.get("cadence_interval_id", 1),
                    run_id=kwargs.get("run_id", "run_001"),
                    suite_outcome=outcome,
                )
            ]

        with (
            patch(
                "adapters.cycles.distributed_flow_executor.asyncio.sleep", new_callable=AsyncMock
            ),
            patch(
                "adapters.cycles.distributed_flow_executor.run_pulse_verification",
                side_effect=pv_side,
            ),
        ):
            await executor.execute_run(cycle_id="cyc_001", run_id="run_001")

        repair_events = [
            call.args[1]
            for call in obs.record_event.call_args_list
            if call.args[1].name == "pulse_check.repair_started"
        ]
        assert len(repair_events) >= 1
        # Check failed_suite_ids is in the event attributes
        found_suite_ids = None
        for key, val in repair_events[0].attributes:
            if key == "failed_suite_ids":
                found_suite_ids = val
        assert found_suite_ids == ["post_dev_check"]

    async def test_boundary_decision_pass_after_repair(
        self,
        mock_registry,
        mock_vault,
        mock_queue,
        mock_squad_profile,
    ):
        """boundary_decision PASS emitted after successful repair."""
        cycle = _cycle_with_pulse_checks(
            [
                {
                    "suite_id": "post_dev_check",
                    "boundary_id": "post_dev",
                    "after_task_types": ["development"],
                    "binding_mode": "milestone",
                    "checks": [{"check_type": "file_exists", "target": "output.md"}],
                }
            ]
        )
        executor, obs = self._make_executor_with_obs(
            mock_registry,
            mock_vault,
            mock_queue,
            mock_squad_profile,
            cycle,
        )
        mock_queue.consume.side_effect = self._consume_side_effect(mock_queue)

        from squadops.cycles.pulse_models import PulseVerificationRecord

        call_count = {"n": 0}

        def pv_side(*, suites, **kwargs):
            call_count["n"] += 1
            outcome = SuiteOutcome.FAIL if call_count["n"] == 1 else SuiteOutcome.PASS
            return [
                PulseVerificationRecord(
                    suite_id="post_dev_check",
                    boundary_id="post_dev",
                    cadence_interval_id=kwargs.get("cadence_interval_id", 1),
                    run_id=kwargs.get("run_id", "run_001"),
                    suite_outcome=outcome,
                )
            ]

        with (
            patch(
                "adapters.cycles.distributed_flow_executor.asyncio.sleep", new_callable=AsyncMock
            ),
            patch(
                "adapters.cycles.distributed_flow_executor.run_pulse_verification",
                side_effect=pv_side,
            ),
        ):
            await executor.execute_run(cycle_id="cyc_001", run_id="run_001")

        # After repair succeeds, boundary_decision with PASS should be emitted
        decision_events = [
            call.args[1]
            for call in obs.record_event.call_args_list
            if call.args[1].name == "pulse_check.boundary_decision"
        ]
        decisions = []
        for evt in decision_events:
            for key, val in evt.attributes:
                if key == "decision":
                    decisions.append(val)
        assert "pass" in decisions

    async def test_repair_tasks_dispatched_to_agent_name_queues(
        self,
        mock_registry,
        mock_vault,
        mock_queue,
        mock_squad_profile,
    ):
        """Repair tasks dispatch to agent-name queues (max_comms, nat_comms), not role queues.

        Verifies the agent_resolver is correctly passed from the profile so that
        repair tasks for role='lead' go to queue='max_comms' (not 'lead_comms'),
        role='strat' goes to 'nat_comms' (not 'strat_comms'), etc.
        """
        cycle = _cycle_with_pulse_checks(
            [
                {
                    "suite_id": "post_dev_check",
                    "boundary_id": "post_dev",
                    "after_task_types": ["development"],
                    "binding_mode": "milestone",
                    "checks": [{"check_type": "file_exists", "target": "output.md"}],
                }
            ]
        )
        executor, obs = self._make_executor_with_obs(
            mock_registry,
            mock_vault,
            mock_queue,
            mock_squad_profile,
            cycle,
        )
        mock_queue.consume.side_effect = self._consume_side_effect(mock_queue)

        from squadops.cycles.pulse_models import PulseVerificationRecord

        call_count = {"n": 0}

        def pv_side(*, suites, **kwargs):
            call_count["n"] += 1
            outcome = SuiteOutcome.FAIL if call_count["n"] == 1 else SuiteOutcome.PASS
            return [
                PulseVerificationRecord(
                    suite_id="post_dev_check",
                    boundary_id="post_dev",
                    cadence_interval_id=kwargs.get("cadence_interval_id", 1),
                    run_id=kwargs.get("run_id", "run_001"),
                    suite_outcome=outcome,
                )
            ]

        with (
            patch(
                "adapters.cycles.distributed_flow_executor.asyncio.sleep", new_callable=AsyncMock
            ),
            patch(
                "adapters.cycles.distributed_flow_executor.run_pulse_verification",
                side_effect=pv_side,
            ),
        ):
            await executor.execute_run(cycle_id="cyc_001", run_id="run_001")

        # Collect all queue names that publish was called with
        published_queues = [call.args[0] for call in mock_queue.publish.call_args_list]

        # Repair tasks should go to agent-name queues, NOT role queues
        assert "lead_comms" not in published_queues, "Should use 'max_comms' not 'lead_comms'"
        assert "strat_comms" not in published_queues, "Should use 'nat_comms' not 'strat_comms'"
        assert "dev_comms" not in published_queues, "Should use 'neo_comms' not 'dev_comms'"

        # Agent-name queues should be present (repair dispatches to max, nat, neo, data-agent)
        assert "max_comms" in published_queues, "Lead repair task should go to max_comms"
        assert "nat_comms" in published_queues, "Strategy repair task should go to nat_comms"
        assert "neo_comms" in published_queues, "Dev repair task should go to neo_comms"
        assert "data-agent_comms" in published_queues, (
            "Data repair task should go to data-agent_comms"
        )


# ---------------------------------------------------------------------------
# SIP-0087: Prefect task-run lifecycle + contextvar scope + heartbeat
# ---------------------------------------------------------------------------


class TestDispatchTaskPrefectLifecycle:
    """Verify _dispatch_task drives the Prefect task-run lifecycle, enters the
    correlation contextvar scope, and spawns the heartbeat."""

    @pytest.fixture
    def envelope(self):
        return TaskEnvelope(
            task_id="task_abc",
            agent_id="neo",
            cycle_id="cyc_001",
            pulse_id="p1",
            project_id="proj_001",
            task_type="development.design",
            correlation_id="corr",
            causation_id="cause",
            trace_id="trace",
            span_id="span",
            metadata={"role": "dev", "capability_id": "dev.design"},
        )

    @pytest.fixture
    def mock_reporter(self):
        reporter = MagicMock()
        reporter.create_task_run = AsyncMock(return_value="tr_new")
        reporter.set_task_run_state = AsyncMock()
        return reporter

    def _build_executor(self, mock_queue, mock_reporter=None):
        from adapters.cycles.distributed_flow_executor import DistributedFlowExecutor

        return DistributedFlowExecutor(
            queue=mock_queue,
            task_timeout=5.0,
            prefect_reporter=mock_reporter,
        )

    def _wire_success_reply(self, mock_queue, task_id: str):
        call_count = 0

        async def consume_side_effect(queue_name, max_messages=1):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return [
                    _make_result_message(
                        task_id=task_id,
                        outputs={"summary": "ok", "artifacts": []},
                        queue_name=queue_name,
                    )
                ]
            return []

        mock_queue.consume.side_effect = consume_side_effect

    async def test_creates_task_run_and_sets_running_when_prefect_enabled(
        self, mock_queue, mock_reporter, envelope
    ):
        self._wire_success_reply(mock_queue, envelope.task_id)
        executor = self._build_executor(mock_queue, mock_reporter)

        with patch(
            "adapters.cycles.distributed_flow_executor.asyncio.sleep",
            new_callable=AsyncMock,
        ):
            await executor._dispatch_task(envelope, "run_001", flow_run_id="fr_abc")

        mock_reporter.create_task_run.assert_awaited_once_with(
            "fr_abc", "task_abc", "dev: development.design"
        )
        mock_reporter.set_task_run_state.assert_awaited_once_with(
            "tr_new", "RUNNING", "Running"
        )

    async def test_no_prefect_calls_when_reporter_missing(
        self, mock_queue, envelope
    ):
        self._wire_success_reply(mock_queue, envelope.task_id)
        executor = self._build_executor(mock_queue, mock_reporter=None)

        with patch(
            "adapters.cycles.distributed_flow_executor.asyncio.sleep",
            new_callable=AsyncMock,
        ):
            result = await executor._dispatch_task(
                envelope, "run_001", flow_run_id="fr_abc"
            )

        assert result.status == "SUCCEEDED"

    async def test_no_prefect_calls_when_flow_run_id_missing(
        self, mock_queue, mock_reporter, envelope
    ):
        self._wire_success_reply(mock_queue, envelope.task_id)
        executor = self._build_executor(mock_queue, mock_reporter)

        with patch(
            "adapters.cycles.distributed_flow_executor.asyncio.sleep",
            new_callable=AsyncMock,
        ):
            await executor._dispatch_task(envelope, "run_001", flow_run_id=None)

        mock_reporter.create_task_run.assert_not_awaited()
        mock_reporter.set_task_run_state.assert_not_awaited()

    async def test_skips_creation_when_task_run_id_preallocated(
        self, mock_queue, mock_reporter, envelope
    ):
        # Sequential path pre-creates the task_run (so TASK_DISPATCHED can
        # emit it) and passes task_run_id in. _dispatch_task must not create
        # a second one.
        self._wire_success_reply(mock_queue, envelope.task_id)
        executor = self._build_executor(mock_queue, mock_reporter)

        with patch(
            "adapters.cycles.distributed_flow_executor.asyncio.sleep",
            new_callable=AsyncMock,
        ):
            await executor._dispatch_task(
                envelope, "run_001", flow_run_id="fr_abc", task_run_id="tr_preallocated"
            )

        mock_reporter.create_task_run.assert_not_awaited()
        mock_reporter.set_task_run_state.assert_not_awaited()

    async def test_published_envelope_carries_run_ids(
        self, mock_queue, mock_reporter, envelope
    ):
        """SIP-0087 B1: dispatched envelope on the wire carries flow_run_id /
        task_run_id so the agent can scope its handler logs to the right
        Prefect task pane."""
        published_payload: dict[str, object] = {}

        async def capture_publish(_queue_name, body):
            published_payload.update(json.loads(body)["payload"])

        mock_queue.publish.side_effect = capture_publish
        self._wire_success_reply(mock_queue, envelope.task_id)
        executor = self._build_executor(mock_queue, mock_reporter)

        with patch(
            "adapters.cycles.distributed_flow_executor.asyncio.sleep",
            new_callable=AsyncMock,
        ):
            await executor._dispatch_task(
                envelope, "run_001", flow_run_id="fr_abc", task_run_id="tr_123"
            )

        assert published_payload["flow_run_id"] == "fr_abc"
        assert published_payload["task_run_id"] == "tr_123"

    async def test_published_envelope_run_ids_empty_when_prefect_disabled(
        self, mock_queue, envelope
    ):
        """No Prefect → run IDs serialize as empty strings (not nulls)."""
        published_payload: dict[str, object] = {}

        async def capture_publish(_queue_name, body):
            published_payload.update(json.loads(body)["payload"])

        mock_queue.publish.side_effect = capture_publish
        self._wire_success_reply(mock_queue, envelope.task_id)
        executor = self._build_executor(mock_queue, mock_reporter=None)

        with patch(
            "adapters.cycles.distributed_flow_executor.asyncio.sleep",
            new_callable=AsyncMock,
        ):
            await executor._dispatch_task(envelope, "run_001")

        assert published_payload["flow_run_id"] == ""
        assert published_payload["task_run_id"] == ""

    async def test_scopes_correlation_context_during_publish(
        self, mock_queue, mock_reporter, envelope
    ):
        """The publish coroutine must see the active CorrelationContext so
        any logs emitted during dispatch land in the right Prefect pane."""
        from squadops.telemetry.context import get_correlation_context

        seen: dict[str, object] = {}

        async def capture_ctx(*args, **kwargs):
            ctx = get_correlation_context()
            seen["cycle_id"] = ctx.cycle_id if ctx else None
            seen["flow_run_id"] = ctx.flow_run_id if ctx else None
            seen["task_run_id"] = ctx.task_run_id if ctx else None

        mock_queue.publish.side_effect = capture_ctx
        self._wire_success_reply(mock_queue, envelope.task_id)
        executor = self._build_executor(mock_queue, mock_reporter)

        with patch(
            "adapters.cycles.distributed_flow_executor.asyncio.sleep",
            new_callable=AsyncMock,
        ):
            await executor._dispatch_task(
                envelope, "run_001", flow_run_id="fr_abc", task_run_id="tr_123"
            )

        assert seen == {
            "cycle_id": "cyc_001",
            "flow_run_id": "fr_abc",
            "task_run_id": "tr_123",
        }
        # Context must be cleared after dispatch returns.
        assert get_correlation_context() is None

    async def test_task_heartbeat_logs_periodically_under_contextvar_scope(
        self, mock_queue, envelope, caplog
    ):
        """``_task_heartbeat`` emits an INFO line per interval and carries
        the live correlation context so records are tagged for Prefect."""
        import logging as stdlog

        import adapters.cycles.distributed_flow_executor as dfe
        from squadops.telemetry.context import (
            get_correlation_context,
            use_correlation_context,
            use_run_ids,
        )
        from squadops.telemetry.models import CorrelationContext

        executor = self._build_executor(mock_queue)

        seen_ids: list[tuple[str | None, str | None]] = []
        real_sleep = asyncio.sleep

        async def capturing_sleep(_interval: float) -> None:
            ctx = get_correlation_context()
            seen_ids.append(
                (ctx.flow_run_id if ctx else None, ctx.task_run_id if ctx else None)
            )
            # Let the event loop advance; real sleep avoids tight-looping.
            await real_sleep(0)

        with (
            patch.object(dfe.asyncio, "sleep", capturing_sleep),
            caplog.at_level(stdlog.INFO, logger=dfe.__name__),
        ):
            base = CorrelationContext(cycle_id="cyc_001")
            with use_correlation_context(base), use_run_ids(
                flow_run_id="fr_abc", task_run_id="tr_123"
            ):
                hb = asyncio.create_task(
                    executor._task_heartbeat(envelope, interval=0.01)
                )
                # Yield a few times so the heartbeat can iterate.
                for _ in range(5):
                    await real_sleep(0)
                hb.cancel()
                try:
                    await hb
                except asyncio.CancelledError:
                    pass

        messages = [
            r.getMessage() for r in caplog.records if "task_heartbeat" in r.getMessage()
        ]
        assert messages, "expected at least one task_heartbeat log line"
        first = messages[0]
        assert "capability_id=dev.design" in first
        assert "task_id=task_abc" in first
        # Heartbeat coroutine saw the active flow/task run IDs via contextvar
        # inheritance at create_task time.
        assert ("fr_abc", "tr_123") in seen_ids

    async def test_dispatch_task_cancels_heartbeat_on_return(
        self, mock_queue, mock_reporter, envelope
    ):
        """After ``_dispatch_task`` returns, no orphan heartbeat task should
        remain on the event loop."""
        self._wire_success_reply(mock_queue, envelope.task_id)
        executor = self._build_executor(mock_queue, mock_reporter)

        with patch(
            "adapters.cycles.distributed_flow_executor.asyncio.sleep",
            new_callable=AsyncMock,
        ):
            await executor._dispatch_task(
                envelope, "run_001", flow_run_id="fr_abc", task_run_id="tr_123"
            )

        leftover = [
            t
            for t in asyncio.all_tasks()
            if t.get_name().startswith("prefect-heartbeat-") and not t.done()
        ]
        assert leftover == []

