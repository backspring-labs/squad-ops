"""Unit tests for builder agent skills (SIP-0071 Phase 3).

Tests skill auto-discovery, ArtifactGenerationSkill properties,
and skill execution.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from squadops.agents.skills.builder import SKILLS, ArtifactGenerationSkill
from squadops.llm.models import ChatMessage

pytestmark = [pytest.mark.domain_agents]


class TestBuilderSkillDiscovery:
    def test_skills_list_not_empty(self):
        assert len(SKILLS) > 0

    def test_artifact_generation_in_skills(self):
        assert ArtifactGenerationSkill in SKILLS

    def test_skill_importable_from_package(self):
        from squadops.agents.skills.builder import ArtifactGenerationSkill as Imported

        assert Imported is ArtifactGenerationSkill


class TestArtifactGenerationSkillMeta:
    def test_description(self):
        skill = ArtifactGenerationSkill()
        assert len(skill.description) > 0

    def test_required_capabilities(self):
        skill = ArtifactGenerationSkill()
        assert "llm" in skill.required_capabilities


class TestArtifactGenerationValidation:
    def test_requires_plan(self):
        skill = ArtifactGenerationSkill()
        errors = skill.validate_inputs({})
        assert any("plan" in e for e in errors)

    def test_plan_must_be_string(self):
        skill = ArtifactGenerationSkill()
        errors = skill.validate_inputs({"plan": 42})
        assert any("string" in e for e in errors)

    def test_plan_cannot_be_empty(self):
        skill = ArtifactGenerationSkill()
        errors = skill.validate_inputs({"plan": "  "})
        assert any("empty" in e for e in errors)

    def test_valid_plan_passes(self):
        skill = ArtifactGenerationSkill()
        errors = skill.validate_inputs({"plan": "Build a CLI tool"})
        assert errors == []


class TestArtifactGenerationExecution:
    @pytest.fixture()
    def mock_context(self):
        ctx = MagicMock()
        ctx.llm = MagicMock()
        ctx.llm.chat = AsyncMock(
            return_value=ChatMessage(
                role="assistant",
                content="```python:app/main.py\nprint('hello')\n```",
            ),
        )
        ctx.track_port_call = MagicMock()
        ctx.get_port_calls = MagicMock(return_value=[])
        return ctx

    async def test_success(self, mock_context):
        skill = ArtifactGenerationSkill()
        result = await skill.execute(
            mock_context,
            {"plan": "Build a hello world app"},
        )
        assert result.success is True
        assert "artifacts" in result.outputs

    async def test_outputs_include_build_profile(self, mock_context):
        skill = ArtifactGenerationSkill()
        result = await skill.execute(
            mock_context,
            {"plan": "Build an app", "build_profile": "static_web_builder"},
        )
        assert result.outputs["build_profile"] == "static_web_builder"

    async def test_llm_failure_returns_error(self, mock_context):
        mock_context.llm.chat = AsyncMock(side_effect=RuntimeError("LLM down"))
        skill = ArtifactGenerationSkill()
        result = await skill.execute(
            mock_context,
            {"plan": "Build something"},
        )
        assert result.success is False
        assert "LLM down" in result.error
