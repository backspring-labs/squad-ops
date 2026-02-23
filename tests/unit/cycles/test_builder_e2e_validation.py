"""E2E validation tests for builder role (SIP-0071 Phase 4).

Local validation of builder-aware plan generation, routing diagnostics,
QA handoff artifact flow, and profile integration. These tests exercise
the full plan-generation → handler-resolution path without requiring
Docker services.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from adapters.cycles.config_squad_profile import ConfigSquadProfile
from squadops.bootstrap.handlers import create_handler_registry, HANDLER_CONFIGS
from squadops.capabilities.handlers.build_profiles import (
    ROUTING_BUILDER_PRESENT,
    ROUTING_FALLBACK_NO_BUILDER,
    get_profile,
)
from squadops.cycles.models import (
    AgentProfileEntry,
    Cycle,
    Run,
    SquadProfile,
    TaskFlowPolicy,
)
from squadops.cycles.task_plan import (
    BUILDER_ASSEMBLY_TASK_STEPS,
    _has_builder_role,
    generate_task_plan,
)

pytestmark = [pytest.mark.domain_orchestration]

NOW = datetime(2026, 1, 15, 12, 0, 0, tzinfo=timezone.utc)
CONFIG_PATH = Path(__file__).resolve().parents[3] / "config" / "squad-profiles.yaml"


@pytest.fixture
def builder_profile():
    return SquadProfile(
        profile_id="full-squad-with-builder",
        name="Full Squad with Builder",
        description="6 agents",
        version=1,
        agents=(
            AgentProfileEntry(agent_id="max", role="lead", model="gpt-4", enabled=True),
            AgentProfileEntry(agent_id="neo", role="dev", model="gpt-4", enabled=True),
            AgentProfileEntry(agent_id="nat", role="strat", model="gpt-4", enabled=True),
            AgentProfileEntry(agent_id="bob", role="builder", model="gpt-4", enabled=True),
            AgentProfileEntry(agent_id="eve", role="qa", model="gpt-4", enabled=True),
            AgentProfileEntry(
                agent_id="data-agent", role="data", model="gpt-4", enabled=True,
            ),
        ),
        created_at=NOW,
    )


@pytest.fixture
def run():
    return Run(
        run_id="run_e2e_001",
        cycle_id="cyc_e2e_001",
        run_number=1,
        status="queued",
        initiated_by="api",
        resolved_config_hash="hash_e2e",
    )


def _make_cycle(
    applied_defaults: dict,
    squad_profile_id: str = "full-squad-with-builder",
) -> Cycle:
    return Cycle(
        cycle_id="cyc_e2e_001",
        project_id="e2e_test",
        created_at=NOW,
        created_by="system",
        prd_ref="Build a CLI tool",
        squad_profile_id=squad_profile_id,
        squad_profile_snapshot_ref="sha256:abc",
        task_flow_policy=TaskFlowPolicy(mode="sequential"),
        build_strategy="fresh",
        applied_defaults=applied_defaults,
        execution_overrides={},
    )


# ---------------------------------------------------------------------------
# Routing diagnostics visibility (4.1)
# ---------------------------------------------------------------------------


class TestRoutingDiagnosticsInMetadata:
    """Routing reason must appear on every build step envelope."""

    def test_builder_assemble_has_routing_reason(self, run, builder_profile):
        cycle = _make_cycle({
            "build_tasks": ["builder.assemble", "qa.test"],
        })
        envelopes = generate_task_plan(cycle, run, builder_profile)
        builder_env = next(e for e in envelopes if e.task_type == "builder.assemble")
        assert builder_env.metadata["routing_reason"] == ROUTING_BUILDER_PRESENT

    def test_qa_test_has_routing_reason(self, run, builder_profile):
        cycle = _make_cycle({
            "build_tasks": ["builder.assemble", "qa.test"],
        })
        envelopes = generate_task_plan(cycle, run, builder_profile)
        qa_env = next(e for e in envelopes if e.task_type == "qa.test")
        assert qa_env.metadata["routing_reason"] == ROUTING_BUILDER_PRESENT

    def test_plan_steps_have_no_routing_reason(self, run, builder_profile):
        cycle = _make_cycle({
            "build_tasks": ["builder.assemble", "qa.test"],
        })
        envelopes = generate_task_plan(cycle, run, builder_profile)
        plan_envs = [e for e in envelopes if e.metadata.get("step_index", 99) < 5]
        for env in plan_envs:
            assert "routing_reason" not in env.metadata

    def test_build_step_indices_follow_plan(self, run, builder_profile):
        cycle = _make_cycle({
            "build_tasks": ["builder.assemble", "qa.test"],
        })
        envelopes = generate_task_plan(cycle, run, builder_profile)
        build_envs = [
            e for e in envelopes
            if e.task_type in ("development.develop", "builder.assemble", "qa.test")
        ]
        indices = [e.metadata["step_index"] for e in build_envs]
        assert indices == [5, 6, 7]


# ---------------------------------------------------------------------------
# Builder plan shape (4.1)
# ---------------------------------------------------------------------------


class TestBuilderPlanShape:
    """Full plan+build with builder produces 7 envelopes in correct order."""

    def test_seven_envelopes(self, run, builder_profile):
        cycle = _make_cycle({
            "build_tasks": ["builder.assemble", "qa.test"],
        })
        envelopes = generate_task_plan(cycle, run, builder_profile)
        assert len(envelopes) == 8

    def test_build_step_sequence(self, run, builder_profile):
        cycle = _make_cycle({
            "build_tasks": ["builder.assemble", "qa.test"],
        })
        envelopes = generate_task_plan(cycle, run, builder_profile)
        build_types = [e.task_type for e in envelopes[5:]]
        expected = [step[0] for step in BUILDER_ASSEMBLY_TASK_STEPS]
        assert build_types == expected

    def test_builder_assemble_assigned_to_bob(self, run, builder_profile):
        cycle = _make_cycle({
            "build_tasks": ["builder.assemble", "qa.test"],
        })
        envelopes = generate_task_plan(cycle, run, builder_profile)
        builder_env = next(e for e in envelopes if e.task_type == "builder.assemble")
        assert builder_env.agent_id == "bob"

    def test_qa_step_assigned_to_eve(self, run, builder_profile):
        cycle = _make_cycle({
            "build_tasks": ["builder.assemble", "qa.test"],
        })
        envelopes = generate_task_plan(cycle, run, builder_profile)
        qa_env = next(e for e in envelopes if e.task_type == "qa.test")
        assert qa_env.agent_id == "eve"

    def test_build_only_mode(self, run, builder_profile):
        cycle = _make_cycle({
            "plan_tasks": False,
            "build_tasks": ["builder.assemble", "qa.test"],
        })
        envelopes = generate_task_plan(cycle, run, builder_profile)
        assert len(envelopes) == 3
        assert [e.task_type for e in envelopes] == [
            "development.develop", "builder.assemble", "qa.test",
        ]


# ---------------------------------------------------------------------------
# Handler registry E2E (4.1)
# ---------------------------------------------------------------------------


class TestHandlerRegistryE2E:
    """Handler registry has both builder and legacy handlers registered."""

    def test_builder_assemble_in_full_registry(self):
        registry = create_handler_registry()
        assert "builder.assemble" in registry.list_capabilities()

    def test_development_build_in_full_registry(self):
        registry = create_handler_registry()
        assert "development.develop" in registry.list_capabilities()

    def test_qa_test_in_full_registry(self):
        registry = create_handler_registry()
        assert "qa.test" in registry.list_capabilities()

    def test_builder_handler_config_exists(self):
        handler_classes = [cls for cls, _roles in HANDLER_CONFIGS]
        from squadops.capabilities.handlers.cycle_tasks import BuilderAssembleHandler
        assert BuilderAssembleHandler in handler_classes

    def test_builder_and_dev_build_coexist(self):
        """Both builder.assemble and development.develop registered without conflict."""
        registry = create_handler_registry()
        capabilities = registry.list_capabilities()
        assert "builder.assemble" in capabilities
        assert "development.develop" in capabilities


# ---------------------------------------------------------------------------
# Build profiles accessible (4.1)
# ---------------------------------------------------------------------------


class TestBuildProfileAccessibility:
    """Build profiles required for builder E2E are all resolvable."""

    def test_python_cli_builder_resolvable(self):
        profile = get_profile("python_cli_builder")
        assert profile.name == "python_cli_builder"

    def test_static_web_builder_resolvable(self):
        profile = get_profile("static_web_builder")
        assert profile.name == "static_web_builder"

    def test_web_app_builder_resolvable(self):
        profile = get_profile("web_app_builder")
        assert profile.name == "web_app_builder"


# ---------------------------------------------------------------------------
# YAML profile integration (4.1)
# ---------------------------------------------------------------------------


class TestYAMLProfileBuilderIntegration:
    """Real profile from squad-profiles.yaml validates correctly."""

    @pytest.fixture()
    def provider(self):
        return ConfigSquadProfile(yaml_path=CONFIG_PATH)

    async def test_builder_profile_has_six_agents(self, provider):
        profile = await provider.get_profile("full-squad-with-builder")
        assert len(profile.agents) == 6

    async def test_builder_profile_has_builder_role(self, provider):
        profile = await provider.get_profile("full-squad-with-builder")
        assert _has_builder_role(profile)

    async def test_builder_profile_bob_is_builder(self, provider):
        profile = await provider.get_profile("full-squad-with-builder")
        bob = next(a for a in profile.agents if a.agent_id == "bob")
        assert bob.role == "builder"
        assert bob.enabled is True

    async def test_builder_profile_plan_emits_builder_assemble(self, provider, run):
        profile = await provider.get_profile("full-squad-with-builder")
        cycle = _make_cycle({
            "build_tasks": ["builder.assemble", "qa.test"],
        })
        envelopes = generate_task_plan(cycle, run, profile)
        task_types = [e.task_type for e in envelopes]
        assert "builder.assemble" in task_types

    async def test_builder_profile_routing_reason(self, provider, run):
        profile = await provider.get_profile("full-squad-with-builder")
        cycle = _make_cycle({
            "build_tasks": ["builder.assemble", "qa.test"],
        })
        envelopes = generate_task_plan(cycle, run, profile)
        builder_env = next(e for e in envelopes if e.task_type == "builder.assemble")
        assert builder_env.metadata["routing_reason"] == ROUTING_BUILDER_PRESENT
