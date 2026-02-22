"""Tests for full-squad-with-builder squad profile (SIP-0071 Phase 2).

Validates that the squad profile with builder agent loads correctly,
resolves all 6 agents, and has the builder role properly configured.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from adapters.cycles.config_squad_profile import ConfigSquadProfile

pytestmark = [pytest.mark.domain_orchestration]

CONFIG_PATH = Path(__file__).resolve().parents[3] / "config" / "squad-profiles.yaml"


@pytest.fixture()
def provider():
    return ConfigSquadProfile(yaml_path=CONFIG_PATH)


class TestFullSquadWithBuilderProfile:
    async def test_profile_loads(self, provider):
        profile = await provider.get_profile("full-squad-with-builder")
        assert profile.profile_id == "full-squad-with-builder"

    async def test_has_six_agents(self, provider):
        profile = await provider.get_profile("full-squad-with-builder")
        assert len(profile.agents) == 6

    async def test_builder_agent_present(self, provider):
        profile = await provider.get_profile("full-squad-with-builder")
        builder_agents = [a for a in profile.agents if a.role == "builder"]
        assert len(builder_agents) == 1

    async def test_builder_agent_is_bob(self, provider):
        profile = await provider.get_profile("full-squad-with-builder")
        builder_agents = [a for a in profile.agents if a.role == "builder"]
        assert builder_agents[0].agent_id == "bob"

    async def test_builder_agent_enabled(self, provider):
        profile = await provider.get_profile("full-squad-with-builder")
        builder_agents = [a for a in profile.agents if a.role == "builder"]
        assert builder_agents[0].enabled is True

    async def test_all_original_roles_present(self, provider):
        profile = await provider.get_profile("full-squad-with-builder")
        roles = {a.role for a in profile.agents}
        assert roles == {"lead", "dev", "strat", "builder", "qa", "data"}

    async def test_original_full_squad_unchanged(self, provider):
        """Original full-squad profile should still have 5 agents."""
        profile = await provider.get_profile("full-squad")
        assert len(profile.agents) == 5
        roles = {a.role for a in profile.agents}
        assert "builder" not in roles

    async def test_both_profiles_in_listing(self, provider):
        profiles = await provider.list_profiles()
        ids = {p.profile_id for p in profiles}
        assert "full-squad" in ids
        assert "full-squad-with-builder" in ids
