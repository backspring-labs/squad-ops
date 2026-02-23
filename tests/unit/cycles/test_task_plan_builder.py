"""Tests for builder-aware task plan routing (SIP-0071).

Validates that generate_task_plan routes build tasks to builder.assemble
when a builder role is present in the squad profile, and falls back to
development.develop when absent.
"""
from datetime import datetime, timezone

import pytest

from squadops.capabilities.handlers.build_profiles import (
    ROUTING_BUILDER_PRESENT,
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
    BUILDER_ASSEMBLY_TASK_STEPS,
    _has_builder_role,
    generate_task_plan,
)

pytestmark = [pytest.mark.domain_orchestration]

NOW = datetime(2026, 1, 15, 12, 0, 0, tzinfo=timezone.utc)


@pytest.fixture
def profile_with_builder():
    return SquadProfile(
        profile_id="full-squad-with-builder",
        name="Full Squad with Builder",
        description="6 agents",
        version=1,
        agents=(
            AgentProfileEntry(agent_id="nat", role="strat", model="gpt-4", enabled=True),
            AgentProfileEntry(agent_id="neo", role="dev", model="gpt-4", enabled=True),
            AgentProfileEntry(agent_id="eve", role="qa", model="gpt-4", enabled=True),
            AgentProfileEntry(
                agent_id="data-agent", role="data", model="gpt-4", enabled=True
            ),
            AgentProfileEntry(agent_id="max", role="lead", model="gpt-4", enabled=True),
            AgentProfileEntry(agent_id="bob", role="builder", model="gpt-4", enabled=True),
        ),
        created_at=NOW,
    )


@pytest.fixture
def profile_without_builder():
    return SquadProfile(
        profile_id="full-squad",
        name="Full Squad",
        description="5 agents",
        version=1,
        agents=(
            AgentProfileEntry(agent_id="nat", role="strat", model="gpt-4", enabled=True),
            AgentProfileEntry(agent_id="neo", role="dev", model="gpt-4", enabled=True),
            AgentProfileEntry(agent_id="eve", role="qa", model="gpt-4", enabled=True),
            AgentProfileEntry(
                agent_id="data-agent", role="data", model="gpt-4", enabled=True
            ),
            AgentProfileEntry(agent_id="max", role="lead", model="gpt-4", enabled=True),
        ),
        created_at=NOW,
    )


@pytest.fixture
def run():
    return Run(
        run_id="run_001",
        cycle_id="cyc_001",
        run_number=1,
        status="queued",
        initiated_by="api",
        resolved_config_hash="config_hash_abc",
    )


