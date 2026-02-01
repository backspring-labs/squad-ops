"""Unit tests for agent role implementations.

Tests all 5 agent roles from SIP-0.8.8 Phase 3.
"""
import hashlib
import json
import pytest
from typing import Any
from unittest.mock import MagicMock, AsyncMock

from squadops.agents.base import PortsBundle
from squadops.agents.exceptions import SkillNotFoundError
from squadops.agents.roles.lead import LeadAgent
from squadops.agents.roles.dev import DevAgent
from squadops.agents.roles.qa import QAAgent
from squadops.agents.roles.strat import StratAgent
from squadops.agents.roles.data import DataAgent
from squadops.agents.skills.base import ExecutionEvidence, Skill, SkillResult
from squadops.agents.skills.registry import SkillRegistry
from squadops.tasks.models import TaskEnvelope, TaskResult


class MockSkill(Skill):
    """Mock skill for testing agent routing."""

    def __init__(self, skill_name: str):
        self._name = skill_name

    @property
    def name(self) -> str:
        return self._name

    async def execute(self, context, inputs: dict[str, Any]) -> SkillResult:
        evidence = ExecutionEvidence.create(
            skill_name=self._name,
            duration_ms=1.0,
            inputs_hash=self._hash(inputs),
            outputs_hash=self._hash({"result": "mock"}),
            port_calls=context.get_port_calls(),
            metadata={"mock": True},
        )
        return SkillResult(
            success=True,
            outputs={"result": "mock", "skill": self._name},
            _evidence=evidence,
        )

    def _hash(self, d: dict) -> str:
        return hashlib.sha256(json.dumps(d, sort_keys=True, default=str).encode()).hexdigest()[:16]


@pytest.fixture
def mock_ports():
    """Create mock ports for testing."""
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
    """Create skill registry with mock skills."""
    registry = SkillRegistry()
    # Register skills for all roles
    skills = [
        # Lead skills
        "task_analysis", "task_delegation", "code_review",
        "cycle_planning", "governance_approval",
        # Dev skills
        "code_generation", "code_modification", "test_writing",
        "bug_fixing", "refactoring",
        # QA skills
        "test_design", "test_execution", "validation", "bug_reporting",
        # Strat skills
        "strategy_analysis", "architecture_review", "requirement_analysis",
        # Data skills
        "data_analysis", "metrics_collection", "report_generation",
    ]
    for skill_name in skills:
        registry.register(MockSkill(skill_name))
    return registry


def create_envelope(task_type: str, **kwargs) -> TaskEnvelope:
    """Helper to create test envelopes."""
    defaults = {
        "task_id": "task-1",
        "agent_id": "agent-1",
        "cycle_id": "cycle-1",
        "pulse_id": "pulse-1",
        "project_id": "proj-1",
        "task_type": task_type,
        "correlation_id": "corr-1",
        "causation_id": "cause-1",
        "trace_id": "trace-1",
        "span_id": "span-1",
        "inputs": {"description": "Test task"},
    }
    defaults.update(kwargs)
    return TaskEnvelope(**defaults)


class TestLeadAgent:
    """Tests for LeadAgent."""

    def test_lead_agent_role_id(self, mock_ports, skill_registry):
        """LeadAgent should have correct ROLE_ID."""
        agent = LeadAgent(
            agent_id="lead-1",
            skill_registry=skill_registry,
            **{k: v for k, v in mock_ports.__dict__.items()},
        )
        assert agent.role_id == "lead"
        assert agent.ROLE_ID == "lead"

    def test_lead_agent_default_skills(self):
        """LeadAgent should have correct default skills."""
        assert LeadAgent.DEFAULT_SKILLS == (
            "task_analysis",
            "task_delegation",
            "code_review",
            "cycle_planning",
            "governance_approval",
        )

    @pytest.mark.asyncio
    async def test_lead_handles_analyze_task(self, mock_ports, skill_registry):
        """LeadAgent should route analyze to task_analysis skill."""
        agent = LeadAgent(
            agent_id="lead-1",
            skill_registry=skill_registry,
            **{k: v for k, v in mock_ports.__dict__.items()},
        )
        envelope = create_envelope("analyze")
        result = await agent.handle_task(envelope)
        assert result.status == "completed"
        assert result.outputs["skill"] == "task_analysis"

    @pytest.mark.asyncio
    async def test_lead_handles_delegate_task(self, mock_ports, skill_registry):
        """LeadAgent should route delegate to task_delegation skill."""
        agent = LeadAgent(
            agent_id="lead-1",
            skill_registry=skill_registry,
            **{k: v for k, v in mock_ports.__dict__.items()},
        )
        envelope = create_envelope("delegate")
        result = await agent.handle_task(envelope)
        assert result.status == "completed"
        assert result.outputs["skill"] == "task_delegation"

    @pytest.mark.asyncio
    async def test_lead_unknown_task_raises(self, mock_ports, skill_registry):
        """LeadAgent should raise for unknown task types."""
        agent = LeadAgent(
            agent_id="lead-1",
            skill_registry=skill_registry,
            **{k: v for k, v in mock_ports.__dict__.items()},
        )
        with pytest.raises(SkillNotFoundError):
            agent._select_skill("unknown_task_type")


