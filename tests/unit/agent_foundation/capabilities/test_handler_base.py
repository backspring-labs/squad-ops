"""Unit tests for capability handler base classes.

Tests CapabilityHandler ABC, HandlerResult, HandlerEvidence.
Part of SIP-0.8.8 Phase 5.
"""
import pytest
from datetime import datetime
from unittest.mock import MagicMock, AsyncMock

from squadops.capabilities.handlers.base import (
    CapabilityHandler,
    HandlerEvidence,
    HandlerResult,
)
from squadops.capabilities.handlers.context import (
    ExecutionContext,
    SkillExecutionRecord,
)
from squadops.agents.base import PortsBundle
from squadops.agents.skills.registry import SkillRegistry
from squadops.agents.skills.base import Skill, SkillResult, ExecutionEvidence


class TestHandlerEvidence:
    """Tests for HandlerEvidence dataclass."""

    def test_create_evidence(self):
        """Should create evidence with all fields."""
        evidence = HandlerEvidence.create(
            handler_name="test_handler",
            capability_id="test.capability",
            duration_ms=100.5,
            skill_executions=[{"skill": "test_skill"}],
            inputs_hash="abc123",
            outputs_hash="def456",
            metadata={"key": "value"},
        )

        assert evidence.handler_name == "test_handler"
        assert evidence.capability_id == "test.capability"
        assert evidence.duration_ms == 100.5
        assert len(evidence.skill_executions) == 1
        assert evidence.inputs_hash == "abc123"
        assert evidence.outputs_hash == "def456"
        assert evidence.metadata["key"] == "value"
        assert isinstance(evidence.executed_at, datetime)

    def test_evidence_is_frozen(self):
        """Evidence should be immutable."""
        evidence = HandlerEvidence.create(
            handler_name="test",
            capability_id="test",
            duration_ms=0,
        )

        with pytest.raises(AttributeError):
            evidence.handler_name = "changed"

    def test_evidence_with_empty_skill_executions(self):
        """Should handle empty skill executions."""
        evidence = HandlerEvidence.create(
            handler_name="test",
            capability_id="test",
            duration_ms=50,
        )

        assert evidence.skill_executions == ()


class TestHandlerResult:
    """Tests for HandlerResult dataclass."""

    def test_create_success_result(self):
        """Should create successful result."""
        evidence = HandlerEvidence.create(
            handler_name="test",
            capability_id="test",
            duration_ms=0,
        )
        result = HandlerResult(
            success=True,
            outputs={"key": "value"},
            _evidence=evidence,
        )

        assert result.success is True
        assert result.outputs["key"] == "value"
        assert result.error is None
        assert result.evidence == evidence

    def test_create_failure_result(self):
        """Should create failed result with error."""
        evidence = HandlerEvidence.create(
            handler_name="test",
            capability_id="test",
            duration_ms=0,
        )
        result = HandlerResult(
            success=False,
            outputs={},
            _evidence=evidence,
            error="Something went wrong",
        )

        assert result.success is False
        assert result.error == "Something went wrong"
        assert result.outputs == {}

    def test_result_with_artifacts(self):
        """Should include artifacts in result."""
        evidence = HandlerEvidence.create(
            handler_name="test",
            capability_id="test",
            duration_ms=0,
        )
        result = HandlerResult(
            success=True,
            outputs={},
            _evidence=evidence,
            artifacts={"code_file": "/path/to/file.py"},
        )

        assert result.artifacts["code_file"] == "/path/to/file.py"

    def test_evidence_property(self):
        """evidence property should return _evidence."""
        evidence = HandlerEvidence.create(
            handler_name="test",
            capability_id="test",
            duration_ms=0,
        )
        result = HandlerResult(
            success=True,
            outputs={},
            _evidence=evidence,
        )

        assert result.evidence is evidence


class TestSkillExecutionRecord:
    """Tests for SkillExecutionRecord."""

    def test_to_dict(self):
        """Should convert to dictionary correctly."""
        record = SkillExecutionRecord(
            skill_name="test_skill",
            inputs={"prompt": "Hello"},
            outputs={"response": "World"},
            success=True,
            duration_ms=50.5,
        )

        d = record.to_dict()

        assert d["skill_name"] == "test_skill"
        assert d["inputs_keys"] == ["prompt"]
        assert d["outputs_keys"] == ["response"]
        assert d["success"] is True
        assert d["duration_ms"] == 50.5
        assert d["error"] is None

    def test_to_dict_with_error(self):
        """Should include error in dict."""
        record = SkillExecutionRecord(
            skill_name="test_skill",
            inputs={},
            outputs={},
            success=False,
            duration_ms=10,
            error="Failed",
        )

        d = record.to_dict()
        assert d["error"] == "Failed"


