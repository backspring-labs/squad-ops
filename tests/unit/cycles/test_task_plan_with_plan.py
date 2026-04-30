"""Tests for generate_task_plan() with manifest (SIP-0086 Phase 3a)."""

from __future__ import annotations

import pytest

from datetime import datetime, timezone

from squadops.cycles.implementation_plan import ImplementationPlan
from squadops.cycles.models import (
    AgentProfileEntry,
    Cycle,
    Run,
    SquadProfile,
    TaskFlowPolicy,
)
from squadops.cycles.task_plan import generate_task_plan

NOW = datetime(2026, 3, 31, tzinfo=timezone.utc)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

MANIFEST_YAML = """\
version: 1
project_id: group_run
cycle_id: cyc_test
prd_hash: abc123
tasks:
  - task_index: 0
    task_type: development.develop
    role: dev
    focus: "Backend models"
    description: "Create models"
    expected_artifacts: ["backend/models.py"]
    acceptance_criteria: ["Models exist"]
    depends_on: []
  - task_index: 1
    task_type: development.develop
    role: dev
    focus: "Backend API"
    description: "Create endpoints"
    expected_artifacts: ["backend/main.py"]
    depends_on: [0]
  - task_index: 2
    task_type: development.develop
    role: dev
    focus: "Frontend shell"
    description: "Create React app"
    expected_artifacts: ["frontend/App.jsx"]
    depends_on: []
  - task_index: 3
    task_type: qa.test
    role: qa
    focus: "Backend tests"
    description: "Write tests"
    expected_artifacts: ["tests/test_api.py"]
    depends_on: [0, 1]
summary:
  total_dev_tasks: 3
  total_qa_tasks: 1
  total_tasks: 4
  estimated_layers: [backend, frontend, test]
"""


def _make_cycle(**overrides) -> Cycle:
    defaults = {
        "cycle_id": "cyc_test",
        "project_id": "group_run",
        "created_at": NOW,
        "created_by": "system",
        "prd_ref": "Build a group run app",
        "squad_profile_id": "full-squad",
        "squad_profile_snapshot_ref": "sha256:abc",
        "task_flow_policy": TaskFlowPolicy(mode="sequential"),
        "build_strategy": "fresh",
        "applied_defaults": {
            "plan_tasks": True,
            "build_tasks": True,
        },
        "execution_overrides": {},
        "expected_artifact_types": ["source", "test"],
    }
    defaults.update(overrides)
    return Cycle(**defaults)


def _make_run(**overrides) -> Run:
    defaults = {
        "run_id": "run_abcdef123456",
        "cycle_id": "cyc_test",
        "run_number": 1,
        "status": "running",
        "initiated_by": "api",
        "resolved_config_hash": "hash123",
    }
    defaults.update(overrides)
    return Run(**defaults)


