"""Tests for squadops/cycles/agent_config.py (SIP-0097 slice 1).

The fallback test moved from test_correction_protocol.py (it tested the
executor staticmethod this module hoisted); assertions are unmodified
apart from attribute access on the ResolvedAgentConfig dataclass.
"""

from __future__ import annotations

import pytest

from squadops.cycles.agent_config import build_agent_resolver, resolve_agent_config
from squadops.cycles.models import AgentProfileEntry

pytestmark = [pytest.mark.domain_orchestration]


class _ProfileStub:
    agents = (
        AgentProfileEntry(agent_id="strat-a", role="strat", model="m", enabled=True),
        AgentProfileEntry(
            agent_id="data-disabled",
            role="data",
            model="m-data",
            enabled=False,
        ),
    )


class TestResolveAgentConfig:
    def test_resolves_enabled_match_with_model(self):
        """An enabled role match propagates agent_id + model (issue #110:
        without the model the handler silently falls back to the container's
        instance default instead of the cycle's squad profile)."""
        resolved = resolve_agent_config("strat", _ProfileStub())
        assert resolved.agent_id == "strat-a"
        assert resolved.model == "m"
        assert resolved.config_overrides == {}

    def test_falls_back_when_role_absent(self):
        """Helper falls back to the bare role when profile has no enabled match.

        Reachable only via direct calls (the run-level path validates required
        roles upstream), but the fallback exists so a misconfigured profile
        can't crash the correction loop. A disabled agent must not match.
        """
        resolved = resolve_agent_config("data", _ProfileStub())
        assert resolved.agent_id == "data"
        assert resolved.model is None
        assert resolved.config_overrides == {}

    def test_none_profile_falls_back(self):
        """A missing profile (lite/local paths) must not crash resolution."""
        resolved = resolve_agent_config("dev", None)
        assert resolved.agent_id == "dev"
        assert resolved.model is None
        assert resolved.config_overrides == {}


class TestBuildAgentResolver:
    def test_maps_only_enabled_agents(self):
        resolver = build_agent_resolver(_ProfileStub())
        assert resolver == {"strat": "strat-a"}

    def test_none_profile_returns_empty(self):
        assert build_agent_resolver(None) == {}