class TestExecutionContext:
    """Tests for ExecutionContext."""

    @pytest.fixture
    def mock_ports(self):
        """Create mock ports."""
        llm = MagicMock()
        llm.chat = AsyncMock()

        return PortsBundle(
            llm=llm,
            memory=MagicMock(),
            prompt_service=MagicMock(),
            queue=MagicMock(),
            metrics=MagicMock(),
            events=MagicMock(),
            filesystem=MagicMock(),
        )

    @pytest.fixture
    def mock_skill(self):
        """Create a mock skill."""
        class MockSkill(Skill):
            @property
            def name(self) -> str:
                return "mock_skill"

            @property
            def description(self) -> str:
                return "A mock skill"

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
                    success=True,
                    outputs={"result": "success"},
                    _evidence=evidence,
                )

        return MockSkill()

    @pytest.fixture
    def skill_registry(self, mock_skill):
        """Create registry with mock skill."""
        registry = SkillRegistry()
        registry.register(mock_skill)
        return registry

    def test_create_context(self, mock_ports, skill_registry):
        """Should create context with all fields."""
        context = ExecutionContext.create(
            agent_id="agent-1",
            role_id="lead",
            task_id="task-1",
            cycle_id="cycle-1",
            ports=mock_ports,
            skill_registry=skill_registry,
        )

        assert context.agent_id == "agent-1"
        assert context.role_id == "lead"
        assert context.task_id == "task-1"
        assert context.cycle_id == "cycle-1"
        assert context.ports is mock_ports
        assert context.skill_registry is skill_registry

    def test_create_skill_context(self, mock_ports, skill_registry):
        """Should create SkillContext correctly."""
        context = ExecutionContext.create(
            agent_id="agent-1",
            role_id="lead",
            task_id="task-1",
            cycle_id="cycle-1",
            ports=mock_ports,
            skill_registry=skill_registry,
        )

        skill_ctx = context.create_skill_context()

        assert skill_ctx.agent_id == "agent-1"
        assert skill_ctx.role_id == "lead"
        assert skill_ctx.task_id == "task-1"
        assert skill_ctx.cycle_id == "cycle-1"
        assert skill_ctx.ports is mock_ports

    @pytest.mark.asyncio
    async def test_execute_skill(self, mock_ports, skill_registry):
        """Should execute skill and record evidence."""
        context = ExecutionContext.create(
            agent_id="agent-1",
            role_id="lead",
            task_id="task-1",
            cycle_id="cycle-1",
            ports=mock_ports,
            skill_registry=skill_registry,
        )

        result = await context.execute_skill("mock_skill", {"input": "value"})

        assert result.success is True
        assert result.outputs["result"] == "success"

        # Should record execution
        executions = context.get_skill_executions()
        assert len(executions) == 1
        assert executions[0]["skill_name"] == "mock_skill"
        assert executions[0]["success"] is True

    def test_has_skill(self, mock_ports, skill_registry):
        """Should check if skill is available."""
        context = ExecutionContext.create(
            agent_id="agent-1",
            role_id="lead",
            task_id="task-1",
            cycle_id="cycle-1",
            ports=mock_ports,
            skill_registry=skill_registry,
        )

        assert context.has_skill("mock_skill") is True
        assert context.has_skill("nonexistent") is False

    @pytest.mark.asyncio
    async def test_get_total_duration(self, mock_ports, skill_registry):
        """Should sum all execution durations."""
        context = ExecutionContext.create(
            agent_id="agent-1",
            role_id="lead",
            task_id="task-1",
            cycle_id="cycle-1",
            ports=mock_ports,
            skill_registry=skill_registry,
        )

        await context.execute_skill("mock_skill", {})
        await context.execute_skill("mock_skill", {})

        total = context.get_total_duration_ms()
        assert total == 20.0  # 10.0 + 10.0

    def test_clear_executions(self, mock_ports, skill_registry):
        """Should clear execution records."""
        context = ExecutionContext.create(
            agent_id="agent-1",
            role_id="lead",
            task_id="task-1",
            cycle_id="cycle-1",
            ports=mock_ports,
            skill_registry=skill_registry,
        )

        context._skill_executions.append(
            SkillExecutionRecord(
                skill_name="test",
                inputs={},
                outputs={},
                success=True,
                duration_ms=10,
            )
        )

        context.clear_executions()
        assert context.get_skill_executions() == []
