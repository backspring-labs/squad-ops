"""
Tests for workload-type branching in task plan generator (SIP-0078).

Validates that generate_task_plan selects the correct step sequence based on
run.workload_type, validates role requirements, and rejects unknown types.
"""

from dataclasses import replace
from datetime import UTC, datetime

import pytest

from squadops.cycles.models import (
    AgentProfileEntry,
    Cycle,
    CycleError,
    Run,
    SquadProfile,
    TaskFlowPolicy,
)
from squadops.cycles.task_plan import (
    BUILD_TASK_STEPS,
    BUILDER_ASSEMBLY_TASK_STEPS,
    CYCLE_TASK_STEPS,
    PLANNING_TASK_STEPS,
    REFINEMENT_TASK_STEPS,
    generate_task_plan,
)

pytestmark = [pytest.mark.domain_orchestration]

NOW = datetime(2026, 1, 15, 12, 0, 0, tzinfo=UTC)


# ---- Fixtures ----


@pytest.fixture
def full_profile():
    """Full 5-agent squad profile (all required plan roles)."""
    return SquadProfile(
        profile_id="full-squad",
        name="Full Squad",
        description="All agents",
        version=1,
        agents=(
            AgentProfileEntry(agent_id="nat", role="strat", model="gpt-4", enabled=True),
            AgentProfileEntry(agent_id="neo", role="dev", model="gpt-4", enabled=True),
            AgentProfileEntry(agent_id="eve", role="qa", model="gpt-4", enabled=True),
            AgentProfileEntry(agent_id="data-agent", role="data", model="gpt-4", enabled=True),
            AgentProfileEntry(agent_id="max", role="lead", model="gpt-4", enabled=True),
        ),
        created_at=NOW,
    )


@pytest.fixture
def lead_qa_profile():
    """Profile with only lead and qa roles (for refinement workloads)."""
    return SquadProfile(
        profile_id="refinement-squad",
        name="Refinement Squad",
        description="Lead + QA only",
        version=1,
        agents=(
            AgentProfileEntry(agent_id="eve", role="qa", model="gpt-4", enabled=True),
            AgentProfileEntry(agent_id="max", role="lead", model="gpt-4", enabled=True),
        ),
        created_at=NOW,
    )


@pytest.fixture
def builder_profile():
    """Full profile plus builder role."""
    return SquadProfile(
        profile_id="builder-squad",
        name="Builder Squad",
        description="Full squad + builder",
        version=1,
        agents=(
            AgentProfileEntry(agent_id="nat", role="strat", model="gpt-4", enabled=True),
            AgentProfileEntry(agent_id="neo", role="dev", model="gpt-4", enabled=True),
            AgentProfileEntry(agent_id="eve", role="qa", model="gpt-4", enabled=True),
            AgentProfileEntry(agent_id="data-agent", role="data", model="gpt-4", enabled=True),
            AgentProfileEntry(agent_id="max", role="lead", model="gpt-4", enabled=True),
            AgentProfileEntry(agent_id="bob", role="builder", model="gpt-4", enabled=True),
        ),
        created_at=NOW,
    )


@pytest.fixture
def cycle():
    return Cycle(
        cycle_id="cyc_001",
        project_id="hello_squad",
        created_at=NOW,
        created_by="system",
        prd_ref="prd_ref_123",
        squad_profile_id="full-squad",
        squad_profile_snapshot_ref="sha256:abc",
        task_flow_policy=TaskFlowPolicy(mode="sequential"),
        build_strategy="fresh",
        applied_defaults={"build_strategy": "fresh"},
        execution_overrides={"timeout": 300},
    )


def _run(workload_type=None):
    return Run(
        run_id="run_001",
        cycle_id="cyc_001",
        run_number=1,
        status="queued",
        initiated_by="api",
        resolved_config_hash="config_hash_abc",
        workload_type=workload_type,
    )


# ---- Planning workload tests ----


class TestPlanningWorkload:
    def test_produces_5_planning_envelopes(self, cycle, full_profile):
        envelopes = generate_task_plan(cycle, _run("planning"), full_profile)
        assert len(envelopes) == 5

    def test_task_types_match_planning_steps(self, cycle, full_profile):
        envelopes = generate_task_plan(cycle, _run("planning"), full_profile)
        actual = [e.task_type for e in envelopes]
        expected = [s[0] for s in PLANNING_TASK_STEPS]
        assert actual == expected

    def test_roles_match_planning_steps(self, cycle, full_profile):
        envelopes = generate_task_plan(cycle, _run("planning"), full_profile)
        actual = [e.metadata["role"] for e in envelopes]
        expected = [s[1] for s in PLANNING_TASK_STEPS]
        assert actual == expected

    def test_agent_ids_resolved_from_profile(self, cycle, full_profile):
        envelopes = generate_task_plan(cycle, _run("planning"), full_profile)
        expected = ["data-agent", "nat", "neo", "eve", "max"]
        assert [e.agent_id for e in envelopes] == expected

    def test_shared_correlation_and_trace_ids(self, cycle, full_profile):
        envelopes = generate_task_plan(cycle, _run("planning"), full_profile)
        assert len({e.correlation_id for e in envelopes}) == 1
        assert len({e.trace_id for e in envelopes}) == 1

    def test_causation_chain(self, cycle, full_profile):
        envelopes = generate_task_plan(cycle, _run("planning"), full_profile)
        assert envelopes[0].causation_id == envelopes[0].correlation_id
        for i in range(1, len(envelopes)):
            assert envelopes[i].causation_id == envelopes[i - 1].task_id

    def test_missing_role_raises_cycle_error(self, cycle, lead_qa_profile):
        with pytest.raises(CycleError, match="missing required roles"):
            generate_task_plan(cycle, _run("planning"), lead_qa_profile)