class TestDevAgent:
    """Tests for DevAgent."""

    def test_dev_agent_role_id(self, mock_ports, skill_registry):
        """DevAgent should have correct ROLE_ID."""
        agent = DevAgent(
            agent_id="dev-1",
            skill_registry=skill_registry,
            **{k: v for k, v in mock_ports.__dict__.items()},
        )
        assert agent.role_id == "dev"
        assert agent.ROLE_ID == "dev"

    def test_dev_agent_default_skills(self):
        """DevAgent should have correct default skills."""
        assert DevAgent.DEFAULT_SKILLS == (
            "code_generation",
            "code_modification",
            "test_writing",
            "bug_fixing",
            "refactoring",
        )

    @pytest.mark.asyncio
    async def test_dev_handles_generate_task(self, mock_ports, skill_registry):
        """DevAgent should route generate to code_generation skill."""
        agent = DevAgent(
            agent_id="dev-1",
            skill_registry=skill_registry,
            **{k: v for k, v in mock_ports.__dict__.items()},
        )
        envelope = create_envelope("generate")
        result = await agent.handle_task(envelope)
        assert result.status == "completed"
        assert result.outputs["skill"] == "code_generation"

    @pytest.mark.asyncio
    async def test_dev_handles_fix_task(self, mock_ports, skill_registry):
        """DevAgent should route fix to bug_fixing skill."""
        agent = DevAgent(
            agent_id="dev-1",
            skill_registry=skill_registry,
            **{k: v for k, v in mock_ports.__dict__.items()},
        )
        envelope = create_envelope("fix")
        result = await agent.handle_task(envelope)
        assert result.status == "completed"
        assert result.outputs["skill"] == "bug_fixing"

    @pytest.mark.asyncio
    async def test_dev_unknown_task_raises(self, mock_ports, skill_registry):
        """DevAgent should raise for unknown task types."""
        agent = DevAgent(
            agent_id="dev-1",
            skill_registry=skill_registry,
            **{k: v for k, v in mock_ports.__dict__.items()},
        )
        with pytest.raises(SkillNotFoundError):
            agent._select_skill("unknown_task_type")


class TestQAAgent:
    """Tests for QAAgent."""

    def test_qa_agent_role_id(self, mock_ports, skill_registry):
        """QAAgent should have correct ROLE_ID."""
        agent = QAAgent(
            agent_id="qa-1",
            skill_registry=skill_registry,
            **{k: v for k, v in mock_ports.__dict__.items()},
        )
        assert agent.role_id == "qa"
        assert agent.ROLE_ID == "qa"

    def test_qa_agent_default_skills(self):
        """QAAgent should have correct default skills."""
        assert QAAgent.DEFAULT_SKILLS == (
            "test_design",
            "test_execution",
            "validation",
            "bug_reporting",
        )

    @pytest.mark.asyncio
    async def test_qa_handles_validate_task(self, mock_ports, skill_registry):
        """QAAgent should route validate to validation skill."""
        agent = QAAgent(
            agent_id="qa-1",
            skill_registry=skill_registry,
            **{k: v for k, v in mock_ports.__dict__.items()},
        )
        envelope = create_envelope("validate")
        result = await agent.handle_task(envelope)
        assert result.status == "completed"
        assert result.outputs["skill"] == "validation"

    @pytest.mark.asyncio
    async def test_qa_handles_run_tests_task(self, mock_ports, skill_registry):
        """QAAgent should route run_tests to test_execution skill."""
        agent = QAAgent(
            agent_id="qa-1",
            skill_registry=skill_registry,
            **{k: v for k, v in mock_ports.__dict__.items()},
        )
        envelope = create_envelope("run_tests")
        result = await agent.handle_task(envelope)
        assert result.status == "completed"
        assert result.outputs["skill"] == "test_execution"


