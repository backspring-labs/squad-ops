"""Unit tests for agent domain models (SIP-0071 additions).

Tests BUILDER_ROLE registration in DEFAULT_ROLES and frozen immutability.
"""

from __future__ import annotations

import pytest

from squadops.agents.models import (
    BUILDER_ROLE,
    DEFAULT_ROLES,
)

pytestmark = [pytest.mark.domain_agents]


class TestBuilderRoleInDefaultRoles:
    def test_builder_key_present(self):
        assert "builder" in DEFAULT_ROLES

    def test_builder_value_is_builder_role(self):
        assert DEFAULT_ROLES["builder"] is BUILDER_ROLE

    def test_builder_default_skills_include_artifact_generation(self):
        assert "artifact_generation" in BUILDER_ROLE.default_skills

    def test_builder_default_skills_include_code_generation(self):
        assert "code_generation" in BUILDER_ROLE.default_skills

    def test_builder_role_is_frozen(self):
        with pytest.raises(AttributeError):
            BUILDER_ROLE.role_id = "hacked"

    def test_default_roles_count_includes_builder(self):
        # 6 roles: lead, dev, qa, strat, data, builder
        assert len(DEFAULT_ROLES) == 6