def _make_cycle(applied_defaults: dict) -> Cycle:
    return Cycle(
        cycle_id="cyc_001",
        project_id="test_project",
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
# _has_builder_role
# ---------------------------------------------------------------------------


class TestHasBuilderRole:
    def test_detects_builder_present(self, profile_with_builder):
        assert _has_builder_role(profile_with_builder) is True

    def test_no_builder_returns_false(self, profile_without_builder):
        assert _has_builder_role(profile_without_builder) is False

    def test_disabled_builder_returns_false(self):
        profile = SquadProfile(
            profile_id="test",
            name="Test",
            description="Test",
            version=1,
            agents=(
                AgentProfileEntry(
                    agent_id="bob", role="builder", model="gpt-4", enabled=False
                ),
            ),
            created_at=NOW,
        )
        assert _has_builder_role(profile) is False


# ---------------------------------------------------------------------------
# Builder routing: builder present → builder.assemble
# ---------------------------------------------------------------------------


class TestBuilderRouting:
    def test_emits_builder_assemble_when_builder_present(
        self, run, profile_with_builder,
    ):
        cycle = _make_cycle({
            "build_tasks": ["builder.assemble", "qa.test"],
        })
        envelopes = generate_task_plan(cycle, run, profile_with_builder)

        task_types = [e.task_type for e in envelopes]
        assert "builder.assemble" in task_types

    def test_builder_assemble_assigned_to_bob(self, run, profile_with_builder):
        cycle = _make_cycle({
            "build_tasks": ["builder.assemble", "qa.test"],
        })
        envelopes = generate_task_plan(cycle, run, profile_with_builder)

        builder_envs = [e for e in envelopes if e.task_type == "builder.assemble"]
        assert len(builder_envs) == 1
        assert builder_envs[0].agent_id == "bob"

    def test_builder_assemble_has_builder_role_in_metadata(
        self, run, profile_with_builder,
    ):
        cycle = _make_cycle({
            "build_tasks": ["builder.assemble", "qa.test"],
        })
        envelopes = generate_task_plan(cycle, run, profile_with_builder)

        builder_envs = [e for e in envelopes if e.task_type == "builder.assemble"]
        assert builder_envs[0].metadata["role"] == "builder"


# ---------------------------------------------------------------------------
# Fallback routing: no builder → development.develop
# ---------------------------------------------------------------------------


class TestFallbackRouting:
    def test_emits_development_build_when_no_builder(
        self, run, profile_without_builder,
    ):
        cycle = _make_cycle({
            "build_tasks": ["development.develop", "qa.test"],
        })
        envelopes = generate_task_plan(cycle, run, profile_without_builder)

        task_types = [e.task_type for e in envelopes]
        assert "development.develop" in task_types
        assert "builder.assemble" not in task_types

    def test_no_build_tasks_no_build_steps(self, run, profile_without_builder):
        cycle = _make_cycle({})
        envelopes = generate_task_plan(cycle, run, profile_without_builder)

        task_types = [e.task_type for e in envelopes]
        assert "development.develop" not in task_types
        assert "builder.assemble" not in task_types
        assert len(envelopes) == 5


# ---------------------------------------------------------------------------
# Routing reason metadata (D14)
# ---------------------------------------------------------------------------


class TestRoutingReason:
    def test_builder_present_routing_reason(self, run, profile_with_builder):
        cycle = _make_cycle({
            "build_tasks": ["builder.assemble", "qa.test"],
        })
        envelopes = generate_task_plan(cycle, run, profile_with_builder)

        build_envs = [
            e for e in envelopes
            if e.task_type in ("builder.assemble", "qa.test")
        ]
        for env in build_envs:
            assert env.metadata["routing_reason"] == ROUTING_BUILDER_PRESENT

    def test_fallback_routing_reason(self, run, profile_without_builder):
        cycle = _make_cycle({
            "build_tasks": ["development.develop", "qa.test"],
        })
        envelopes = generate_task_plan(cycle, run, profile_without_builder)

        build_envs = [
            e for e in envelopes
            if e.task_type in ("development.develop", "qa.test")
        ]
        for env in build_envs:
            assert env.metadata["routing_reason"] == ROUTING_FALLBACK_NO_BUILDER

    def test_routing_reason_only_on_build_steps(self, run, profile_with_builder):
        cycle = _make_cycle({
            "build_tasks": ["builder.assemble", "qa.test"],
        })
        envelopes = generate_task_plan(cycle, run, profile_with_builder)

        plan_envs = [
            e for e in envelopes
            if e.task_type not in ("development.develop", "builder.assemble", "qa.test")
        ]
        for env in plan_envs:
            assert "routing_reason" not in env.metadata

    def test_routing_reason_uses_constants_not_free_text(
        self, run, profile_with_builder,
    ):
        cycle = _make_cycle({
            "build_tasks": ["builder.assemble", "qa.test"],
        })
        envelopes = generate_task_plan(cycle, run, profile_with_builder)

        valid_reasons = {ROUTING_BUILDER_PRESENT, ROUTING_FALLBACK_NO_BUILDER}
        for env in envelopes:
            reason = env.metadata.get("routing_reason")
            if reason is not None:
                assert reason in valid_reasons


# ---------------------------------------------------------------------------
# Plan + build step count
# ---------------------------------------------------------------------------


class TestPlanPlusBuildWithBuilder:
    def test_plan_plus_build_7_envelopes(self, run, profile_with_builder):
        cycle = _make_cycle({
            "build_tasks": ["builder.assemble", "qa.test"],
        })
        envelopes = generate_task_plan(cycle, run, profile_with_builder)
        assert len(envelopes) == 8

    def test_build_only_2_envelopes(self, run, profile_with_builder):
        cycle = _make_cycle({
            "plan_tasks": False,
            "build_tasks": ["builder.assemble", "qa.test"],
        })
        envelopes = generate_task_plan(cycle, run, profile_with_builder)
        assert len(envelopes) == 3
        task_types = [e.task_type for e in envelopes]
        assert task_types == ["development.develop", "builder.assemble", "qa.test"]
