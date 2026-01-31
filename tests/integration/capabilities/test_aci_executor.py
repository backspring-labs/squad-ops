"""
Integration tests for ACICapabilityExecutor.

These tests require RabbitMQ to be running. Mark with @pytest.mark.rabbitmq
for conditional execution.
"""

import asyncio
import json
import pytest
from unittest.mock import AsyncMock, MagicMock

from adapters.capabilities.aci_executor import ACICapabilityExecutor, ExecutorError
from squadops.ports.comms.queue import QueuePort
from squadops.comms.queue_message import QueueMessage
from agents.tasks.models import TaskEnvelope, TaskResult


@pytest.fixture
def mock_queue():
    """Create a mock QueuePort for testing."""
    queue = MagicMock(spec=QueuePort)
    queue.publish = AsyncMock()
    queue.consume = AsyncMock(return_value=[])
    queue.ack = AsyncMock()
    queue.retry = AsyncMock()
    queue.health = AsyncMock(return_value={"status": "healthy"})
    return queue


@pytest.fixture
def executor(mock_queue):
    """Create an ACICapabilityExecutor with mock queue."""
    return ACICapabilityExecutor(
        queue=mock_queue,
        response_queue_prefix="test_responses",
        default_timeout_seconds=5,
    )


@pytest.fixture
def sample_envelope():
    """Create a sample TaskEnvelope."""
    return TaskEnvelope(
        task_id="test-task-123",
        agent_id="data",
        cycle_id="cycle-456",
        pulse_id="pulse-789",
        project_id="project-001",
        task_type="data.test_capability",
        inputs={"param": "value"},
        correlation_id="corr-123",
        causation_id="cause-456",
        trace_id="trace-789",
        span_id="span-012",
    )


class TestACIExecutorBasics:
    """Basic tests for ACICapabilityExecutor."""

    def test_executor_id(self, executor):
        """Executor has a unique ID."""
        assert executor.executor_id.startswith("aci-executor-")
        assert len(executor.executor_id) > len("aci-executor-")

    @pytest.mark.asyncio
    async def test_health_check(self, executor, mock_queue):
        """Health check returns queue status."""
        health = await executor.health()

        assert health["status"] == "healthy"
        assert "executor_id" in health
        assert "queue_status" in health
        mock_queue.health.assert_called_once()

    def test_can_execute_always_true(self, executor):
        """ACI executor can execute any capability."""
        assert executor.can_execute("any.capability", "any_role") is True
        assert executor.can_execute("data.test", "data") is True


class TestTaskExecution:
    """Tests for task execution flow."""

    @pytest.mark.asyncio
    async def test_execute_publishes_to_correct_queue(
        self, executor, mock_queue, sample_envelope
    ):
        """Execute publishes TaskEnvelope to agent queue."""
        # Simulate immediate response
        response_message = MagicMock(spec=QueueMessage)
        response_message.payload = json.dumps({
            "task_id": sample_envelope.task_id,
            "status": "SUCCEEDED",
            "outputs": {"result": "success"},
        })

        mock_queue.consume.return_value = [response_message]

        result = await executor.execute(sample_envelope, timeout_seconds=2)

        # Verify publish was called with correct queue
        mock_queue.publish.assert_called_once()
        call_args = mock_queue.publish.call_args
        assert call_args.kwargs["queue_name"] == "agent.data.tasks"

        # Verify envelope was serialized
        payload = json.loads(call_args.kwargs["payload"])
        assert payload["task_id"] == sample_envelope.task_id
        assert "response_queue" in payload["metadata"]

    @pytest.mark.asyncio
    async def test_execute_returns_result(
        self, executor, mock_queue, sample_envelope
    ):
        """Execute returns TaskResult from response queue."""
        response_message = MagicMock(spec=QueueMessage)
        response_message.payload = json.dumps({
            "task_id": sample_envelope.task_id,
            "status": "SUCCEEDED",
            "outputs": {"key": "value"},
        })

        mock_queue.consume.return_value = [response_message]

        result = await executor.execute(sample_envelope)

        assert isinstance(result, TaskResult)
        assert result.task_id == sample_envelope.task_id
        assert result.status == "SUCCEEDED"
        assert result.outputs == {"key": "value"}

    @pytest.mark.asyncio
    async def test_execute_handles_failed_result(
        self, executor, mock_queue, sample_envelope
    ):
        """Execute handles FAILED status from agent."""
        response_message = MagicMock(spec=QueueMessage)
        response_message.payload = json.dumps({
            "task_id": sample_envelope.task_id,
            "status": "FAILED",
            "error": "Task execution failed",
        })

        mock_queue.consume.return_value = [response_message]

        result = await executor.execute(sample_envelope)

        assert result.status == "FAILED"
        assert result.error == "Task execution failed"

    @pytest.mark.asyncio
    async def test_execute_acknowledges_message(
        self, executor, mock_queue, sample_envelope
    ):
        """Execute acknowledges the response message."""
        response_message = MagicMock(spec=QueueMessage)
        response_message.payload = json.dumps({
            "task_id": sample_envelope.task_id,
            "status": "SUCCEEDED",
            "outputs": {},
        })

        mock_queue.consume.return_value = [response_message]

        await executor.execute(sample_envelope)

        mock_queue.ack.assert_called_once_with(response_message)