# ---- Refinement workload tests ----


class TestRefinementWorkload:
    def test_produces_2_refinement_envelopes(self, cycle, full_profile):
        envelopes = generate_task_plan(cycle, _run("refinement"), full_profile)
        assert len(envelopes) == 2

    def test_task_types_match_refinement_steps(self, cycle, full_profile):
        envelopes = generate_task_plan(cycle, _run("refinement"), full_profile)
        actual = [e.task_type for e in envelopes]
        expected = [s[0] for s in REFINEMENT_TASK_STEPS]
        assert actual == expected

    def test_lead_qa_only_profile_succeeds(self, cycle, lead_qa_profile):
        envelopes = generate_task_plan(cycle, _run("refinement"), lead_qa_profile)
        assert len(envelopes) == 2

    def test_missing_lead_raises_cycle_error(self, cycle):
        qa_only = SquadProfile(
            profile_id="qa-only",
            name="QA Only",
            description="",
            version=1,
            agents=(
                AgentProfileEntry(agent_id="eve", role="qa", model="gpt-4", enabled=True),
            ),
            created_at=NOW,
        )
        with pytest.raises(CycleError, match="missing required refinement roles.*lead"):
            generate_task_plan(cycle, _run("refinement"), qa_only)

    def test_missing_qa_raises_cycle_error(self, cycle):
        lead_only = SquadProfile(
            profile_id="lead-only",
            name="Lead Only",
            description="",
            version=1,
            agents=(
                AgentProfileEntry(agent_id="max", role="lead", model="gpt-4", enabled=True),
            ),
            created_at=NOW,
        )
        with pytest.raises(CycleError, match="missing required refinement roles.*qa"):
            generate_task_plan(cycle, _run("refinement"), lead_only)

    def test_causation_chain_2_steps(self, cycle, full_profile):
        envelopes = generate_task_plan(cycle, _run("refinement"), full_profile)
        assert envelopes[0].causation_id == envelopes[0].correlation_id
        assert envelopes[1].causation_id == envelopes[0].task_id


# ---- Implementation workload tests ----


class TestImplementationWorkload:
    def test_no_builder_produces_build_task_steps(self, cycle, full_profile):
        envelopes = generate_task_plan(cycle, _run("implementation"), full_profile)
        actual = [e.task_type for e in envelopes]
        expected = [s[0] for s in BUILD_TASK_STEPS]
        assert actual == expected

    def test_builder_present_produces_assembly_steps(self, cycle, builder_profile):
        envelopes = generate_task_plan(cycle, _run("implementation"), builder_profile)
        actual = [e.task_type for e in envelopes]
        expected = [s[0] for s in BUILDER_ASSEMBLY_TASK_STEPS]
        assert actual == expected


# ---- Evaluation workload tests ----


class TestEvaluationWorkload:
    def test_produces_cycle_task_steps(self, cycle, full_profile):
        envelopes = generate_task_plan(cycle, _run("evaluation"), full_profile)
        actual = [e.task_type for e in envelopes]
        expected = [s[0] for s in CYCLE_TASK_STEPS]
        assert actual == expected

    def test_missing_role_raises_cycle_error(self, cycle, lead_qa_profile):
        with pytest.raises(CycleError, match="missing required roles"):
            generate_task_plan(cycle, _run("evaluation"), lead_qa_profile)


# ---- Unknown workload type tests ----


class TestUnknownWorkloadType:
    def test_typo_raises_cycle_error(self, cycle, full_profile):
        with pytest.raises(CycleError, match="Unknown workload_type 'plannnig'"):
            generate_task_plan(cycle, _run("plannnig"), full_profile)

    def test_error_message_lists_known_types(self, cycle, full_profile):
        with pytest.raises(CycleError, match="Known types:"):
            generate_task_plan(cycle, _run("unknown_type"), full_profile)


# ---- Legacy backward compatibility ----


class TestLegacyBackwardCompat:
    def test_no_workload_type_uses_plan_tasks_flag(self, cycle, full_profile):
        """workload_type=None → legacy path, plan_tasks=True → CYCLE_TASK_STEPS."""
        envelopes = generate_task_plan(cycle, _run(None), full_profile)
        actual = [e.task_type for e in envelopes]
        expected = [s[0] for s in CYCLE_TASK_STEPS]
        assert actual == expected

    def test_no_workload_type_with_build_tasks(self, cycle, full_profile):
        """workload_type=None, build_tasks=True → plan+build steps."""
        cycle_with_build = replace(
            cycle,
            applied_defaults={"plan_tasks": True, "build_tasks": True},
        )
        envelopes = generate_task_plan(cycle_with_build, _run(None), full_profile)
        assert len(envelopes) == 7  # 5 plan + 2 build

    def test_workload_type_ignores_plan_tasks_flag(self, cycle, full_profile):
        """When workload_type is set, plan_tasks/build_tasks flags are ignored."""
        cycle_with_flags = replace(
            cycle,
            applied_defaults={"plan_tasks": True, "build_tasks": True},
        )
        envelopes = generate_task_plan(cycle_with_flags, _run("planning"), full_profile)
        # Should produce 5 planning steps, NOT 5 plan + 2 build
        assert len(envelopes) == 5
        actual = [e.task_type for e in envelopes]
        expected = [s[0] for s in PLANNING_TASK_STEPS]
        assert actual == expected
