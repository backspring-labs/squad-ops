"""Unit tests for cycle DTO mapping — profile_to_response with role_label and display_name."""

from __future__ import annotations

from datetime import UTC, datetime

from squadops.api.routes.cycles.mapping import profile_to_response
from squadops.cycles.models import AgentProfileEntry, SquadProfile


class TestProfileToResponse:
    def _make_profile(self, agents: tuple) -> SquadProfile:
        return SquadProfile(
            profile_id="full-squad",
            name="Full Squad",
            description="All agents",
            version=1,
            agents=agents,
            created_at=datetime(2025, 6, 1, tzinfo=UTC),
        )

    def test_role_label_populated(self):
        profile = self._make_profile((
            AgentProfileEntry(
                agent_id="neo", role="dev", model="qwen2.5:7b", enabled=True
            ),
        ))
        resp = profile_to_response(profile)
        agent = resp.agents[0]
        assert agent.role_label == "Developer"

    def test_display_name_from_agent_id(self):
        profile = self._make_profile((
            AgentProfileEntry(
                agent_id="max", role="lead", model="qwen2.5:7b", enabled=True
            ),
        ))
        resp = profile_to_response(profile)
        agent = resp.agents[0]
        assert agent.display_name == "Max"

    def test_unknown_role_gets_title_label(self):
        profile = self._make_profile((
            AgentProfileEntry(
                agent_id="zara", role="custom_role", model="qwen2.5:7b", enabled=True
            ),
        ))
        resp = profile_to_response(profile)
        agent = resp.agents[0]
        assert agent.role_label == "Custom_Role"
        assert agent.display_name == "Zara"

    def test_all_agents_get_labels(self):
        agents = (
            AgentProfileEntry(agent_id="max", role="lead", model="m", enabled=True),
            AgentProfileEntry(agent_id="neo", role="dev", model="m", enabled=True),
            AgentProfileEntry(agent_id="nat", role="strat", model="m", enabled=True),
            AgentProfileEntry(agent_id="eve", role="qa", model="m", enabled=True),
            AgentProfileEntry(agent_id="data", role="data", model="m", enabled=True),
            AgentProfileEntry(agent_id="bob", role="builder", model="m", enabled=True),
        )
        profile = self._make_profile(agents)
        resp = profile_to_response(profile)

        for agent in resp.agents:
            assert agent.role_label is not None
            assert agent.display_name is not None
