"""Legacy parity tests for SIP-0071 Phase 4.

Verifies that 5-agent mode is completely unaffected by the addition
of the builder role. These tests guard against regressions where
builder code paths accidentally alter existing behavior.

The 5-agent squad (lead, dev, strat, qa, data) must:
- Produce ``development.develop`` in the task plan (not ``builder.assemble``)
- Emit ``fallback_no_builder`` routing reason on build steps
- Resolve agent_id=neo for the build step (dev role)
- Generate the same 5-step plan when no build_tasks are configured
- Work with the real ``full-squad`` profile from squad-profiles.yaml
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from adapters.cycles.config_squad_profile import ConfigSquadProfile
from squadops.capabilities.handlers.build_profiles import (
    ROUTING_FALLBACK_NO_BUILDER,
)
from squadops.cycles.models import (
    AgentProfileEntry,
    Cycle,
    Run,
    SquadProfile,
    TaskFlowPolicy,
)
from squadops.cycles.task_plan import (
    BUILD_TASK_STEPS,
    CYCLE_TASK_STEPS,
    _has_builder_role,
    generate_task_plan,
)

pytestmark = [pytest.mark.domain_orchestration]

NOW = datetime(2026, 1, 15, 12, 0, 0, tzinfo=UTC)
CONFIG_PATH = Path(__file__).resolve().parents[3] / "config" / "squad-profiles.yaml"


@pytest.fixture
def five_agent_profile():
    """Standard 5-agent profile (no builder)."""
    return SquadProfile(
        profile_id="full-squad",
        name="Full Squad",
        description="All 5 agents",
        version=1,
        agents=(
            AgentProfileEntry(agent_id="max", role="lead", model="gpt-4", enabled=True),
            AgentProfileEntry(agent_id="neo", role="dev", model="gpt-4", enabled=True),
            AgentProfileEntry(agent_id="nat", role="strat", model="gpt-4", enabled=True),
            AgentProfileEntry(agent_id="eve", role="qa", model="gpt-4", enabled=True),
            AgentProfileEntry(
                agent_id="data-agent",
                role="data",
                model="gpt-4",
                enabled=True,
            ),
        ),
        created_at=NOW,
    )


@pytest.fixture
def run():
    return Run(
        run_id="run_legacy_001",
        cycle_id="cyc_legacy_001",
        run_number=1,
        status="queued",
        initiated_by="api",
        resolved_config_hash="hash_legacy",
    )


def _make_cycle(applied_defaults: dict) -> Cycle:
    return Cycle(
        cycle_id="cyc_legacy_001",
        project_id="legacy_test",
        created_at=NOW,
        created_by="system",
        prd_ref="Build a CLI tool",
        squad_profile_id="full-squad",
        squad_profile_snapshot_ref="sha256:abc",
        task_flow_policy=TaskFlowPolicy(mode="sequential"),
        build_strategy="fresh",
        applied_defaults=applied_defaults,
        execution_overrides={},
    )


# ---------------------------------------------------------------------------
# Plan-only mode (no build tasks)
# ---------------------------------------------------------------------------


class TestLegacyPlanOnlyMode:
    """5-agent plan-only cycle — zero build tasks, 5 plan steps."""

    def test_five_plan_steps(self, run, five_agent_profile):
        cycle = _make_cycle({})
        envelopes = generate_task_plan(cycle, run, five_agent_profile)
        assert len(envelopes) == 5

    def test_plan_task_types_unchanged(self, run, five_agent_profile):
        cycle = _make_cycle({})
        envelopes = generate_task_plan(cycle, run, five_agent_profile)
        expected = [step[0] for step in CYCLE_TASK_STEPS]
        assert [e.task_type for e in envelopes] == expected

    def test_no_routing_reason_on_plan_steps(self, run, five_agent_profile):
        cycle = _make_cycle({})
        envelopes = generate_task_plan(cycle, run, five_agent_profile)
        for env in envelopes:
            assert "routing_reason" not in env.metadata

    def test_no_builder_assemble_anywhere(self, run, five_agent_profile):
        cycle = _make_cycle({})
        envelopes = generate_task_plan(cycle, run, five_agent_profile)
        assert all(e.task_type != "builder.assemble" for e in envelopes)


# ---------------------------------------------------------------------------
# Plan + build mode (legacy dev builds)
# ---------------------------------------------------------------------------


class TestLegacyPlanPlusBuild:
    """5-agent plan+build cycle — development.develop, NOT builder.assemble."""

    def test_seven_total_envelopes(self, run, five_agent_profile):
        cycle = _make_cycle(
            {
                "build_tasks": ["development.develop", "qa.test"],
            }
        )
        envelopes = generate_task_plan(cycle, run, five_agent_profile)
        assert len(envelopes) == 7

    def test_development_build_emitted(self, run, five_agent_profile):
        cycle = _make_cycle(
            {
                "build_tasks": ["development.develop", "qa.test"],
            }
        )
        envelopes = generate_task_plan(cycle, run, five_agent_profile)
        task_types = [e.task_type for e in envelopes]
        assert "development.develop" in task_types

    def test_no_builder_assemble(self, run, five_agent_profile):
        cycle = _make_cycle(
            {
                "build_tasks": ["development.develop", "qa.test"],
            }
        )
        envelopes = generate_task_plan(cycle, run, five_agent_profile)
        task_types = [e.task_type for e in envelopes]
        assert "builder.assemble" not in task_types

    def test_build_step_assigned_to_neo(self, run, five_agent_profile):
        cycle = _make_cycle(
            {
                "build_tasks": ["development.develop", "qa.test"],
            }
        )
        envelopes = generate_task_plan(cycle, run, five_agent_profile)
        build_envs = [e for e in envelopes if e.task_type == "development.develop"]
        assert len(build_envs) == 1
        assert build_envs[0].agent_id == "neo"

    def test_fallback_routing_reason(self, run, five_agent_profile):
        cycle = _make_cycle(
            {
                "build_tasks": ["development.develop", "qa.test"],
            }
        )
        envelopes = generate_task_plan(cycle, run, five_agent_profile)
        build_envs = [e for e in envelopes if e.task_type in ("development.develop", "qa.test")]
        for env in build_envs:
            assert env.metadata["routing_reason"] == ROUTING_FALLBACK_NO_BUILDER

    def test_plan_steps_unchanged_in_combined_mode(self, run, five_agent_profile):
        cycle = _make_cycle(
            {
                "build_tasks": ["development.develop", "qa.test"],
            }
        )
        envelopes = generate_task_plan(cycle, run, five_agent_profile)
        plan_types = [e.task_type for e in envelopes[:5]]
        expected = [step[0] for step in CYCLE_TASK_STEPS]
        assert plan_types == expected

    def test_build_step_sequence(self, run, five_agent_profile):
        cycle = _make_cycle(
            {
                "build_tasks": ["development.develop", "qa.test"],
            }
        )
        envelopes = generate_task_plan(cycle, run, five_agent_profile)
        build_types = [e.task_type for e in envelopes[5:]]
        expected = [step[0] for step in BUILD_TASK_STEPS]
        assert build_types == expected


# ---------------------------------------------------------------------------
# Real YAML profile integration
# ---------------------------------------------------------------------------


class TestLegacyYAMLProfileIntegration:
    """Tests using the real full-squad profile from squad-profiles.yaml."""

    @pytest.fixture()
    def provider(self):
        return ConfigSquadProfile(yaml_path=CONFIG_PATH)

    async def test_full_squad_has_no_builder(self, provider):
        profile = await provider.get_profile("full-squad")
        assert not _has_builder_role(profile)

    async def test_full_squad_has_five_agents(self, provider):
        profile = await provider.get_profile("full-squad")
        assert len(profile.agents) == 5

    async def test_full_squad_plan_emits_development_build(self, provider, run):
        profile = await provider.get_profile("full-squad")
        cycle = _make_cycle(
            {
                "build_tasks": ["development.develop", "qa.test"],
            }
        )
        envelopes = generate_task_plan(cycle, run, profile)
        task_types = [e.task_type for e in envelopes]
        assert "development.develop" in task_types
        assert "builder.assemble" not in task_types

    async def test_full_squad_plan_only_five_steps(self, provider, run):
        profile = await provider.get_profile("full-squad")
        cycle = _make_cycle({})
        envelopes = generate_task_plan(cycle, run, profile)
        assert len(envelopes) == 5

    async def test_full_squad_build_route_reason(self, provider, run):
        profile = await provider.get_profile("full-squad")
        cycle = _make_cycle(
            {
                "build_tasks": ["development.develop", "qa.test"],
            }
        )
        envelopes = generate_task_plan(cycle, run, profile)
        build_envs = [e for e in envelopes if e.task_type in ("development.develop", "qa.test")]
        for env in build_envs:
            assert env.metadata["routing_reason"] == ROUTING_FALLBACK_NO_BUILDER
