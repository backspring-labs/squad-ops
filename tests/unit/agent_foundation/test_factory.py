"""Unit tests for AgentFactory.

Tests dependency-injected agent creation from SIP-0.8.8.
"""

from unittest.mock import MagicMock

import pytest

from squadops.agents.base import BaseAgent
from squadops.agents.exceptions import AgentRoleNotFoundError
from squadops.agents.factory import AgentFactory
from squadops.agents.models import AgentConfig, AgentRole
from squadops.tasks.models import TaskEnvelope, TaskResult


class TestAgent(BaseAgent):
    """Test agent implementation."""

    ROLE_ID = "test"

    async def handle_task(self, envelope: TaskEnvelope) -> TaskResult:
        return TaskResult(
            task_id=envelope.task_id,
            status="completed",
        )


class LeadAgent(BaseAgent):
    """Lead agent implementation."""

    ROLE_ID = "lead"

    async def handle_task(self, envelope: TaskEnvelope) -> TaskResult:
        return TaskResult(
            task_id=envelope.task_id,
            status="delegated",
        )


@pytest.fixture
def mock_ports():
    """Create mock ports."""
    return {
        "llm": MagicMock(),
        "memory": MagicMock(),
        "prompt_service": MagicMock(),
        "queue": MagicMock(),
        "metrics": MagicMock(),
        "events": MagicMock(),
        "filesystem": MagicMock(),
    }


@pytest.fixture
def factory(mock_ports):
    """Create factory with mock ports."""
    return AgentFactory(**mock_ports)


class TestAgentFactory:
    """Tests for AgentFactory."""

    def test_factory_initialization(self, factory):
        """Factory should initialize with ports."""
        assert factory is not None
        # Default roles should be available
        roles = factory.list_roles()
        assert "lead" in roles
        assert "dev" in roles
        assert "qa" in roles

    def test_register_agent_type(self, factory):
        """register_agent_type should add agent class."""
        factory.register_agent_type("test", TestAgent)
        # Should not raise
        config = AgentConfig(agent_id="agent-1", role_id="test")
        # Need to register role first
        factory.register_role(
            AgentRole(
                role_id="test",
                display_name="Test Agent",
                description="Testing",
            )
        )
        agent = factory.create(config)
        assert isinstance(agent, TestAgent)

    def test_register_duplicate_type_raises(self, factory):
        """register_agent_type should raise on duplicate."""
        factory.register_agent_type("lead", LeadAgent)
        with pytest.raises(ValueError, match="already registered"):
            factory.register_agent_type("lead", LeadAgent)

    def test_register_role(self, factory):
        """register_role should add custom role."""
        custom_role = AgentRole(
            role_id="custom",
            display_name="Custom Agent",
            description="Custom role",
            default_skills=("skill_a", "skill_b"),
        )
        factory.register_role(custom_role)
        role = factory.get_role("custom")
        assert role.display_name == "Custom Agent"
        assert role.default_skills == ("skill_a", "skill_b")

    def test_register_duplicate_role_raises(self, factory):
        """register_role should raise on duplicate."""
        with pytest.raises(ValueError, match="already registered"):
            factory.register_role(
                AgentRole(
                    role_id="lead",
                    display_name="Duplicate",
                    description="Duplicate",
                )
            )

    def test_get_role_not_found(self, factory):
        """get_role should raise for missing role."""
        with pytest.raises(AgentRoleNotFoundError):
            factory.get_role("nonexistent")

    def test_create_agent(self, factory, mock_ports):
        """create should instantiate agent with ports."""
        factory.register_agent_type("lead", LeadAgent)
        config = AgentConfig(agent_id="lead-1", role_id="lead")
        agent = factory.create(config)

        assert isinstance(agent, LeadAgent)
        assert agent.agent_id == "lead-1"
        assert agent.role_id == "lead"
        assert agent.llm is mock_ports["llm"]
        assert agent.memory is mock_ports["memory"]

    def test_create_with_port_overrides(self, factory, mock_ports):
        """create should allow port overrides."""
        factory.register_agent_type("lead", LeadAgent)
        config = AgentConfig(agent_id="lead-1", role_id="lead")

        override_llm = MagicMock()
        agent = factory.create(config, llm=override_llm)

        assert agent.llm is override_llm
        assert agent.llm is not mock_ports["llm"]

    def test_create_unknown_role_raises(self, factory):
        """create should raise for unknown role."""
        config = AgentConfig(agent_id="agent-1", role_id="unknown")
        with pytest.raises(AgentRoleNotFoundError):
            factory.create(config)

    def test_create_no_agent_class_raises(self, factory):
        """create should raise if no agent class registered."""
        # "dev" role exists but no agent class registered
        config = AgentConfig(agent_id="dev-1", role_id="dev")
        with pytest.raises(ValueError, match="No agent class registered"):
            factory.create(config)

    def test_create_from_role(self, factory, mock_ports):
        """create_from_role should be convenient wrapper."""
        factory.register_agent_type("lead", LeadAgent)
        agent = factory.create_from_role("lead-1", "lead")

        assert agent.agent_id == "lead-1"
        assert agent.role_id == "lead"
        assert agent.llm is mock_ports["llm"]

    def test_create_with_skill_registry(self, mock_ports):
        """Factory should pass skill registry to agents."""
        skill_registry = MagicMock()
        factory = AgentFactory(skill_registry=skill_registry, **mock_ports)
        factory.register_agent_type("lead", LeadAgent)

        agent = factory.create_from_role("lead-1", "lead")
        assert agent.skill_registry is skill_registry

    def test_create_skill_registry_override(self, mock_ports):
        """create should allow skill registry override."""
        factory = AgentFactory(**mock_ports)
        factory.register_agent_type("lead", LeadAgent)

        override_registry = MagicMock()
        agent = factory.create_from_role(
            "lead-1",
            "lead",
            skill_registry=override_registry,
        )
        assert agent.skill_registry is override_registry

    def test_list_roles_includes_defaults(self, factory):
        """list_roles should include default roles."""
        roles = factory.list_roles()
        assert "lead" in roles
        assert "dev" in roles
        assert "qa" in roles
        assert "strat" in roles
        assert "data" in roles
