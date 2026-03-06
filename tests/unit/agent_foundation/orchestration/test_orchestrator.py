"""Unit tests for AgentOrchestrator.

Tests multi-agent coordination and task routing.
Part of SIP-0.8.8 Phase 6.
"""

from unittest.mock import MagicMock

import pytest

from squadops.agents.base import PortsBundle
from squadops.agents.skills.registry import SkillRegistry
from squadops.capabilities.handlers.base import CapabilityHandler, HandlerEvidence, HandlerResult
from squadops.orchestration.handler_registry import HandlerRegistry
from squadops.orchestration.orchestrator import AgentOrchestrator
from squadops.tasks.models import TaskEnvelope


class MockHandler(CapabilityHandler):
    """Mock handler for testing."""

    def __init__(self, capability_id: str, outputs: dict = None):
        self._capability_id = capability_id
        self._outputs = outputs or {}

    @property
    def name(self) -> str:
        return f"handler_{self._capability_id}"

    @property
    def capability_id(self) -> str:
        return self._capability_id

    async def handle(self, context, inputs):
        evidence = HandlerEvidence.create(
            handler_name=self.name,
            capability_id=self.capability_id,
            duration_ms=5.0,
        )
        return HandlerResult(
            success=True,
            outputs=self._outputs,
            _evidence=evidence,
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
    """Create handler registry with test handlers."""
    registry = HandlerRegistry()
    registry.register(
        MockHandler("governance.task_analysis", {"summary": "test"}),
        roles=("lead",),
    )
    registry.register(
        MockHandler("development.code_generation", {"code": "test code"}),
        roles=("dev",),
    )
    registry.register(
        MockHandler("qa.validation", {"valid": True}),
        roles=("qa",),
    )
    return registry


@pytest.fixture
def orchestrator(handler_registry, skill_registry, mock_ports):
    """Create orchestrator."""
    return AgentOrchestrator(
        handler_registry=handler_registry,
        skill_registry=skill_registry,
        ports=mock_ports,
    )


def create_envelope(
    task_type: str,
    agent_id: str = "test-agent",
    inputs: dict = None,
) -> TaskEnvelope:
    """Create test envelope."""
    return TaskEnvelope(
        task_id=f"task-{task_type}",
        agent_id=agent_id,
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


class TestTaskRouting:
    """Tests for task routing logic."""

    def test_route_governance_task(self, orchestrator):
        """Should route governance tasks to lead."""
        envelope = create_envelope("governance.task_analysis")

        routing = orchestrator.route_task(envelope)

        assert routing.target_role == "lead"
        assert routing.capability_id == "governance.task_analysis"

    def test_route_development_task(self, orchestrator):
        """Should route development tasks to dev."""
        envelope = create_envelope("development.code_generation")

        routing = orchestrator.route_task(envelope)

        assert routing.target_role == "dev"

    def test_route_qa_task(self, orchestrator):
        """Should route QA tasks to qa."""
        envelope = create_envelope("qa.validation")

        routing = orchestrator.route_task(envelope)

        assert routing.target_role == "qa"

    def test_route_unknown_to_lead(self, orchestrator):
        """Should route unknown tasks to lead."""
        envelope = create_envelope("unknown.task")

        routing = orchestrator.route_task(envelope)

        assert routing.target_role == "lead"
        assert "default" in routing.reason


class TestTaskSubmission:
    """Tests for task submission."""

    @pytest.mark.asyncio
    async def test_submit_task_success(self, orchestrator):
        """Should execute task successfully."""
        envelope = create_envelope("governance.task_analysis")

        result = await orchestrator.submit_task(envelope)

        assert result.status == "SUCCEEDED"
        assert result.outputs["summary"] == "test"

    @pytest.mark.asyncio
    async def test_submit_task_handler_not_found(self, orchestrator):
        """Should fail for unknown capability."""
        envelope = create_envelope("nonexistent.capability")

        result = await orchestrator.submit_task(envelope)

        assert result.status == "FAILED"
        assert "No handler" in result.error

    @pytest.mark.asyncio
    async def test_submit_batch(self, orchestrator):
        """Should execute batch of tasks."""
        envelopes = [
            create_envelope("governance.task_analysis"),
            create_envelope("development.code_generation"),
        ]

        results = await orchestrator.submit_batch(envelopes)

        assert len(results) == 2
        assert results[0].status == "SUCCEEDED"
        assert results[1].status == "SUCCEEDED"

    @pytest.mark.asyncio
    async def test_submit_batch_fail_fast(self, orchestrator):
        """Should skip remaining on failure."""
        envelopes = [
            create_envelope("nonexistent.capability"),  # Will fail
            create_envelope("governance.task_analysis"),  # Should be skipped
        ]

        results = await orchestrator.submit_batch(envelopes)

        assert len(results) == 2
        assert results[0].status == "FAILED"
        assert results[1].status == "SKIPPED"

    @pytest.mark.asyncio
    async def test_active_tasks_tracking(self, orchestrator):
        """Should track active tasks during execution."""
        # Before submission
        assert orchestrator.get_active_tasks() == []

        # After submission (synchronous check not possible, just verify method)
        envelope = create_envelope("governance.task_analysis")
        await orchestrator.submit_task(envelope)

        # After completion
        assert orchestrator.get_active_tasks() == []


class TestOrchestratorCapabilities:
    """Tests for capability discovery."""

    def test_get_available_capabilities(self, orchestrator):
        """Should list all capabilities."""
        caps = orchestrator.get_available_capabilities()

        assert len(caps) == 3
        assert "governance.task_analysis" in caps
        assert "development.code_generation" in caps
        assert "qa.validation" in caps

    def test_get_capabilities_by_role(self, orchestrator):
        """Should filter by role."""
        lead_caps = orchestrator.get_available_capabilities(role="lead")
        dev_caps = orchestrator.get_available_capabilities(role="dev")

        assert "governance.task_analysis" in lead_caps
        assert "development.code_generation" in dev_caps
        assert "governance.task_analysis" not in dev_caps


class TestHealthCheck:
    """Tests for health check."""

    @pytest.mark.asyncio
    async def test_health_check(self, orchestrator):
        """Should return health status."""
        health = await orchestrator.health_check()

        assert health["status"] == "healthy"
        assert health["capabilities"] == 3
        assert "executor" in health


class TestEnvelopeCreation:
    """Tests for envelope creation helper."""

    def test_create_envelope(self, orchestrator):
        """Should create valid envelope."""
        envelope = orchestrator.create_envelope(
            task_type="test.task",
            inputs={"key": "value"},
            metadata={"source": "test"},
        )

        assert envelope.task_type == "test.task"
        assert envelope.inputs == {"key": "value"}
        assert envelope.metadata == {"source": "test"}
        assert envelope.task_id.startswith("task-")
        assert envelope.cycle_id.startswith("cycle-")

    def test_create_envelope_with_explicit_ids(self, orchestrator):
        """Should respect explicit IDs."""
        envelope = orchestrator.create_envelope(
            task_type="test.task",
            inputs={},
            agent_id="specific-agent",
            cycle_id="specific-cycle",
        )

        assert envelope.agent_id == "specific-agent"
        assert envelope.cycle_id == "specific-cycle"


class TestOrchestratorCallSiteBoundary:
    """SIP-0061: Orchestrator MUST NOT call record_generation."""

    @pytest.mark.asyncio
    async def test_orchestrator_does_not_call_record_generation(
        self, handler_registry, skill_registry, mock_ports
    ):
        """Orchestrator lifecycle code never calls record_generation."""
        mock_obs = MagicMock()
        orchestrator = AgentOrchestrator(
            handler_registry=handler_registry,
            skill_registry=skill_registry,
            ports=mock_ports,
            llm_observability=mock_obs,
        )
        envelopes = [create_envelope("governance.task_analysis")]
        await orchestrator.submit_batch(envelopes)

        mock_obs.record_generation.assert_not_called()
