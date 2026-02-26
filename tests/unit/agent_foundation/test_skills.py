"""Unit tests for Skills infrastructure.

Tests Skill, SkillContext, and SkillRegistry from SIP-0.8.8.
"""

import hashlib
import json
from datetime import UTC, datetime
from typing import Any
from unittest.mock import MagicMock

import pytest

from squadops.agents.base import PortsBundle
from squadops.agents.exceptions import SkillContractViolation, SkillNotFoundError
from squadops.agents.skills.base import (
    ExecutionEvidence,
    Skill,
    SkillResult,
)
from squadops.agents.skills.context import SkillContext
from squadops.agents.skills.registry import SkillRegistry


class EchoSkill(Skill):
    """Simple skill that echoes inputs for testing."""

    @property
    def name(self) -> str:
        return "echo"

    @property
    def description(self) -> str:
        return "Echoes inputs back as outputs"

    @property
    def required_capabilities(self) -> tuple[str, ...]:
        return ("llm",)

    async def execute(
        self,
        context: SkillContext,
        inputs: dict[str, Any],
    ) -> SkillResult:
        # Track LLM access
        _ = context.llm
        context.track_port_call("llm", "generate", prompt="test")

        evidence = ExecutionEvidence.create(
            skill_name=self.name,
            duration_ms=1.0,
            inputs_hash=self._hash(inputs),
            outputs_hash=self._hash(inputs),
            port_calls=context.get_port_calls(),
        )
        return SkillResult(
            success=True,
            outputs=dict(inputs),
            _evidence=evidence,
        )

    def _hash(self, d: dict) -> str:
        return hashlib.sha256(json.dumps(d, sort_keys=True).encode()).hexdigest()[:16]


class NoEvidenceSkill(Skill):
    """Skill that violates contract by not producing evidence."""

    @property
    def name(self) -> str:
        return "no_evidence"

    async def execute(
        self,
        context: SkillContext,
        inputs: dict[str, Any],
    ) -> SkillResult:
        # Return result without proper evidence
        return SkillResult(
            success=True,
            outputs={},
            _evidence=None,  # type: ignore - intentionally broken
        )


class WrongNameSkill(Skill):
    """Skill that produces evidence with wrong name."""

    @property
    def name(self) -> str:
        return "wrong_name"

    async def execute(
        self,
        context: SkillContext,
        inputs: dict[str, Any],
    ) -> SkillResult:
        evidence = ExecutionEvidence.create(
            skill_name="different_name",  # Wrong!
            duration_ms=1.0,
            inputs_hash="abc",
            outputs_hash="xyz",
        )
        return SkillResult(
            success=True,
            outputs={},
            _evidence=evidence,
        )