def _make_profile() -> SquadProfile:
    return SquadProfile(
        profile_id="full-squad",
        name="Full Squad",
        description="Test profile",
        version=1,
        agents=[
            AgentProfileEntry(agent_id="max", role="lead", model="test", enabled=True),
            AgentProfileEntry(agent_id="neo", role="dev", model="test", enabled=True),
            AgentProfileEntry(agent_id="nat", role="strat", model="test", enabled=True),
            AgentProfileEntry(agent_id="eve", role="qa", model="test", enabled=True),
            AgentProfileEntry(agent_id="data", role="data", model="test", enabled=True),
        ],
        created_at=NOW,
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestGenerateTaskPlanWithManifest:
    def test_manifest_produces_correct_envelope_count(self):
        manifest = ImplementationPlan.from_yaml(MANIFEST_YAML)
        cycle = _make_cycle()
        run = _make_run()
        profile = _make_profile()

        envelopes = generate_task_plan(cycle, run, profile, plan=manifest)

        # 5 planning steps + 4 manifest build steps = 9
        assert len(envelopes) == 9

    def test_without_manifest_produces_static_steps(self):
        cycle = _make_cycle()
        run = _make_run()
        profile = _make_profile()

        envelopes = generate_task_plan(cycle, run, profile, plan=None)

        # 5 planning steps + 2 static build steps = 7
        assert len(envelopes) == 7

    def test_manifest_envelopes_have_deterministic_ids(self):
        manifest = ImplementationPlan.from_yaml(MANIFEST_YAML)
        cycle = _make_cycle()
        run = _make_run()
        profile = _make_profile()

        envelopes = generate_task_plan(cycle, run, profile, plan=manifest)

        # Manifest-derived envelopes are the last 4
        manifest_envelopes = envelopes[5:]
        assert len(manifest_envelopes) == 4

        # Check RC-2 deterministic ID format
        assert manifest_envelopes[0].task_id == (
            "task-run_abcdef12-m000-development.develop"
        )
        assert manifest_envelopes[1].task_id == (
            "task-run_abcdef12-m001-development.develop"
        )
        assert manifest_envelopes[3].task_id == (
            "task-run_abcdef12-m003-qa.test"
        )

    def test_manifest_envelopes_have_subtask_focus(self):
        manifest = ImplementationPlan.from_yaml(MANIFEST_YAML)
        cycle = _make_cycle()
        run = _make_run()
        profile = _make_profile()

        envelopes = generate_task_plan(cycle, run, profile, plan=manifest)

        build_env = envelopes[5]  # First manifest task
        assert build_env.inputs["subtask_focus"] == "Backend models"
        assert build_env.inputs["subtask_description"] == "Create models"
        assert build_env.inputs["expected_artifacts"] == ["backend/models.py"]
        assert build_env.inputs["subtask_index"] == 0

    def test_manifest_envelopes_have_acceptance_criteria(self):
        manifest = ImplementationPlan.from_yaml(MANIFEST_YAML)
        cycle = _make_cycle()
        run = _make_run()
        profile = _make_profile()

        envelopes = generate_task_plan(cycle, run, profile, plan=manifest)

        build_env = envelopes[5]
        assert build_env.inputs["acceptance_criteria"] == ["Models exist"]

    def test_causation_chain_links_sequentially(self):
        manifest = ImplementationPlan.from_yaml(MANIFEST_YAML)
        cycle = _make_cycle()
        run = _make_run()
        profile = _make_profile()

        envelopes = generate_task_plan(cycle, run, profile, plan=manifest)

        # Each envelope's causation_id should be the previous task's task_id
        for i in range(1, len(envelopes)):
            assert envelopes[i].causation_id == envelopes[i - 1].task_id

    def test_planning_steps_preserved_before_manifest(self):
        manifest = ImplementationPlan.from_yaml(MANIFEST_YAML)
        cycle = _make_cycle()
        run = _make_run()
        profile = _make_profile()

        envelopes = generate_task_plan(cycle, run, profile, plan=manifest)

        # First 5 are planning steps
        planning_types = [e.task_type for e in envelopes[:5]]
        assert planning_types == [
            "strategy.analyze_prd",
            "development.design",
            "qa.validate",
            "data.report",
            "governance.review",
        ]

    def test_planning_envelopes_have_no_subtask_focus(self):
        manifest = ImplementationPlan.from_yaml(MANIFEST_YAML)
        cycle = _make_cycle()
        run = _make_run()
        profile = _make_profile()

        envelopes = generate_task_plan(cycle, run, profile, plan=manifest)

        for env in envelopes[:5]:
            assert "subtask_focus" not in env.inputs

    def test_missing_role_raises_cycle_error(self):
        manifest = ImplementationPlan.from_yaml(MANIFEST_YAML)
        cycle = _make_cycle()
        run = _make_run()
        # Profile without qa role
        profile = SquadProfile(
            profile_id="no-qa",
            name="No QA",
            description="Missing QA",
            version=1,
            agents=[
                AgentProfileEntry(
                    agent_id="max", role="lead", model="test", enabled=True
                ),
                AgentProfileEntry(
                    agent_id="neo", role="dev", model="test", enabled=True
                ),
                AgentProfileEntry(
                    agent_id="nat", role="strat", model="test", enabled=True
                ),
                AgentProfileEntry(
                    agent_id="data", role="data", model="test", enabled=True
                ),
            ],
            created_at=NOW,
        )

        from squadops.cycles.models import CycleError

        with pytest.raises(CycleError, match="qa"):
            generate_task_plan(cycle, run, profile, plan=manifest)

    def test_task_id_namespaces_do_not_collide(self):
        """Planning (UUID), manifest (-m{idx}-), correction (corr-) are distinct."""
        manifest = ImplementationPlan.from_yaml(MANIFEST_YAML)
        cycle = _make_cycle()
        run = _make_run()
        profile = _make_profile()

        envelopes = generate_task_plan(cycle, run, profile, plan=manifest)

        planning_ids = [e.task_id for e in envelopes[:5]]
        manifest_ids = [e.task_id for e in envelopes[5:]]

        # Planning IDs are UUIDs (hex), manifest IDs start with "task-"
        for pid in planning_ids:
            assert not pid.startswith("task-"), f"Planning ID should be UUID: {pid}"
        for mid in manifest_ids:
            assert mid.startswith("task-"), f"Manifest ID should be deterministic: {mid}"
            assert "-m" in mid, f"Manifest ID should use -m namespace: {mid}"

    def test_no_build_tasks_skips_manifest(self):
        """Manifest is ignored when build_tasks is not enabled."""
        manifest = ImplementationPlan.from_yaml(MANIFEST_YAML)
        cycle = _make_cycle(applied_defaults={"plan_tasks": True, "build_tasks": False})
        run = _make_run()
        profile = _make_profile()

        envelopes = generate_task_plan(cycle, run, profile, plan=manifest)

        # Only planning steps, no build steps at all
        assert len(envelopes) == 5
        assert all("subtask_focus" not in e.inputs for e in envelopes)
