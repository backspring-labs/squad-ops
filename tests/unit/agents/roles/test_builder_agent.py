"""Unit tests for BuilderAgent (SIP-0071).

Tests role ID, default skills, and task type routing.
"""

from __future__ import annotations

import pytest

from squadops.agents.roles.builder import TASK_TYPE_SKILL_MAP, BuilderAgent

pytestmark = [pytest.mark.domain_agents]


class TestBuilderAgentMeta:
    def test_role_id_is_builder(self):
        assert BuilderAgent.ROLE_ID == "builder"

    def test_default_skills(self):
        assert "artifact_generation" in BuilderAgent.DEFAULT_SKILLS
        assert "code_generation" in BuilderAgent.DEFAULT_SKILLS


class TestTaskTypeRouting:
    def test_build_maps_to_artifact_generation(self):
        assert TASK_TYPE_SKILL_MAP["build"] == "artifact_generation"

    def test_builder_assemble_maps_to_artifact_generation(self):
        assert TASK_TYPE_SKILL_MAP["builder.assemble"] == "artifact_generation"


class TestBuilderAgentImport:
    def test_importable_from_roles_package(self):
        from squadops.agents.roles import BuilderAgent as Imported

        assert Imported is BuilderAgent
