"""Local bootstrap verification tests for builder role (SIP-0071 Phase 3).

Tests that the builder role bootstraps cleanly in the handler and skill
registries, and that dry-run plan generation emits builder.build tasks
when the full-squad-with-builder profile is used.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from adapters.cycles.config_squad_profile import ConfigSquadProfile
from squadops.bootstrap.handlers import create_handler_registry
from squadops.bootstrap.skills import get_skills_for_role, create_skill_registry
from squadops.cycles.task_plan import generate_task_plan, _has_builder_role
from squadops.cycles.models import Cycle, Run, TaskFlowPolicy

pytestmark = [pytest.mark.domain_orchestration]

NOW = datetime(2026, 1, 15, 12, 0, 0, tzinfo=timezone.utc)
CONFIG_PATH = Path(__file__).resolve().parents[3] / "config" / "squad-profiles.yaml"


# ---------------------------------------------------------------------------
# Handler registry bootstrap
# ---------------------------------------------------------------------------


class TestBuilderHandlerBootstrap:
    def test_builder_role_produces_handler_registry(self):
        """Builder role should produce a valid handler registry."""
        registry = create_handler_registry(roles=["builder"])
        capabilities = registry.list_capabilities()
        assert "builder.build" in capabilities

    def test_builder_plus_all_roles_no_errors(self):
        """Full registry with builder included should create without errors."""
        registry = create_handler_registry()
        capabilities = registry.list_capabilities()
        assert "builder.build" in capabilities
        assert "development.build" in capabilities
        assert "qa.build_validate" in capabilities


# ---------------------------------------------------------------------------
# Skill registry bootstrap
# ---------------------------------------------------------------------------


class TestBuilderSkillBootstrap:
    def test_builder_skills_discoverable(self):
        """Builder role skills should be discoverable."""
        skills = get_skills_for_role("builder")
        skill_names = [s().name for s in skills]
        assert "artifact_generation" in skill_names

    def test_builder_skill_registry_creates(self):
        """Skill registry with builder role should create without errors."""
        registry = create_skill_registry(roles=["builder"])
        skills = registry.list_skills()
        assert "artifact_generation" in skills


# ---------------------------------------------------------------------------
# Dry-run plan generation
# ---------------------------------------------------------------------------


class TestDryRunPlanGeneration:
    @pytest.fixture()
    def provider(self):
        return ConfigSquadProfile(yaml_path=CONFIG_PATH)

    async def test_plan_emits_builder_build(self, provider):
        """Plan generation with builder profile should emit builder.build."""
        profile = await provider.get_profile("full-squad-with-builder")
        assert _has_builder_role(profile)

        cycle = Cycle(
            cycle_id="dry-run-001",
            project_id="test",
            created_at=NOW,
            created_by="system",
            prd_ref="Build a CLI tool",
            squad_profile_id="full-squad-with-builder",
            squad_profile_snapshot_ref="sha256:abc",
            task_flow_policy=TaskFlowPolicy(mode="sequential"),
            build_strategy="fresh",
            applied_defaults={
                "build_tasks": ["builder.build", "qa.build_validate"],
            },
            execution_overrides={},
        )
        run = Run(
            run_id="run_dry_001",
            cycle_id="dry-run-001",
            run_number=1,
            status="queued",
            initiated_by="api",
            resolved_config_hash="hash",
        )

        envelopes = generate_task_plan(cycle, run, profile)
        task_types = [e.task_type for e in envelopes]

        assert "builder.build" in task_types
        assert "development.build" not in task_types

    async def test_plan_without_builder_falls_back(self, provider):
        """Plan generation without builder should emit development.build."""
        profile = await provider.get_profile("full-squad")
        assert not _has_builder_role(profile)

        cycle = Cycle(
            cycle_id="dry-run-002",
            project_id="test",
            created_at=NOW,
            created_by="system",
            prd_ref="Build a CLI tool",
            squad_profile_id="full-squad",
            squad_profile_snapshot_ref="sha256:abc",
            task_flow_policy=TaskFlowPolicy(mode="sequential"),
            build_strategy="fresh",
            applied_defaults={
                "build_tasks": ["development.build", "qa.build_validate"],
            },
            execution_overrides={},
        )
        run = Run(
            run_id="run_dry_002",
            cycle_id="dry-run-002",
            run_number=1,
            status="queued",
            initiated_by="api",
            resolved_config_hash="hash",
        )

        envelopes = generate_task_plan(cycle, run, profile)
        task_types = [e.task_type for e in envelopes]

        assert "development.build" in task_types
        assert "builder.build" not in task_types
