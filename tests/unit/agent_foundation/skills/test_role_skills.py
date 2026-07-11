"""Unit tests for role-specific skills.

Tests skills WITHOUT agents - direct SkillContext mocking.
Part of SIP-0.8.8 Phase 4.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from squadops.agents.base import PortsBundle
from squadops.agents.skills.context import SkillContext

# Data skills
from squadops.agents.skills.data.metrics_collection import MetricsCollectionSkill

# Dev skills
from squadops.agents.skills.dev.code_generation import CodeGenerationSkill

# Lead skills
from squadops.agents.skills.lead.task_delegation import TaskDelegationSkill

# QA skills
from squadops.agents.skills.qa.test_execution import TestExecutionSkill
from squadops.agents.skills.qa.validation import ValidationSkill

# Strat skills


@pytest.fixture
def mock_ports():
    """Create mock ports for skill testing."""
    llm = MagicMock()
    llm.chat = AsyncMock()

    filesystem = MagicMock()
    filesystem.read = MagicMock(return_value='{"key": "value"}')
    filesystem.write = MagicMock()
    filesystem.exists = MagicMock(return_value=True)

    return PortsBundle(
        llm=llm,
        memory=MagicMock(),
        prompt_service=MagicMock(),
        queue=MagicMock(),
        metrics=MagicMock(),
        events=MagicMock(),
        filesystem=filesystem,
    )


@pytest.fixture
def skill_context(mock_ports):
    """Create skill context for testing."""
    return SkillContext(
        agent_id="test-agent",
        role_id="test",
        task_id="task-1",
        cycle_id="cycle-1",
        ports=mock_ports,
    )


class TestTaskDelegationSkill:
    """Tests for TaskDelegationSkill."""

    def test_validate_inputs_missing_fields(self):
        """Validation should fail without required fields."""
        skill = TaskDelegationSkill()
        errors = skill.validate_inputs({})
        assert "'task_type' is required" in errors
        assert "'task_description' is required" in errors

    @pytest.mark.asyncio
    async def test_execute_delegates_to_dev(self, skill_context):
        """Skill should delegate code tasks to dev."""
        skill = TaskDelegationSkill()
        result = await skill.execute(
            skill_context,
            {
                "task_type": "code_generate",
                "task_description": "Generate code",
            },
        )

        assert result.success is True
        assert result.outputs["target_role"] == "dev"
        assert "task_envelope" in result.outputs

    @pytest.mark.asyncio
    async def test_execute_delegates_to_qa(self, skill_context):
        """Skill should delegate test tasks to qa."""
        skill = TaskDelegationSkill()
        result = await skill.execute(
            skill_context,
            {
                "task_type": "validate",
                "task_description": "Validate output",
            },
        )

        assert result.success is True
        assert result.outputs["target_role"] == "qa"


class TestCodeGenerationSkill:
    """Tests for CodeGenerationSkill."""

    def test_validate_inputs_missing_requirements(self):
        """Validation should fail without requirements."""
        skill = CodeGenerationSkill()
        errors = skill.validate_inputs({})
        assert "'requirements' is required" in errors

    @pytest.mark.asyncio
    async def test_execute_generates_code(self, skill_context, mock_ports):
        """Skill should generate code from requirements."""
        mock_ports.llm.chat.return_value = MagicMock(
            content="```python\ndef hello():\n    print('Hello')\n```\n\nThis function prints Hello."
        )

        skill = CodeGenerationSkill()
        result = await skill.execute(
            skill_context,
            {"requirements": "Create a hello function"},
        )

        assert result.success is True
        assert "code" in result.outputs
        assert "def hello" in result.outputs["code"]

    @pytest.mark.asyncio
    async def test_execute_with_language(self, skill_context, mock_ports):
        """Skill should respect language parameter."""
        mock_ports.llm.chat.return_value = MagicMock(content="code here")

        skill = CodeGenerationSkill()
        result = await skill.execute(
            skill_context,
            {"requirements": "Hello function", "language": "javascript"},
        )

        assert result.outputs["language"] == "javascript"


class TestTestExecutionSkill:
    """Tests for TestExecutionSkill."""

    def test_validate_inputs_missing_path(self):
        """Validation should fail without test_path."""
        skill = TestExecutionSkill()
        errors = skill.validate_inputs({})
        assert "'test_path' is required" in errors

    @pytest.mark.asyncio
    async def test_execute_returns_results(self, skill_context):
        """Skill should return test results."""
        skill = TestExecutionSkill()
        result = await skill.execute(
            skill_context,
            {"test_path": "tests/unit/"},
        )

        assert result.success is True
        assert "passed" in result.outputs
        assert "total" in result.outputs
        assert "results" in result.outputs


class TestValidationSkill:
    """Tests for ValidationSkill."""

    def test_validate_inputs_missing_criteria(self):
        """Validation should fail without criteria."""
        skill = ValidationSkill()
        errors = skill.validate_inputs({"artifact_path": "/test"})
        assert "'criteria' is required" in errors

    @pytest.mark.asyncio
    async def test_execute_validates_json(self, skill_context, mock_ports):
        """Skill should validate JSON content."""
        mock_ports.filesystem.read.return_value = '{"valid": "json"}'

        skill = ValidationSkill()
        result = await skill.execute(
            skill_context,
            {
                "artifact_path": "/test.json",
                "criteria": ["valid_json", "not_empty"],
            },
        )

        assert result.success is True
        assert result.outputs["valid"] is True
        assert result.outputs["errors"] == []

    @pytest.mark.asyncio
    async def test_execute_detects_invalid_json(self, skill_context, mock_ports):
        """Skill should detect invalid JSON."""
        mock_ports.filesystem.read.return_value = "not json {"

        skill = ValidationSkill()
        result = await skill.execute(
            skill_context,
            {
                "artifact_path": "/test.json",
                "criteria": ["valid_json"],
            },
        )

        assert result.outputs["valid"] is False
        assert any("Invalid JSON" in e for e in result.outputs["errors"])


class TestMetricsCollectionSkill:
    """Tests for MetricsCollectionSkill."""

    def test_validate_inputs_empty_metrics(self):
        """Validation should fail with empty metric_names."""
        skill = MetricsCollectionSkill()
        errors = skill.validate_inputs({"metric_names": []})
        assert "'metric_names' cannot be empty" in errors

    @pytest.mark.asyncio
    async def test_execute_collects_metrics(self, skill_context):
        """Skill should collect metrics."""
        skill = MetricsCollectionSkill()
        result = await skill.execute(
            skill_context,
            {"metric_names": ["cpu_usage", "memory_usage"]},
        )

        assert result.success is True
        assert result.outputs["metric_count"] == 2
        assert "cpu_usage" in result.outputs["metrics"]
        assert "timestamp" in result.outputs
