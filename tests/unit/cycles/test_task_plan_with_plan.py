"""Tests for generate_task_plan() with manifest (SIP-0086 Phase 3a)."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from squadops.cycles.implementation_plan import ImplementationPlan
from squadops.cycles.models import (
    AgentProfileEntry,
    Cycle,
    Run,
    SquadProfile,
    TaskFlowPolicy,
)
from squadops.cycles.task_plan import generate_task_plan

NOW = datetime(2026, 3, 31, tzinfo=UTC)


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
        "squad_profile_id": "full",
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
        profile_id="full",
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

    def test_per_agent_role_numbering(self):
        """#94: each envelope carries a 1-based role_index + role_total counted
        per agent (≈ per role), in dispatch order. With this manifest neo (dev)
        runs 1 planning + 3 build tasks = 4 (numbered 1/4..4/4) and eve (qa) runs
        1 planning + 1 build = 2 — the per-role progress the global index hid."""
        from collections import defaultdict

        manifest = ImplementationPlan.from_yaml(MANIFEST_YAML)
        envelopes = generate_task_plan(_make_cycle(), _make_run(), _make_profile(), plan=manifest)

        by_agent: dict[str, list[tuple[int, int]]] = defaultdict(list)
        for e in envelopes:
            by_agent[e.agent_id].append((e.inputs["role_index"], e.inputs["role_total"]))

        assert by_agent["neo"] == [(1, 4), (2, 4), (3, 4), (4, 4)]  # dev
        assert by_agent["eve"] == [(1, 2), (2, 2)]  # qa
        assert by_agent["max"] == [(1, 1)]  # lead
        assert by_agent["nat"] == [(1, 1)]  # strat
        assert by_agent["data"] == [(1, 1)]  # data

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
        assert manifest_envelopes[0].task_id == ("task-run_abcdef12-m000-development.develop")
        assert manifest_envelopes[1].task_id == ("task-run_abcdef12-m001-development.develop")
        assert manifest_envelopes[3].task_id == ("task-run_abcdef12-m003-qa.test")

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
                AgentProfileEntry(agent_id="max", role="lead", model="test", enabled=True),
                AgentProfileEntry(agent_id="neo", role="dev", model="test", enabled=True),
                AgentProfileEntry(agent_id="nat", role="strat", model="test", enabled=True),
                AgentProfileEntry(agent_id="data", role="data", model="test", enabled=True),
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


class TestCriteriaScopeDispatchNet:
    """#464 final net: generate_task_plan rejects a source-regex plan for
    EVERY run shape — gate-time checks only ever add earlier rejections."""

    def test_source_regex_plan_fails_at_dispatch(self):
        from squadops.cycles.models import CycleError

        manifest = ImplementationPlan.from_yaml(
            MANIFEST_YAML.replace(
                'acceptance_criteria: ["Models exist"]',
                "acceptance_criteria: [{check: regex_match, "
                "file: backend/models.py, pattern: 'class \\w+', count_min: 1}]",
            )
        )
        with pytest.raises(CycleError) as exc_info:
            generate_task_plan(_make_cycle(), _make_run(), _make_profile(), plan=manifest)
        assert "criteria scope" in str(exc_info.value)
        assert "backend/models.py" in str(exc_info.value)


# ---------------------------------------------------------------------------
# Workload-invariant tail preservation (#439)
# ---------------------------------------------------------------------------

DEV_ONLY_MANIFEST_YAML = """\
version: 1
project_id: group_run
cycle_id: cyc_test
prd_hash: abc123
tasks:
  - task_index: 0
    task_type: development.develop
    role: dev
    focus: "Backend routes"
    description: "Fill route stubs"
    expected_artifacts: ["backend/routes.py"]
    depends_on: []
  - task_index: 1
    task_type: development.develop
    role: dev
    focus: "Frontend views"
    description: "Fill view stubs"
    expected_artifacts: ["frontend/src/views/RunsListView.jsx"]
    depends_on: []
summary:
  total_dev_tasks: 2
  total_qa_tasks: 0
  total_tasks: 2
  estimated_layers: [backend, frontend]
