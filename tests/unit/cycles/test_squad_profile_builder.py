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
        # full-38 is the V38 comparison arm: the `full` roster verbatim on
        # qwen3.8:27b, added for the model-comparison window and pinned here
        # so its presence is a deliberate fact rather than drift.
        profiles = await provider.list_profiles()
        ids = {p.profile_id for p in profiles}
        # full-38-atlas is arm B of the 1.7.0 Atlas A/B (#1160): the same roster with the
        # model named as Atlas serves it. Inert until that deploy selects it.
        # solo is the Solo arm of the 1.8.1 comparison window (SIP-0108 §10i): one generalist
        # process serving every role full-38 serves. Torn down after the window by default
        # (1.8.1 plan §8 decision 12) — its removal moves this line too.
        assert ids == {"smoke", "lite", "full", "full-38", "full-38-atlas", "solo"}


class TestFull38QaCompletionBudget:
    """1.6.5 E (#998 ask 2), amended by #1619. Bug caught: the override is dropped by the
    loader or lands on `full` — either silently changes what the set measures.

    The third concern this class carried, "applied to every role", is now the INTENDED state
    on `full-38` and only there. #1619: per-call caps are agent-level, not task-type scoped
    (SIP-0108 §4.4), so a one-agent comparison arm holds one cap for every task type and the
    squad arm can only match it by carrying the same cap on every member. The flat value is
    what makes the two arms comparable; a per-member cap made them differ on the one thing
    §4.4 says must be equal.
    """

    async def test_every_full_38_member_carries_the_flat_override(self, provider):
        """#1619 resolution 1. Bug this catches: a member added to `full-38` without the cap,
        which reintroduces the per-role difference the window cannot tolerate — and does it
        silently, because the profile still looks like a squad."""
        profile = await provider.get_profile("full-38")

        caps = {a.role: a.config_overrides.get("max_completion_tokens") for a in profile.agents}
        assert set(caps.values()) == {12288}, caps

    async def test_full_is_untouched(self, provider):
        profile = await provider.get_profile("full")
        assert all(not a.config_overrides for a in profile.agents)
