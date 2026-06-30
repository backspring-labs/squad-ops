"""Tests for the builder-equipped squad profile (SIP-0071 Phase 2).

Validates that the squad profile carrying a builder agent loads correctly,
resolves all 6 agents, and has the builder role properly configured.

Profile-name history: the original `full-squad-with-builder` was removed in
PR #175, leaving `spark-squad-with-builder` as the lone builder profile; #173
then consolidated the squad-profile names by model tier — the builder profile
is now `full` (27b) and the surviving no-builder profile is `smoke` (3b). These
tests target the current names.
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


class TestFullSquadBuilderProfile:
    """The `full` profile (27b) is the builder-equipped squad (#173)."""

    async def test_profile_loads(self, provider):
        profile = await provider.get_profile("full")
        assert profile.profile_id == "full"

    async def test_has_six_agents(self, provider):
        profile = await provider.get_profile("full")
        assert len(profile.agents) == 6

    async def test_builder_agent_present(self, provider):
        profile = await provider.get_profile("full")
        builder_agents = [a for a in profile.agents if a.role == "builder"]
        assert len(builder_agents) == 1

    async def test_builder_agent_is_bob(self, provider):
        profile = await provider.get_profile("full")
        builder_agents = [a for a in profile.agents if a.role == "builder"]
        assert builder_agents[0].agent_id == "bob"

    async def test_builder_agent_enabled(self, provider):
        profile = await provider.get_profile("full")
        builder_agents = [a for a in profile.agents if a.role == "builder"]
        assert builder_agents[0].enabled is True

    async def test_all_roles_present(self, provider):
        profile = await provider.get_profile("full")
        roles = {a.role for a in profile.agents}
        assert roles == {"lead", "dev", "strat", "builder", "qa", "data"}

    async def test_smoke_has_no_builder(self, provider):
        """The surviving no-builder profile `smoke` still has 5 agents and no
        builder role — the no-builder build path (dev does assembly) the planner
        capability filter supports."""
        profile = await provider.get_profile("smoke")
        assert len(profile.agents) == 5
        roles = {a.role for a in profile.agents}
        assert "builder" not in roles

    async def test_consolidated_profiles_in_listing(self, provider):
        profiles = await provider.list_profiles()
        ids = {p.profile_id for p in profiles}
        assert ids == {"smoke", "lite", "full"}