class ValidatingSkill(Skill):
    """Skill with input validation."""

    @property
    def name(self) -> str:
        return "validating"

    def validate_inputs(self, inputs: dict[str, Any]) -> list[str]:
        errors = []
        if "required_field" not in inputs:
            errors.append("required_field is required")
        return errors

    async def execute(
        self,
        context: SkillContext,
        inputs: dict[str, Any],
    ) -> SkillResult:
        evidence = ExecutionEvidence.create(
            skill_name=self.name,
            duration_ms=1.0,
            inputs_hash="abc",
            outputs_hash="xyz",
        )
        return SkillResult(
            success=True,
            outputs={"validated": True},
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
def skill_context(mock_ports):
    """Create skill context for testing."""
    return SkillContext(
        agent_id="agent-1",
        role_id="dev",
        task_id="task-1",
        cycle_id="cycle-1",
        ports=mock_ports,
    )


class TestExecutionEvidence:
    """Tests for ExecutionEvidence."""

    def test_evidence_is_frozen(self):
        """Evidence should be immutable."""
        evidence = ExecutionEvidence(
            skill_name="test",
            executed_at=datetime.now(UTC),
            duration_ms=1.0,
            inputs_hash="abc",
            outputs_hash="xyz",
        )
        with pytest.raises(AttributeError):
            evidence.skill_name = "changed"

    def test_create_sets_timestamp(self):
        """create() should set current timestamp."""
        before = datetime.now(UTC)
        evidence = ExecutionEvidence.create(
            skill_name="test",
            duration_ms=1.0,
            inputs_hash="abc",
            outputs_hash="xyz",
        )
        after = datetime.now(UTC)
        assert before <= evidence.executed_at <= after

    def test_create_stores_port_calls(self):
        """create() should store port calls."""
        evidence = ExecutionEvidence.create(
            skill_name="test",
            duration_ms=1.0,
            inputs_hash="abc",
            outputs_hash="xyz",
            port_calls=["llm.generate", "memory.store"],
        )
        assert evidence.port_calls == ("llm.generate", "memory.store")

    def test_create_stores_metadata(self):
        """create() should store metadata."""
        evidence = ExecutionEvidence.create(
            skill_name="test",
            duration_ms=1.0,
            inputs_hash="abc",
            outputs_hash="xyz",
            metadata={"key": "value"},
        )
        assert evidence.metadata == {"key": "value"}


class TestSkillResult:
    """Tests for SkillResult."""

    def test_result_is_frozen(self):
        """Result should be immutable."""
        evidence = ExecutionEvidence.create(
            skill_name="test",
            duration_ms=1.0,
            inputs_hash="abc",
            outputs_hash="xyz",
        )
        result = SkillResult(
            success=True,
            outputs={"data": 1},
            _evidence=evidence,
        )
        with pytest.raises(AttributeError):
            result.success = False

    def test_evidence_property(self):
        """evidence property should return _evidence."""
        evidence = ExecutionEvidence.create(
            skill_name="test",
            duration_ms=1.0,
            inputs_hash="abc",
            outputs_hash="xyz",
        )
        result = SkillResult(
            success=True,
            outputs={},
            _evidence=evidence,
        )
        assert result.evidence is evidence


class TestSkillContext:
    """Tests for SkillContext."""

    def test_from_agent_creates_context(self, mock_ports):
        """from_agent should create properly initialized context."""
        context = SkillContext.from_agent(
            agent_id="agent-1",
            role_id="dev",
            task_id="task-1",
            cycle_id="cycle-1",
            ports=mock_ports,
        )
        assert context.agent_id == "agent-1"
        assert context.role_id == "dev"
        assert context.task_id == "task-1"
        assert context.cycle_id == "cycle-1"
        assert context.ports is mock_ports

    def test_port_accessors_track_calls(self, skill_context):
        """Port accessors should track access."""
        _ = skill_context.llm
        _ = skill_context.memory
        _ = skill_context.filesystem
        calls = skill_context.get_port_calls()
        assert "llm.access" in calls
        assert "memory.access" in calls
        assert "filesystem.access" in calls

    def test_track_port_call_explicit(self, skill_context):
        """track_port_call should record custom calls."""
        skill_context.track_port_call("llm", "generate", model="gpt-4")
        calls = skill_context.get_port_calls()
        assert "llm.generate(model=gpt-4)" in calls

    def test_clear_port_calls(self, skill_context):
        """clear_port_calls should reset tracking."""
        _ = skill_context.llm
        skill_context.clear_port_calls()
        assert skill_context.get_port_calls() == []


class TestSkillRegistry:
    """Tests for SkillRegistry."""

    def test_register_skill(self):
        """register should add skill to registry."""
        registry = SkillRegistry()
        skill = EchoSkill()
        registry.register(skill)
        assert registry.get("echo") is skill

    def test_register_duplicate_raises(self):
        """register should raise on duplicate."""
        registry = SkillRegistry()
        registry.register(EchoSkill())
        with pytest.raises(ValueError, match="already registered"):
            registry.register(EchoSkill())

    def test_unregister_skill(self):
        """unregister should remove skill."""
        registry = SkillRegistry()
        registry.register(EchoSkill())
        assert registry.unregister("echo") is True
        assert registry.get("echo") is None

    def test_unregister_missing_returns_false(self):
        """unregister should return False for missing skill."""
        registry = SkillRegistry()
        assert registry.unregister("nonexistent") is False

    def test_list_skills(self):
        """list_skills should return all registered names."""
        registry = SkillRegistry()
        registry.register(EchoSkill())
        registry.register(ValidatingSkill())
        names = registry.list_skills()
        assert set(names) == {"echo", "validating"}

    def test_get_skills_by_capability(self):
        """get_skills_by_capability should filter by capability."""
        registry = SkillRegistry()
        registry.register(EchoSkill())  # requires llm
        registry.register(ValidatingSkill())  # no requirements
        llm_skills = registry.get_skills_by_capability("llm")
        assert len(llm_skills) == 1
        assert llm_skills[0].name == "echo"

    @pytest.mark.asyncio
    async def test_execute_success(self, skill_context):
        """execute should run skill and return result."""
        registry = SkillRegistry()
        registry.register(EchoSkill())
        result = await registry.execute(
            "echo",
            skill_context,
            {"message": "hello"},
        )
        assert result.success is True
        assert result.outputs == {"message": "hello"}
        assert result.evidence.skill_name == "echo"

    @pytest.mark.asyncio
    async def test_execute_skill_not_found(self, skill_context):
        """execute should raise for missing skill."""
        registry = SkillRegistry()
        with pytest.raises(SkillNotFoundError):
            await registry.execute("nonexistent", skill_context, {})

    @pytest.mark.asyncio
    async def test_execute_validation_failure(self, skill_context):
        """execute should handle validation errors."""
        registry = SkillRegistry()
        registry.register(ValidatingSkill())
        result = await registry.execute(
            "validating",
            skill_context,
            {},  # Missing required_field
        )
        assert result.success is False
        assert "required_field is required" in result.error

    @pytest.mark.asyncio
    async def test_execute_no_evidence_raises(self, skill_context):
        """execute should raise if skill produces no evidence."""
        registry = SkillRegistry()
        registry.register(NoEvidenceSkill())
        with pytest.raises(SkillContractViolation, match="failed to produce"):
            await registry.execute("no_evidence", skill_context, {})

    @pytest.mark.asyncio
    async def test_execute_wrong_name_raises(self, skill_context):
        """execute should raise if evidence has wrong skill name."""
        registry = SkillRegistry()
        registry.register(WrongNameSkill())
        with pytest.raises(SkillContractViolation, match="skill_name mismatch"):
            await registry.execute("wrong_name", skill_context, {})

    @pytest.mark.asyncio
    async def test_execute_exception_handled(self, skill_context):
        """execute should handle skill exceptions."""

        class FailingSkill(Skill):
            @property
            def name(self) -> str:
                return "failing"

            async def execute(self, context, inputs):
                raise RuntimeError("Skill failed")

        registry = SkillRegistry()
        registry.register(FailingSkill())
        result = await registry.execute("failing", skill_context, {})
        assert result.success is False
        assert "Skill failed" in result.error
