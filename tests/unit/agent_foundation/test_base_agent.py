"""Unit tests for BaseAgent and PortsBundle.

Tests the agent foundation from SIP-0.8.8.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock

from squadops.agents.base import BaseAgent, PortsBundle
from squadops.tasks.models import TaskEnvelope, TaskResult


class ConcreteAgent(BaseAgent):
    """Concrete implementation for testing."""

    ROLE_ID = "test"

    async def handle_task(self, envelope: TaskEnvelope) -> TaskResult:
        """Simple task handler for testing."""
        return TaskResult(
            task_id=envelope.task_id,
            status="completed",
            outputs={"handled": True},
        )


@pytest.fixture
def mock_ports():
    """Create mock ports for testing."""
    return {
        "llm": MagicMock(),
        "memory": MagicMock(),
        "prompt_service": MagicMock(),
        "queue": MagicMock(),
        "metrics": MagicMock(),
        "events": MagicMock(),
        "filesystem": MagicMock(),
    }


class TestPortsBundle:
    """Tests for PortsBundle."""

    def test_bundle_is_frozen(self, mock_ports):
        """Bundle should be immutable."""
        bundle = PortsBundle(**mock_ports)
        with pytest.raises(AttributeError):
            bundle.llm = MagicMock()

    def test_bundle_stores_all_ports(self, mock_ports):
        """Bundle should store all ports."""
        bundle = PortsBundle(**mock_ports)
        assert bundle.llm is mock_ports["llm"]
        assert bundle.memory is mock_ports["memory"]
        assert bundle.prompt_service is mock_ports["prompt_service"]
        assert bundle.queue is mock_ports["queue"]
        assert bundle.metrics is mock_ports["metrics"]
        assert bundle.events is mock_ports["events"]
        assert bundle.filesystem is mock_ports["filesystem"]


class TestBaseAgent:
    """Tests for BaseAgent."""

    def test_agent_stores_identity(self, mock_ports):
        """Agent should store agent_id and role_id."""
        agent = ConcreteAgent(agent_id="agent-1", **mock_ports)
        assert agent.agent_id == "agent-1"
        assert agent.role_id == "test"

    def test_agent_uses_custom_role_id(self, mock_ports):
        """Agent should use provided role_id over class default."""
        agent = ConcreteAgent(agent_id="agent-1", role_id="custom", **mock_ports)
        assert agent.role_id == "custom"

    def test_agent_exposes_ports(self, mock_ports):
        """Agent should expose port accessors."""
        agent = ConcreteAgent(agent_id="agent-1", **mock_ports)
        assert agent.llm is mock_ports["llm"]
        assert agent.memory is mock_ports["memory"]
        assert agent.prompt_service is mock_ports["prompt_service"]
        assert agent.queue is mock_ports["queue"]
        assert agent.metrics is mock_ports["metrics"]
        assert agent.events is mock_ports["events"]
        assert agent.filesystem is mock_ports["filesystem"]

    def test_agent_exposes_ports_bundle(self, mock_ports):
        """Agent should expose ports bundle."""
        agent = ConcreteAgent(agent_id="agent-1", **mock_ports)
        bundle = agent.ports
        assert isinstance(bundle, PortsBundle)
        assert bundle.llm is mock_ports["llm"]

    def test_agent_stores_skill_registry(self, mock_ports):
        """Agent should store skill registry if provided."""
        registry = MagicMock()
        agent = ConcreteAgent(
            agent_id="agent-1",
            skill_registry=registry,
            **mock_ports,
        )
        assert agent.skill_registry is registry

    def test_agent_skill_registry_optional(self, mock_ports):
        """Skill registry should be optional."""
        agent = ConcreteAgent(agent_id="agent-1", **mock_ports)
        assert agent.skill_registry is None

    @pytest.mark.asyncio
    async def test_handle_task_abstract(self, mock_ports):
        """Concrete agents must implement handle_task."""
        agent = ConcreteAgent(agent_id="agent-1", **mock_ports)
        envelope = TaskEnvelope(
            task_id="task-1",
            agent_id="agent-1",
            cycle_id="cycle-1",
            pulse_id="pulse-1",
            project_id="proj-1",
            task_type="test",
            correlation_id="corr-1",
            causation_id="cause-1",
            trace_id="trace-1",
            span_id="span-1",
        )
        result = await agent.handle_task(envelope)
        assert result.task_id == "task-1"
        assert result.status == "completed"

    @pytest.mark.asyncio
    async def test_lifecycle_hooks_exist(self, mock_ports):
        """Lifecycle hooks should be callable."""
        agent = ConcreteAgent(agent_id="agent-1", **mock_ports)
        await agent.on_agent_start()
        await agent.on_agent_stop()
        await agent.on_cycle_start("cycle-1")
        await agent.on_cycle_end("cycle-1")
        await agent.on_pulse_start("pulse-1")
        await agent.on_pulse_end("pulse-1")

    def test_get_system_prompt_with_service(self, mock_ports):
        """get_system_prompt should use prompt_service."""
        mock_ports["prompt_service"].get_system_prompt.return_value = MagicMock(
            content="Test system prompt"
        )
        agent = ConcreteAgent(agent_id="agent-1", **mock_ports)
        prompt = agent.get_system_prompt()
        assert prompt == "Test system prompt"
        mock_ports["prompt_service"].get_system_prompt.assert_called_once_with("test")

    def test_get_system_prompt_without_service(self, mock_ports):
        """get_system_prompt should return empty if no service."""
        mock_ports["prompt_service"] = None
        agent = ConcreteAgent(agent_id="agent-1", **mock_ports)
        prompt = agent.get_system_prompt()
        assert prompt == ""

    @pytest.mark.asyncio
    async def test_health_check(self, mock_ports):
        """health() should aggregate health info."""
        mock_ports["llm"].health = AsyncMock(
            return_value={"healthy": True, "provider": "test"}
        )
        agent = ConcreteAgent(agent_id="agent-1", **mock_ports)
        health = await agent.health()
        assert health["healthy"] is True
        assert health["agent_id"] == "agent-1"
        assert health["role_id"] == "test"
        assert health["llm"]["provider"] == "test"

    @pytest.mark.asyncio
    async def test_health_check_unhealthy_llm(self, mock_ports):
        """health() should reflect unhealthy LLM."""
        mock_ports["llm"].health = AsyncMock(return_value={"healthy": False})
        agent = ConcreteAgent(agent_id="agent-1", **mock_ports)
        health = await agent.health()
        assert health["healthy"] is False