"""

BUILDER_MANIFEST_YAML = """\
version: 1
project_id: group_run
cycle_id: cyc_test
prd_hash: abc123
tasks:
  - task_index: 0
    task_type: development.develop
    role: dev
    focus: "Backend routes"
    description: "Fill route stubs"
    expected_artifacts: ["backend/routes.py"]
    depends_on: []
  - task_index: 1
    task_type: builder.assemble
    role: builder
    focus: "Package deliverable"
    description: "Assemble qa_handoff.md"
    expected_artifacts: ["qa_handoff.md"]
    depends_on: [0]
summary:
  total_dev_tasks: 1
  total_builder_tasks: 1
  total_qa_tasks: 0
  total_tasks: 2
  estimated_layers: [backend]
"""


QA_BEFORE_ASSEMBLE_MANIFEST_YAML = """\
version: 1
project_id: group_run
cycle_id: cyc_test
prd_hash: abc123
tasks:
  - task_index: 0
    task_type: development.develop
    role: dev
    focus: "Backend routes"
    description: "Fill route stubs"
    expected_artifacts: ["backend/routes.py"]
    depends_on: []
  - task_index: 1
    task_type: qa.test
    role: qa
    focus: "Backend API Tests"
    description: "Write tests"
    expected_artifacts: ["tests/test_api.py"]
    depends_on: [0]
  - task_index: 2
    task_type: builder.assemble
    role: builder
    focus: "QA Handoff and Assembly"
    description: "Assemble qa_handoff.md"
    expected_artifacts: ["qa_handoff.md"]
    depends_on: [1]
summary:
  total_dev_tasks: 1
  total_builder_tasks: 1
  total_qa_tasks: 1
  total_tasks: 3
  estimated_layers: [backend, test]
