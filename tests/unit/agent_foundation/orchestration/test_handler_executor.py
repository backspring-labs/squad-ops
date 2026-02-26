"""Unit tests for HandlerExecutor.

Tests capability execution via handlers.
Part of SIP-0.8.8 Phase 6.
"""

from unittest.mock import MagicMock

import pytest

from squadops.agents.base import PortsBundle
from squadops.agents.skills.registry import SkillRegistry
from squadops.capabilities.handlers.base import CapabilityHandler, HandlerEvidence, HandlerResult
from squadops.orchestration.handler_executor import HandlerExecutor
from squadops.orchestration.handler_registry import HandlerRegistry
from squadops.tasks.models import TaskEnvelope


class MockHandler(CapabilityHandler):
    """Mock handler for testing."""

    def __init__(
        self,
        name: str = "mock_handler",
        capability_id: str = "mock.capability",
        success: bool = True,
        outputs: dict = None,
        error: str = None,
    ):
        self._name = name
        self._capability_id = capability_id
        self._success = success
        self._outputs = outputs or {}
        self._error = error

    @property
    def name(self) -> str:
        return self._name

    @property
    def capability_id(self) -> str:
        return self._capability_id

    def validate_inputs(self, inputs, contract=None):
        if self._capability_id == "mock.requires_input" and "required" not in inputs:
            return ["'required' is required"]
        return []

    async def handle(self, context, inputs):
        evidence = HandlerEvidence.create(
            handler_name=self.name,
            capability_id=self.capability_id,
            duration_ms=10.0,
        )
        return HandlerResult(
            success=self._success,
            outputs=self._outputs,
            _evidence=evidence,
            error=self._error,
        )


@pytest.fixture
def mock_ports():
    """Create mock ports."""
    return PortsBundle(
        llm=MagicMock(),
        memory=MagicMock(),
        prompt_service=MagicMock(),
        queue=MagicMock(),
        metrics=MagicMock(),
        events=MagicMock(),
        filesystem=MagicMock(),
    )


@pytest.fixture
def skill_registry():
    """Create empty skill registry."""
    return SkillRegistry()


@pytest.fixture
def handler_registry():
    """Create handler registry with mock handler."""
    registry = HandlerRegistry()
    registry.register(
        MockHandler(outputs={"result": "success"}),
        roles=("lead",),
    )
    return registry


@pytest.fixture
def executor(handler_registry, skill_registry, mock_ports):
    """Create handler executor."""
    return HandlerExecutor(
        executor_id="test-executor",
        handler_registry=handler_registry,
        skill_registry=skill_registry,
        ports=mock_ports,
    )


def create_envelope(
    task_type: str = "mock.capability",
    inputs: dict = None,
    task_id: str = "task-1",
) -> TaskEnvelope:
    """Create test envelope."""
    return TaskEnvelope(
        task_id=task_id,
        agent_id="test-agent",
        cycle_id="cycle-1",
        pulse_id="pulse-1",
        project_id="project-1",
        task_type=task_type,
        inputs=inputs or {},
        correlation_id="corr-1",
        causation_id="cause-1",
        trace_id="trace-1",
        span_id="span-1",
    )


class TestHandlerExecutor:
    """Tests for HandlerExecutor."""

    def test_executor_id(self, executor):
        """Should return executor ID."""
        assert executor.executor_id == "test-executor"

    @pytest.mark.asyncio
    async def test_execute_success(self, executor):
        """Should execute successfully."""
        envelope = create_envelope()

        result = await executor.execute(envelope)

        assert result.status == "SUCCEEDED"
        assert result.outputs["result"] == "success"
        assert result.task_id == "task-1"

    @pytest.mark.asyncio
    async def test_execute_handler_not_found(self, executor):
        """Should fail when handler not found."""
        envelope = create_envelope(task_type="nonexistent.capability")

        result = await executor.execute(envelope)

        assert result.status == "FAILED"
        assert "No handler for capability" in result.error

    @pytest.mark.asyncio
    async def test_execute_validation_failure(self, handler_registry, skill_registry, mock_ports):
        """Should fail on validation error."""
        handler_registry.register(
            MockHandler(capability_id="mock.requires_input"),
            allow_override=True,
        )
        executor = HandlerExecutor(
            executor_id="test",
            handler_registry=handler_registry,
            skill_registry=skill_registry,
            ports=mock_ports,
        )
        envelope = create_envelope(task_type="mock.requires_input", inputs={})

        result = await executor.execute(envelope)

        assert result.status == "FAILED"
        assert "Validation failed" in result.error

    @pytest.mark.asyncio
    async def test_execute_handler_failure(self, handler_registry, skill_registry, mock_ports):
        """Should handle handler failure."""
        handler_registry.register(
            MockHandler(
                capability_id="mock.failing",
                success=False,
                error="Handler failed",
            ),
        )
        executor = HandlerExecutor(
            executor_id="test",
            handler_registry=handler_registry,
            skill_registry=skill_registry,
            ports=mock_ports,
        )
        envelope = create_envelope(task_type="mock.failing")

        result = await executor.execute(envelope)

        assert result.status == "FAILED"
        assert result.error == "Handler failed"

    @pytest.mark.asyncio
    async def test_execute_with_evidence(self, executor):
        """Should include execution evidence."""
        envelope = create_envelope()

        result = await executor.execute(envelope)

        assert result.execution_evidence is not None
        assert "handler_name" in result.execution_evidence
        assert "duration_ms" in result.execution_evidence

    @pytest.mark.asyncio
    async def test_health(self, executor):
        """Should return health status."""
        health = await executor.health()

        assert health["status"] == "healthy"
        assert health["executor_id"] == "test-executor"
        assert "handlers_registered" in health
        assert "skills_registered" in health

    def test_can_execute_registered(self, executor):
        """Should return True for registered capability."""
        assert executor.can_execute("mock.capability", "lead") is True

    def test_can_execute_not_registered(self, executor):
        """Should return False for unregistered capability."""
        assert executor.can_execute("nonexistent", "lead") is False


class TestHandlerExecutorTimeout:
    """Tests for timeout handling."""

    @pytest.mark.asyncio
    async def test_execute_timeout(self, handler_registry, skill_registry, mock_ports):
        """Should raise TimeoutError on timeout."""
        import asyncio

        class SlowHandler(CapabilityHandler):
            @property
            def name(self):
                return "slow"

            @property
            def capability_id(self):
                return "mock.slow"

            async def handle(self, context, inputs):
                await asyncio.sleep(10)  # Slow operation
                evidence = HandlerEvidence.create(
                    handler_name=self.name,
                    capability_id=self.capability_id,
                    duration_ms=10000,
                )
                return HandlerResult(success=True, outputs={}, _evidence=evidence)

        handler_registry.register(SlowHandler())
        executor = HandlerExecutor(
            executor_id="test",
            handler_registry=handler_registry,
            skill_registry=skill_registry,
            ports=mock_ports,
        )
        envelope = create_envelope(task_type="mock.slow")

        with pytest.raises(TimeoutError):
            await executor.execute(envelope, timeout_seconds=0.1)
