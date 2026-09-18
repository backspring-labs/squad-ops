"""Tests for squadops/cycles/agent_config.py (SIP-0097 slice 1).

The fallback test moved from test_correction_protocol.py (it tested the
executor staticmethod this module hoisted); assertions are unmodified
apart from attribute access on the ResolvedAgentConfig dataclass.
"""

from __future__ import annotations

import pytest

from squadops.cycles.agent_config import (
    UnservedRoleError,
    build_agent_resolver,
    resolve_agent_config,
    roles_served,
    served_roles,
    serves_role,
)
from squadops.cycles.models import AgentProfileEntry

pytestmark = [pytest.mark.domain_orchestration]


class _ProfileStub:
    profile_id = "stub"
    agents = (
        AgentProfileEntry(agent_id="strat-a", role="strat", model="m", enabled=True),
        AgentProfileEntry(
            agent_id="data-disabled",
            role="data",
            model="m-data",
            enabled=False,
        ),
    )


class _SoloProfileStub:
    """One agent serving every role — the shape the comparison window's arm needs."""

    profile_id = "solo"
    agents = (
        AgentProfileEntry(
            agent_id="han",
            role="generalist",
            model="m",
            enabled=True,
            config_overrides={"max_completion_tokens": 12288},
            serves_roles=("lead", "strat", "dev", "qa", "data", "builder"),
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

    def test_an_unserved_role_is_refused_and_names_what_the_profile_does_serve(self):
        """#1598-era behaviour deleted (SIP-0108 §10i item 1): an unmatched role used to
        resolve to ``ResolvedAgentConfig(role, None, {})`` — an agent id equal to the role,
        which is a queue no agent consumes. Nothing failed at resolution; the envelope was
        published and the run waited out its budget.

        What the deleted fallback produced and who consumed it: a ``ResolvedAgentConfig``
        whose ``agent_id`` was the role name, consumed by the correction runner, the repair
        dispatcher and ``build_task_envelopes`` as a queue name. Its only other consumer was
        this test. A disabled agent must still not match.
        """
        with pytest.raises(UnservedRoleError) as excinfo:
            resolve_agent_config("data", _ProfileStub())
        message = str(excinfo.value)
        assert "'data'" in message
        assert "'stub'" in message
        # The reader is told what IS served, so the fix does not need a second look.
        assert "['strat']" in message

    def test_no_profile_is_refused_rather_than_resolved(self):
        """A role cannot be resolved without a profile, and pretending otherwise was the
        same silent queue. A cycle names its squad profile at creation."""
        with pytest.raises(UnservedRoleError, match="no squad profile is bound"):
            resolve_agent_config("dev", None)

    def test_one_agent_serving_every_role_resolves_each_with_its_overrides(self):
        """The Solo arm's shape: every step role resolves to the one agent, carrying the
        per-task-type override the squad reproduced on its qa member."""
        for role in ("lead", "strat", "dev", "qa", "data", "builder"):
            resolved = resolve_agent_config(role, _SoloProfileStub())
            assert resolved.agent_id == "han"
            assert resolved.config_overrides == {"max_completion_tokens": 12288}

    def test_a_declared_map_does_not_answer_for_the_agents_own_role_name(self):
        """``serves_roles`` REPLACES the identity, it does not extend it — otherwise a
        profile could not withhold a role from an agent that happens to be named for it."""
        with pytest.raises(UnservedRoleError):
            resolve_agent_config("generalist", _SoloProfileStub())


class TestBuildAgentResolver:
    def test_maps_only_enabled_agents(self):
        resolver = build_agent_resolver(_ProfileStub())
        assert resolver == {"strat": "strat-a"}

    def test_none_profile_returns_empty(self):
        assert build_agent_resolver(None) == {}

    def test_every_declared_role_maps_to_the_one_agent(self):
        """The map the executor hands the repair dispatcher (``_dispatch_repair``'s
        ``agent_resolver``). Bug this catches: reading one role per agent leaves a one-agent
        profile resolving only ``generalist``, so every repair is dispatched to a queue that
        does not exist and the run waits out its budget."""
        assert build_agent_resolver(_SoloProfileStub()) == {
            "lead": "han",
            "strat": "han",
            "dev": "han",
            "qa": "han",
            "data": "han",
            "builder": "han",
        }


class TestServedRoles:
    def test_the_three_readers_see_the_declared_map(self):
        """``served_roles`` is what create-time preflight, plan building and
        implementation-plan validation all ask; a disabled agent contributes nothing."""
        assert served_roles(_SoloProfileStub()) == frozenset(
            {"lead", "strat", "dev", "qa", "data", "builder"}
        )
        assert served_roles(_ProfileStub()) == frozenset({"strat"})
        assert served_roles(None) == frozenset()

    def test_an_empty_declaration_is_the_identity_map(self):
        """A present-but-empty declaration means the same as none — otherwise every profile
        on main would have to be rewritten to keep working."""
        entry = AgentProfileEntry(agent_id="neo", role="dev", model="m", enabled=True)
        assert roles_served(entry) == ("dev",)
        assert serves_role(_ProfileStub(), "strat") is True
        assert serves_role(_ProfileStub(), "data") is False