class TestTimeoutHandling:
    """Tests for timeout handling."""

    @pytest.mark.asyncio
    async def test_execute_timeout(self, executor, mock_queue, sample_envelope):
        """Execute raises TimeoutError when no response received."""
        # Never return a message
        mock_queue.consume.return_value = []

        with pytest.raises(TimeoutError) as exc:
            await executor.execute(sample_envelope, timeout_seconds=0.1)

        assert "timed out" in str(exc.value).lower()

    @pytest.mark.asyncio
    async def test_timeout_uses_provided_value(
        self, mock_queue, sample_envelope
    ):
        """Execute uses provided timeout value."""
        executor = ACICapabilityExecutor(
            queue=mock_queue,
            default_timeout_seconds=100,  # Long default
        )

        mock_queue.consume.return_value = []

        with pytest.raises(TimeoutError):
            # Short explicit timeout should override
            await executor.execute(sample_envelope, timeout_seconds=0.1)


class TestErrorHandling:
    """Tests for error handling."""

    @pytest.mark.asyncio
    async def test_invalid_json_response_ignored(
        self, executor, mock_queue, sample_envelope
    ):
        """Invalid JSON in response is ignored, waits for valid response."""
        bad_message = MagicMock(spec=QueueMessage)
        bad_message.payload = "not valid json"

        good_message = MagicMock(spec=QueueMessage)
        good_message.payload = json.dumps({
            "task_id": sample_envelope.task_id,
            "status": "SUCCEEDED",
            "outputs": {},
        })

        # First call returns bad message, second returns good
        mock_queue.consume.side_effect = [[bad_message], [good_message]]

        result = await executor.execute(sample_envelope, timeout_seconds=2)

        assert result.status == "SUCCEEDED"
        # Bad message should be acknowledged (discarded)
        assert mock_queue.ack.call_count == 2

    @pytest.mark.asyncio
    async def test_wrong_task_id_retried(
        self, executor, mock_queue, sample_envelope
    ):
        """Response with wrong task_id is retried."""
        wrong_message = MagicMock(spec=QueueMessage)
        wrong_message.payload = json.dumps({
            "task_id": "wrong-task-id",
            "status": "SUCCEEDED",
            "outputs": {},
        })

        correct_message = MagicMock(spec=QueueMessage)
        correct_message.payload = json.dumps({
            "task_id": sample_envelope.task_id,
            "status": "SUCCEEDED",
            "outputs": {},
        })

        mock_queue.consume.side_effect = [[wrong_message], [correct_message]]

        result = await executor.execute(sample_envelope, timeout_seconds=2)

        # Wrong message should be retried
        mock_queue.retry.assert_called_once()
        assert result.task_id == sample_envelope.task_id


class TestResponseQueueNaming:
    """Tests for response queue naming."""

    @pytest.mark.asyncio
    async def test_response_queue_includes_task_id(
        self, executor, mock_queue, sample_envelope
    ):
        """Response queue name includes task_id."""
        response_message = MagicMock(spec=QueueMessage)
        response_message.payload = json.dumps({
            "task_id": sample_envelope.task_id,
            "status": "SUCCEEDED",
            "outputs": {},
        })

        mock_queue.consume.return_value = [response_message]

        await executor.execute(sample_envelope)

        # Check consume was called with correct queue
        consume_call = mock_queue.consume.call_args
        assert sample_envelope.task_id in consume_call.kwargs["queue_name"]

    @pytest.mark.asyncio
    async def test_response_queue_uses_prefix(self, mock_queue, sample_envelope):
        """Response queue uses configured prefix."""
        executor = ACICapabilityExecutor(
            queue=mock_queue,
            response_queue_prefix="custom_prefix",
        )

        response_message = MagicMock(spec=QueueMessage)
        response_message.payload = json.dumps({
            "task_id": sample_envelope.task_id,
            "status": "SUCCEEDED",
            "outputs": {},
        })

        mock_queue.consume.return_value = [response_message]

        await executor.execute(sample_envelope, timeout_seconds=1)

        consume_call = mock_queue.consume.call_args
        assert consume_call.kwargs["queue_name"].startswith("custom_prefix.")
