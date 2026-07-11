"""Unit tests for concrete capability handlers.

Tests governance, development, QA, data, and warmboot handlers.
Part of SIP-0.8.8 Phase 5.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from squadops.agents.base import PortsBundle
from squadops.agents.skills.base import ExecutionEvidence, Skill, SkillResult
from squadops.agents.skills.registry import SkillRegistry
from squadops.capabilities.handlers.context import ExecutionContext
from squadops.capabilities.handlers.data import (
    MetricsCollectionHandler,
)
from squadops.capabilities.handlers.development import (
    CodeAnalysisHandler,
    CodeGenerationHandler,
)
from squadops.capabilities.handlers.governance import (
    TaskDelegationHandler,
)
from squadops.capabilities.handlers.qa import (
    TestExecutionHandler,
    ValidationHandler,
)
from squadops.capabilities.handlers.warmboot import (
    ContextSyncHandler,
    WarmbootHandler,
)

# =============================================================================
# Test Fixtures
# =============================================================================


class MockSkill(Skill):
    """Configurable mock skill for testing."""

    def __init__(self, name: str, outputs: dict = None, success: bool = True, error: str = None):
        self._name = name
        self._outputs = outputs or {}
        self._success = success
        self._error = error

    @property
    def name(self) -> str:
        return self._name

    @property
    def description(self) -> str:
        return f"Mock {self._name} skill"

    @property
    def required_capabilities(self) -> tuple[str, ...]:
        return ()

    def validate_inputs(self, inputs):
        return []

    async def execute(self, context, inputs):
        evidence = ExecutionEvidence.create(
            skill_name=self.name,
            duration_ms=10.0,
            inputs_hash="abc",
            outputs_hash="def",
            port_calls=[],
        )
        return SkillResult(
            success=self._success,
            outputs=self._outputs,
            _evidence=evidence,
            error=self._error,
        )


@pytest.fixture
def mock_ports():
    """Create mock ports."""
    llm = MagicMock()
    llm.chat = AsyncMock()

    memory = MagicMock()
    memory.store = AsyncMock(return_value="mem-123")
    memory.search = AsyncMock(return_value=[])

    filesystem = MagicMock()
    filesystem.read = MagicMock(return_value="file content")
    filesystem.write = MagicMock()

    return PortsBundle(
        llm=llm,
        memory=memory,
        prompt_service=MagicMock(),
        queue=MagicMock(),
        metrics=MagicMock(),
        events=MagicMock(),
        filesystem=filesystem,
    )


def create_context(mock_ports, skills: list[Skill]) -> ExecutionContext:
    """Create ExecutionContext with given skills."""
    registry = SkillRegistry()
    for skill in skills:
        registry.register(skill)

    return ExecutionContext.create(
        agent_id="test-agent",
        role_id="test",
        task_id="task-1",
        cycle_id="cycle-1",
        ports=mock_ports,
        skill_registry=registry,
    )


# =============================================================================
# Governance Handler Tests
# =============================================================================


class TestTaskDelegationHandler:
    """Tests for TaskDelegationHandler."""

    def test_validate_inputs_missing_fields(self):
        """Should fail without required fields."""
        handler = TaskDelegationHandler()
        errors = handler.validate_inputs({})
        assert "'task_type' is required" in errors
        assert "'task_description' is required" in errors

    @pytest.mark.asyncio
    async def test_handle_success(self, mock_ports):
        """Should handle task delegation successfully."""
        skill = MockSkill(
            "task_delegation",
            outputs={
                "target_role": "dev",
                "task_envelope": {"task_id": "t-1"},
            },
        )
        context = create_context(mock_ports, [skill])

        handler = TaskDelegationHandler()
        result = await handler.handle(
            context,
            {"task_type": "code_generate", "task_description": "Generate code"},
        )

        assert result.success is True
        assert result.outputs["target_role"] == "dev"


# =============================================================================
# Development Handler Tests
# =============================================================================


class TestCodeGenerationHandler:
    """Tests for CodeGenerationHandler."""

    def test_validate_inputs_missing_requirements(self):
        """Should fail without requirements."""
        handler = CodeGenerationHandler()
        errors = handler.validate_inputs({})
        assert "'requirements' is required" in errors

    @pytest.mark.asyncio
    async def test_handle_success(self, mock_ports):
        """Should handle code generation successfully."""
        code_skill = MockSkill(
            "code_generation",
            outputs={"code": "def hello(): pass", "language": "python"},
        )
        write_skill = MockSkill("file_write", outputs={"bytes_written": 20})
        context = create_context(mock_ports, [code_skill, write_skill])

        handler = CodeGenerationHandler()
        result = await handler.handle(
            context,
            {"requirements": "Hello function"},
        )

        assert result.success is True
        assert "def hello" in result.outputs["code"]
        assert result.outputs["language"] == "python"

    @pytest.mark.asyncio
    async def test_handle_with_file_write(self, mock_ports):
        """Should write code to file when output_path provided."""
        code_skill = MockSkill(
            "code_generation",
            outputs={"code": "def hello(): pass", "language": "python"},
        )
        write_skill = MockSkill("file_write", outputs={"bytes_written": 20})
        context = create_context(mock_ports, [code_skill, write_skill])

        handler = CodeGenerationHandler()
        result = await handler.handle(
            context,
            {"requirements": "Hello function", "output_path": "/tmp/code.py"},
        )

        assert result.success is True
        assert result.artifacts.get("code_file") == "/tmp/code.py"


class TestCodeAnalysisHandler:
    """Tests for CodeAnalysisHandler."""

    def test_validate_inputs_missing_both(self):
        """Should fail without file_path or code."""
        handler = CodeAnalysisHandler()
        errors = handler.validate_inputs({})
        assert "Either 'file_path' or 'code' is required" in errors

    @pytest.mark.asyncio
    async def test_handle_with_code(self, mock_ports):
        """Should analyze provided code."""
        llm_skill = MockSkill("llm_query", outputs={"response": "Analysis result"})
        read_skill = MockSkill("file_read", outputs={"content": "code"})
        context = create_context(mock_ports, [llm_skill, read_skill])

        handler = CodeAnalysisHandler()
        result = await handler.handle(
            context,
            {"code": "def hello(): pass"},
        )

        assert result.success is True
        assert result.outputs["analysis"] == "Analysis result"


# =============================================================================
# QA Handler Tests
# =============================================================================


class TestTestExecutionHandler:
    """Tests for TestExecutionHandler."""

    def test_validate_inputs_missing_path(self):
        """Should fail without test_path."""
        handler = TestExecutionHandler()
        errors = handler.validate_inputs({})
        assert "'test_path' is required" in errors

    @pytest.mark.asyncio
    async def test_handle_success(self, mock_ports):
        """Should handle test execution successfully."""
        skill = MockSkill(
            "test_execution",
            outputs={
                "passed": 5,
                "failed": 0,
                "total": 5,
                "results": [],
            },
        )
        context = create_context(mock_ports, [skill])

        handler = TestExecutionHandler()
        result = await handler.handle(
            context,
            {"test_path": "tests/unit/"},
        )

        assert result.success is True
        assert result.outputs["passed"] == 5
        assert result.outputs["all_passed"] is True


class TestValidationHandler:
    """Tests for ValidationHandler."""

    def test_validate_inputs_missing_criteria(self):
        """Should fail without criteria."""
        handler = ValidationHandler()
        errors = handler.validate_inputs({"artifact_path": "/test"})
        assert "'criteria' is required" in errors

    @pytest.mark.asyncio
    async def test_handle_success(self, mock_ports):
        """Should handle validation successfully."""
        skill = MockSkill(
            "validation",
            outputs={"valid": True, "errors": []},
        )
        context = create_context(mock_ports, [skill])

        handler = ValidationHandler()
        result = await handler.handle(
            context,
            {"artifact_path": "/test.json", "criteria": ["valid_json"]},
        )

        assert result.success is True
        assert result.outputs["valid"] is True


# =============================================================================
# Data Handler Tests
# =============================================================================


class TestMetricsCollectionHandler:
    """Tests for MetricsCollectionHandler."""

    def test_validate_inputs_empty_metrics(self):
        """Should fail with empty metric_names."""
        handler = MetricsCollectionHandler()
        errors = handler.validate_inputs({"metric_names": []})
        assert "'metric_names' cannot be empty" in errors

    @pytest.mark.asyncio
    async def test_handle_success(self, mock_ports):
        """Should handle metrics collection successfully."""
        skill = MockSkill(
            "metrics_collection",
            outputs={
                "metrics": {"cpu": 50},
                "metric_count": 1,
                "timestamp": "2024-01-01T00:00:00Z",
                "aggregation_method": "latest",
            },
        )
        context = create_context(mock_ports, [skill])

        handler = MetricsCollectionHandler()
        result = await handler.handle(
            context,
            {"metric_names": ["cpu"]},
        )

        assert result.success is True
        assert result.outputs["metric_count"] == 1


# =============================================================================
# Warmboot Handler Tests
# =============================================================================


class TestWarmbootHandler:
    """Tests for WarmbootHandler."""

    def test_validate_inputs_missing_fields(self):
        """Should fail without required fields."""
        handler = WarmbootHandler()
        errors = handler.validate_inputs({})
        assert "'agent_id' is required" in errors
        assert "'context_query' is required" in errors

    @pytest.mark.asyncio
    async def test_handle_success(self, mock_ports):
        """Should handle warmboot successfully."""
        recall_skill = MockSkill(
            "memory_recall",
            outputs={"results": [{"content": "memory1"}], "count": 1},
        )
        store_skill = MockSkill("memory_store", outputs={"memory_id": "mem-123"})
        context = create_context(mock_ports, [recall_skill, store_skill])

        handler = WarmbootHandler()
        result = await handler.handle(
            context,
            {"agent_id": "agent-1", "context_query": "recent tasks"},
        )

        assert result.success is True
        assert result.outputs["recall_count"] == 1
        assert result.outputs["warmboot_complete"] is True


class TestContextSyncHandler:
    """Tests for ContextSyncHandler."""

    def test_validate_inputs_empty_content(self):
        """Should fail with empty content."""
        handler = ContextSyncHandler()
        errors = handler.validate_inputs({"content": "  "})
        assert "'content' cannot be empty" in errors

    @pytest.mark.asyncio
    async def test_handle_success(self, mock_ports):
        """Should handle context sync successfully."""
        skill = MockSkill("memory_store", outputs={"memory_id": "mem-456"})
        context = create_context(mock_ports, [skill])

        handler = ContextSyncHandler()
        result = await handler.handle(
            context,
            {"content": "Important context to save"},
        )

        assert result.success is True
        assert result.outputs["memory_id"] == "mem-456"
        assert result.outputs["synced"] is True


# =============================================================================
# Evidence Tests
# =============================================================================


class TestHandlerEvidence:
    """Tests for evidence generation across handlers."""

    @pytest.mark.asyncio
    async def test_evidence_tracks_skill_executions(self, mock_ports):
        """Evidence should track all skill executions."""
        code_skill = MockSkill(
            "code_generation",
            outputs={"code": "code", "language": "python"},
        )
        write_skill = MockSkill("file_write", outputs={"bytes_written": 4})
        context = create_context(mock_ports, [code_skill, write_skill])

        handler = CodeGenerationHandler()
        result = await handler.handle(
            context,
            {"requirements": "test", "output_path": "/tmp/test.py"},
        )

        # Should have evidence for both skill executions
        assert len(result.evidence.skill_executions) == 2

    @pytest.mark.asyncio
    async def test_evidence_has_duration(self, mock_ports):
        """Evidence should track execution duration."""
        skill = MockSkill(
            "task_delegation",
            outputs={"target_role": "dev", "task_envelope": {}},
        )
        context = create_context(mock_ports, [skill])

        handler = TaskDelegationHandler()
        result = await handler.handle(
            context,
            {"task_type": "development.develop", "task_description": "test"},
        )

        assert result.evidence.duration_ms >= 0

    @pytest.mark.asyncio
    async def test_evidence_has_hashes(self, mock_ports):
        """Evidence should have input/output hashes."""
        skill = MockSkill("validation", outputs={"valid": True, "errors": []})
        context = create_context(mock_ports, [skill])

        handler = ValidationHandler()
        result = await handler.handle(
            context,
            {"artifact_path": "/test", "criteria": ["valid_json"]},
        )

        assert result.evidence.inputs_hash != ""
        assert result.evidence.outputs_hash != ""
