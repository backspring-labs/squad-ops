"""Unit tests for shared skills.

Tests skills WITHOUT agents - direct SkillContext mocking.
Part of SIP-0.8.8 Phase 4.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from squadops.agents.base import PortsBundle
from squadops.agents.skills.context import SkillContext
from squadops.agents.skills.shared.file_read import FileReadSkill
from squadops.agents.skills.shared.file_write import FileWriteSkill
from squadops.agents.skills.shared.llm_query import LLMQuerySkill
from squadops.agents.skills.shared.memory_recall import MemoryRecallSkill
from squadops.agents.skills.shared.memory_store import MemoryStoreSkill


@pytest.fixture
def mock_ports():
    """Create mock ports for skill testing."""
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


class TestLLMQuerySkill:
    """Tests for LLMQuerySkill."""

    def test_required_capabilities(self):
        """Skill should require llm capability."""
        skill = LLMQuerySkill()
        assert "llm" in skill.required_capabilities

    def test_validate_inputs_missing_prompt(self):
        """Validation should fail without prompt."""
        skill = LLMQuerySkill()
        errors = skill.validate_inputs({})
        assert "'prompt' is required" in errors

    def test_validate_inputs_empty_prompt(self):
        """Validation should fail with empty prompt."""
        skill = LLMQuerySkill()
        errors = skill.validate_inputs({"prompt": ""})
        assert "'prompt' cannot be empty" in errors

    def test_validate_inputs_valid(self):
        """Validation should pass with valid prompt."""
        skill = LLMQuerySkill()
        errors = skill.validate_inputs({"prompt": "Hello"})
        assert errors == []

    @pytest.mark.asyncio
    async def test_execute_success(self, skill_context, mock_ports):
        """Skill should successfully query LLM."""
        mock_ports.llm.chat.return_value = MagicMock(content="LLM response")

        skill = LLMQuerySkill()
        result = await skill.execute(skill_context, {"prompt": "Hello"})

        assert result.success is True
        assert result.outputs["response"] == "LLM response"
        assert result.evidence.skill_name == "llm_query"
        mock_ports.llm.chat.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_with_system_prompt(self, skill_context, mock_ports):
        """Skill should include system prompt in messages."""
        mock_ports.llm.chat.return_value = MagicMock(content="Response")

        skill = LLMQuerySkill()
        await skill.execute(
            skill_context,
            {"prompt": "Hello", "system_prompt": "You are helpful"},
        )

        call_args = mock_ports.llm.chat.call_args
        messages = call_args[0][0]
        assert len(messages) == 2
        assert messages[0].role == "system"

    @pytest.mark.asyncio
    async def test_execute_error_handling(self, skill_context, mock_ports):
        """Skill should handle errors gracefully."""
        mock_ports.llm.chat.side_effect = Exception("LLM error")

        skill = LLMQuerySkill()
        result = await skill.execute(skill_context, {"prompt": "Hello"})

        assert result.success is False
        assert "LLM error" in result.error
        assert result.evidence.skill_name == "llm_query"


class TestFileReadSkill:
    """Tests for FileReadSkill."""

    def test_required_capabilities(self):
        """Skill should require filesystem capability."""
        skill = FileReadSkill()
        assert "filesystem" in skill.required_capabilities

    def test_validate_inputs_missing_path(self):
        """Validation should fail without path."""
        skill = FileReadSkill()
        errors = skill.validate_inputs({})
        assert "'path' is required" in errors

    @pytest.mark.asyncio
    async def test_execute_success(self, skill_context, mock_ports):
        """Skill should successfully read file."""
        mock_ports.filesystem.read.return_value = "Hello World"

        skill = FileReadSkill()
        result = await skill.execute(skill_context, {"path": "/test/file.txt"})

        assert result.success is True
        assert result.outputs["content"] == "Hello World"
        assert result.outputs["size"] == 11
        assert result.evidence.skill_name == "file_read"

    @pytest.mark.asyncio
    async def test_execute_file_not_found(self, skill_context, mock_ports):
        """Skill should handle file not found."""
        mock_ports.filesystem.read.side_effect = FileNotFoundError("Not found")

        skill = FileReadSkill()
        result = await skill.execute(skill_context, {"path": "/missing.txt"})

        assert result.success is False
        assert "Not found" in result.error


class TestFileWriteSkill:
    """Tests for FileWriteSkill."""

    def test_validate_inputs_missing_content(self):
        """Validation should fail without content."""
        skill = FileWriteSkill()
        errors = skill.validate_inputs({"path": "/test.txt"})
        assert "'content' is required" in errors

    @pytest.mark.asyncio
    async def test_execute_success(self, skill_context, mock_ports):
        """Skill should successfully write file."""
        skill = FileWriteSkill()
        result = await skill.execute(
            skill_context,
            {"path": "/test/file.txt", "content": "Hello"},
        )

        assert result.success is True
        assert result.outputs["bytes_written"] == 5
        mock_ports.filesystem.write.assert_called_once()


class TestMemoryStoreSkill:
    """Tests for MemoryStoreSkill."""

    def test_required_capabilities(self):
        """Skill should require memory capability."""
        skill = MemoryStoreSkill()
        assert "memory" in skill.required_capabilities

    def test_validate_inputs_empty_content(self):
        """Validation should fail with empty content."""
        skill = MemoryStoreSkill()
        errors = skill.validate_inputs({"content": "  "})
        assert "'content' cannot be empty" in errors

    @pytest.mark.asyncio
    async def test_execute_success(self, skill_context, mock_ports):
        """Skill should successfully store in memory."""
        skill = MemoryStoreSkill()
        result = await skill.execute(
            skill_context,
            {"content": "Important information"},
        )

        assert result.success is True
        assert result.outputs["memory_id"] == "mem-123"
        mock_ports.memory.store.assert_called_once()


class TestMemoryRecallSkill:
    """Tests for MemoryRecallSkill."""

    def test_validate_inputs_invalid_limit(self):
        """Validation should fail with invalid limit."""
        skill = MemoryRecallSkill()
        errors = skill.validate_inputs({"query": "test", "limit": -1})
        assert "'limit' must be a positive integer" in errors

    @pytest.mark.asyncio
    async def test_execute_success(self, skill_context, mock_ports):
        """Skill should successfully search memory."""
        # MemoryResult has entry (MemoryEntry), memory_id, and score
        mock_entry = MagicMock()
        mock_entry.content = "Result 1"
        mock_entry.metadata = ()

        mock_result = MagicMock()
        mock_result.memory_id = "mem-1"
        mock_result.entry = mock_entry
        mock_result.score = 0.9

        mock_ports.memory.search.return_value = [mock_result]

        skill = MemoryRecallSkill()
        result = await skill.execute(skill_context, {"query": "search term"})

        assert result.success is True
        assert result.outputs["count"] == 1
        assert result.outputs["results"][0]["memory_id"] == "mem-1"


class TestSkillEvidenceGeneration:
    """Tests for skill evidence generation."""

    @pytest.mark.asyncio
    async def test_evidence_has_required_fields(self, skill_context, mock_ports):
        """Evidence should have all required fields."""
        mock_ports.llm.chat.return_value = MagicMock(content="Response")

        skill = LLMQuerySkill()
        result = await skill.execute(skill_context, {"prompt": "Test"})

        evidence = result.evidence
        assert evidence.skill_name == "llm_query"
        assert evidence.duration_ms >= 0
        assert evidence.inputs_hash is not None
        assert evidence.outputs_hash is not None
        assert evidence.executed_at is not None

    @pytest.mark.asyncio
    async def test_evidence_tracks_port_calls(self, skill_context, mock_ports):
        """Evidence should include port calls."""
        mock_ports.llm.chat.return_value = MagicMock(content="Response")

        skill = LLMQuerySkill()
        result = await skill.execute(skill_context, {"prompt": "Test"})

        assert len(result.evidence.port_calls) > 0
        assert any("llm" in call for call in result.evidence.port_calls)
