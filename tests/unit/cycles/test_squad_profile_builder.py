"""Tests for the builder-equipped squad profile (SIP-0071 Phase 2).

Validates that the squad profile carrying a builder agent loads correctly,
resolves all 6 agents, and has the builder role properly configured.

The original `full-squad-with-builder` profile was removed in PR #175; the
surviving builder profile is `spark-squad-with-builder`, so these tests target
it. (Broader squad-profile name consolidation is tracked in issue #173 — this
change only re-points the stale assertions at the profile that still exists.)
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


class TestSparkSquadWithBuilderProfile:
    async def test_profile_loads(self, provider):
        profile = await provider.get_profile("spark-squad-with-builder")
        assert profile.profile_id == "spark-squad-with-builder"

    async def test_has_six_agents(self, provider):
        profile = await provider.get_profile("spark-squad-with-builder")
        assert len(profile.agents) == 6

    async def test_builder_agent_present(self, provider):
        profile = await provider.get_profile("spark-squad-with-builder")
        builder_agents = [a for a in profile.agents if a.role == "builder"]
        assert len(builder_agents) == 1

    async def test_builder_agent_is_bob(self, provider):
        profile = await provider.get_profile("spark-squad-with-builder")
        builder_agents = [a for a in profile.agents if a.role == "builder"]
        assert builder_agents[0].agent_id == "bob"

    async def test_builder_agent_enabled(self, provider):
        profile = await provider.get_profile("spark-squad-with-builder")
        builder_agents = [a for a in profile.agents if a.role == "builder"]
        assert builder_agents[0].enabled is True

    async def test_all_roles_present(self, provider):
        profile = await provider.get_profile("spark-squad-with-builder")
        roles = {a.role for a in profile.agents}
        assert roles == {"lead", "dev", "strat", "builder", "qa", "data"}

    async def test_full_squad_has_no_builder(self, provider):
        """The non-builder `full-squad` profile still has 5 agents and no builder
        role — the distinction the builder profile exists to add."""
        profile = await provider.get_profile("full-squad")
        assert len(profile.agents) == 5
        roles = {a.role for a in profile.agents}
        assert "builder" not in roles

    async def test_both_profiles_in_listing(self, provider):
        profiles = await provider.list_profiles()
        ids = {p.profile_id for p in profiles}
        assert "full-squad" in ids
        assert "spark-squad-with-builder" in ids