"""


def _make_builder_profile() -> SquadProfile:
    profile = _make_profile()
    return SquadProfile(
        profile_id="full",
        name="Full Squad",
        description="Test profile",
        version=1,
        agents=[
            *profile.agents,
            AgentProfileEntry(agent_id="bob", role="builder", model="test", enabled=True),
        ],
        created_at=NOW,
    )


class TestWorkloadInvariantTail:
    """#439: a dev-only manifest must not descope assembly/verification.

    Attempt 3 of the Phase-0.5 spike (cyc_62c30fcc91a3) authored a 4-dev-task
    manifest; substitution dropped builder.assemble AND qa.test, the run
    completed with no build subject, and every required check reported
    subject_missing (blocked_unverified) — while the deliverable was in fact
    functional. The tail is workload-owned, not plan-optional.
    """

    def test_implementation_workload_dev_only_plan_keeps_tail(self):
        """The attempt-3 reproduction: implementation workload + builder squad."""
        manifest = ImplementationPlan.from_yaml(DEV_ONLY_MANIFEST_YAML)
        run = _make_run(workload_type="implementation")
        cycle = _make_cycle(
            applied_defaults={
                "plan_tasks": True,
                "build_tasks": True,
                "build_profile": "fullstack_fastapi_react",
            }
        )
        envelopes = generate_task_plan(cycle, run, _make_builder_profile(), plan=manifest)

        types = [e.task_type for e in envelopes]
        assert types == [
            "governance.define_done",
            "development.develop",
            "development.develop",
            "builder.assemble",
            "qa.test",
        ]

    def test_tail_agents_resolve_to_builder_and_qa_roles(self):
        manifest = ImplementationPlan.from_yaml(DEV_ONLY_MANIFEST_YAML)
        run = _make_run(workload_type="implementation")
        cycle = _make_cycle(
            applied_defaults={
                "plan_tasks": True,
                "build_tasks": True,
                "build_profile": "fullstack_fastapi_react",
            }
        )
        envelopes = generate_task_plan(cycle, run, _make_builder_profile(), plan=manifest)

        tail = {e.task_type: e.agent_id for e in envelopes[-2:]}
        assert tail == {"builder.assemble": "bob", "qa.test": "eve"}

    def test_plan_authored_builder_task_stands_in_no_duplicate(self):
        """A manifest that authors its own builder.assemble replaces the static
        one; only the missing qa.test is re-appended."""
        manifest = ImplementationPlan.from_yaml(BUILDER_MANIFEST_YAML)
        run = _make_run(workload_type="implementation")
        cycle = _make_cycle(
            applied_defaults={
                "plan_tasks": True,
                "build_tasks": True,
                "build_profile": "fullstack_fastapi_react",
            }
        )
        envelopes = generate_task_plan(cycle, run, _make_builder_profile(), plan=manifest)

        types = [e.task_type for e in envelopes]
        assert types.count("builder.assemble") == 1
        assert types[-1] == "qa.test"
        # The surviving builder task is the plan's (manifest -m namespace id)
        builder_env = next(e for e in envelopes if e.task_type == "builder.assemble")
        assert "-m001-" in builder_env.task_id

    def test_legacy_path_non_builder_profile_keeps_qa_test(self):
        """Legacy flags path, no builder role: dev-only plan still ends in qa.test."""
        manifest = ImplementationPlan.from_yaml(DEV_ONLY_MANIFEST_YAML)
        envelopes = generate_task_plan(_make_cycle(), _make_run(), _make_profile(), plan=manifest)

        types = [e.task_type for e in envelopes]
        assert types[-1] == "qa.test"
        assert types.count("qa.test") == 1
        assert "builder.assemble" not in types  # no builder role, no builder step

    def test_plan_with_qa_task_unchanged_from_before(self):
        """Existing behavior guard: a manifest that already carries qa.test gets
        no extra tail (the original MANIFEST_YAML shape)."""
        manifest = ImplementationPlan.from_yaml(MANIFEST_YAML)
        envelopes = generate_task_plan(_make_cycle(), _make_run(), _make_profile(), plan=manifest)

        types = [e.task_type for e in envelopes]
        assert len(envelopes) == 9
        assert types.count("qa.test") == 1

    def test_plan_authored_qa_before_assemble_is_reordered(self):
        """#458, the attempt-3.8 reproduction (art_d76f0a2bf05c): the manifest
        authored qa.test BEFORE builder.assemble, so testing preceded assembly
        and the (repaired) assembled deliverable was never tested. Ordering is
        workload-owned: plan tasks stand in, but the tail runs in canonical
        order regardless of authored position."""
        manifest = ImplementationPlan.from_yaml(QA_BEFORE_ASSEMBLE_MANIFEST_YAML)
        run = _make_run(workload_type="implementation")
        cycle = _make_cycle(
            applied_defaults={
                "plan_tasks": True,
                "build_tasks": True,
                "build_profile": "fullstack_fastapi_react",
            }
        )
        envelopes = generate_task_plan(cycle, run, _make_builder_profile(), plan=manifest)

        types = [e.task_type for e in envelopes]
        assert types == [
            "governance.define_done",
            "development.develop",
            "builder.assemble",
            "qa.test",
        ]
        # The plan's own tasks stand in (manifest -m namespace), not statics
        assert all(
            "-m00" in e.task_id for e in envelopes if e.task_type in ("builder.assemble", "qa.test")
        )

    def test_plan_qa_only_static_assemble_precedes_it(self):
        """Second-order #458 case: plan authors qa.test but NOT builder.assemble.
        The re-appended static assemble must still run BEFORE the plan's qa.test
        (pre-fix it was appended after all plan tasks, i.e. after testing)."""
        manifest = ImplementationPlan.from_yaml(MANIFEST_YAML)  # 3 dev + qa.test
        run = _make_run(workload_type="implementation")
        cycle = _make_cycle(
            applied_defaults={
                "plan_tasks": True,
                "build_tasks": True,
                "build_profile": "fullstack_fastapi_react",
            }
        )
        envelopes = generate_task_plan(cycle, run, _make_builder_profile(), plan=manifest)

        types = [e.task_type for e in envelopes]
        assert types.index("builder.assemble") < types.index("qa.test")
        assert types[-1] == "qa.test"
        # The surviving qa task is the plan's, not the static tuple's
        qa_env = next(e for e in envelopes if e.task_type == "qa.test")
        assert "-m003-" in qa_env.task_id


# ---------------------------------------------------------------------------
# SIP-0098 98.3 net-a: bind-mode plan validation raises at dispatch (backstop)
# ---------------------------------------------------------------------------


def _models_contract():
    """A one-fill-file contract covering backend/models.py (the artifact MANIFEST_YAML's
    task 0 produces) so a bind-mode plan must bind its criterion."""
    from squadops.cycles.verification_contract import VerificationContract

    return VerificationContract.from_dict(
        {
            "contract_version": 1,
            "skeleton": {
                "expander": "fullstack_fastapi_react",
                "interface_manifest_hash": "a" * 64,
            },
            "capabilities": ["python"],
            "frozen": [],
            "fill_files": {
                "backend/models.py": {
                    "interface": [
                        {
                            "check": "import_present",
                            "id": "vc-models-base",
                            "module": "pydantic",
                            "symbol": "BaseModel",
                        }
                    ],
                    "implementation": [],
                }
            },
            "behavioral": {
                "build": [],
                "suite": {"checks": [], "coverage_expectations": []},
                "probes": [],
            },
        }
    )


_BIND_MANIFEST_YAML = MANIFEST_YAML.replace(
    '    expected_artifacts: ["backend/models.py"]\n    acceptance_criteria: ["Models exist"]',
    '    expected_artifacts: ["backend/models.py"]\n    criteria_refs: ["vc-models-base"]',
)


class TestGenerateTaskPlanBindMode:
    def test_bound_plan_passes_net_a(self):
        from squadops.cycles.models import CycleError  # noqa: F401 — imported for symmetry

        plan = ImplementationPlan.from_yaml(_BIND_MANIFEST_YAML)
        envelopes = generate_task_plan(
            _make_cycle(), _make_run(), _make_profile(), plan=plan, contract=_models_contract()
        )
        # a correctly-bound plan is unaffected — same 9 envelopes as author mode
        assert len(envelopes) == 9

    def test_unbound_plan_raises_cycle_error(self):
        from squadops.cycles.models import CycleError

        # task 0 produces the covered file but binds nothing -> silent descoping
        plan = ImplementationPlan.from_yaml(MANIFEST_YAML)
        with pytest.raises(CycleError, match="contract binding"):
            generate_task_plan(
                _make_cycle(), _make_run(), _make_profile(), plan=plan, contract=_models_contract()
            )

    def test_author_mode_ignores_binding(self):
        # no contract passed -> author mode -> the unbound plan is fine (byte-identical)
        plan = ImplementationPlan.from_yaml(MANIFEST_YAML)
        envelopes = generate_task_plan(_make_cycle(), _make_run(), _make_profile(), plan=plan)
        assert len(envelopes) == 9

    def test_dispatch_resolves_refs_into_acceptance_criteria(self):
        # 98.3 slice C: the bound ref materializes into the dispatched envelope's
        # acceptance_criteria as a TypedCheck stamped with the contract id + file.
        from squadops.cycles.implementation_plan import TypedCheck

        plan = ImplementationPlan.from_yaml(_BIND_MANIFEST_YAML)
        envelopes = generate_task_plan(
            _make_cycle(), _make_run(), _make_profile(), plan=plan, contract=_models_contract()
        )
        models_env = next(e for e in envelopes if e.inputs.get("subtask_focus") == "Backend models")
        typed = [c for c in models_env.inputs["acceptance_criteria"] if isinstance(c, TypedCheck)]
        assert [c.id for c in typed] == ["vc-models-base"]
        assert typed[0].check == "import_present"
        assert typed[0].params["file"] == "backend/models.py"

    def test_dispatch_author_mode_leaves_criteria_untouched(self):
        # no contract -> the envelope carries only the plan's authored criteria (a prose
        # string here), never a resolved TypedCheck.
        from squadops.cycles.implementation_plan import TypedCheck

        plan = ImplementationPlan.from_yaml(MANIFEST_YAML)
        envelopes = generate_task_plan(_make_cycle(), _make_run(), _make_profile(), plan=plan)
        models_env = next(e for e in envelopes if e.inputs.get("subtask_focus") == "Backend models")
        assert models_env.inputs["acceptance_criteria"] == ["Models exist"]
        assert not any(isinstance(c, TypedCheck) for c in models_env.inputs["acceptance_criteria"])