class TestStratAgent:
    """Tests for StratAgent."""

    def test_strat_agent_role_id(self, mock_ports, skill_registry):
        """StratAgent should have correct ROLE_ID."""
        agent = StratAgent(
            agent_id="strat-1",
            skill_registry=skill_registry,
            **{k: v for k, v in mock_ports.__dict__.items()},
        )
        assert agent.role_id == "strat"
        assert agent.ROLE_ID == "strat"

    def test_strat_agent_default_skills(self):
        """StratAgent should have correct default skills."""
        assert StratAgent.DEFAULT_SKILLS == (
            "strategy_analysis",
            "architecture_review",
            "requirement_analysis",
        )

    @pytest.mark.asyncio
    async def test_strat_handles_strategy_task(self, mock_ports, skill_registry):
        """StratAgent should route strategy to strategy_analysis skill."""
        agent = StratAgent(
            agent_id="strat-1",
            skill_registry=skill_registry,
            **{k: v for k, v in mock_ports.__dict__.items()},
        )
        envelope = create_envelope("strategy")
        result = await agent.handle_task(envelope)
        assert result.status == "completed"
        assert result.outputs["skill"] == "strategy_analysis"

    @pytest.mark.asyncio
    async def test_strat_handles_architecture_task(self, mock_ports, skill_registry):
        """StratAgent should route architecture to architecture_review skill."""
        agent = StratAgent(
            agent_id="strat-1",
            skill_registry=skill_registry,
            **{k: v for k, v in mock_ports.__dict__.items()},
        )
        envelope = create_envelope("architecture")
        result = await agent.handle_task(envelope)
        assert result.status == "completed"
        assert result.outputs["skill"] == "architecture_review"


class TestDataAgent:
    """Tests for DataAgent."""

    def test_data_agent_role_id(self, mock_ports, skill_registry):
        """DataAgent should have correct ROLE_ID."""
        agent = DataAgent(
            agent_id="data-1",
            skill_registry=skill_registry,
            **{k: v for k, v in mock_ports.__dict__.items()},
        )
        assert agent.role_id == "data"
        assert agent.ROLE_ID == "data"

    def test_data_agent_default_skills(self):
        """DataAgent should have correct default skills."""
        assert DataAgent.DEFAULT_SKILLS == (
            "data_analysis",
            "metrics_collection",
            "report_generation",
        )

    @pytest.mark.asyncio
    async def test_data_handles_analyze_data_task(self, mock_ports, skill_registry):
        """DataAgent should route analyze_data to data_analysis skill."""
        agent = DataAgent(
            agent_id="data-1",
            skill_registry=skill_registry,
            **{k: v for k, v in mock_ports.__dict__.items()},
        )
        envelope = create_envelope("analyze_data")
        result = await agent.handle_task(envelope)
        assert result.status == "completed"
        assert result.outputs["skill"] == "data_analysis"

    @pytest.mark.asyncio
    async def test_data_handles_report_task(self, mock_ports, skill_registry):
        """DataAgent should route report to report_generation skill."""
        agent = DataAgent(
            agent_id="data-1",
            skill_registry=skill_registry,
            **{k: v for k, v in mock_ports.__dict__.items()},
        )
        envelope = create_envelope("report")
        result = await agent.handle_task(envelope)
        assert result.status == "completed"
        assert result.outputs["skill"] == "report_generation"


class TestAgentWithoutRegistry:
    """Tests for agents without skill registry."""

    @pytest.mark.asyncio
    async def test_agent_without_registry_returns_failed(self, mock_ports):
        """Agent without skill registry should return failed result."""
        agent = LeadAgent(
            agent_id="lead-1",
            skill_registry=None,
            **{k: v for k, v in mock_ports.__dict__.items()},
        )
        envelope = create_envelope("analyze")
        result = await agent.handle_task(envelope)
        assert result.status == "failed"
        assert "Skill registry not available" in result.error


class TestTaskInputMapping:
    """Tests for task input mapping."""

    @pytest.mark.asyncio
    async def test_envelope_inputs_passed_to_skill(self, mock_ports, skill_registry):
        """Envelope inputs should be passed to skill."""
        agent = LeadAgent(
            agent_id="lead-1",
            skill_registry=skill_registry,
            **{k: v for k, v in mock_ports.__dict__.items()},
        )
        envelope = create_envelope(
            "analyze",
            inputs={"description": "Test", "priority": "high"},
        )
        inputs = agent._map_task_to_inputs(envelope)
        assert inputs["description"] == "Test"
        assert inputs["priority"] == "high"
        assert inputs["_task_id"] == "task-1"
        assert inputs["_task_type"] == "analyze"
        assert inputs["_cycle_id"] == "cycle-1"
