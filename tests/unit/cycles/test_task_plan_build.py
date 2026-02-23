"""Tests for build task plan generation (SIP-Enhanced-Agent-Build-Capabilities).

Validates that generate_task_plan correctly handles build_tasks and plan_tasks
flags in applied_defaults to produce plan-only, plan+build, or build-only
task sequences.

Part of Phase 2.
"""

from datetime import datetime, timezone

import pytest

from squadops.cycles.models import (
    AgentProfileEntry,
    Cycle,
    Gate,
    Run,
    SquadProfile,
    TaskFlowPolicy,
)
from squadops.cycles.task_plan import (
    BUILD_TASK_STEPS,
    CYCLE_TASK_STEPS,
    generate_task_plan,
)
from squadops.tasks.models import TaskEnvelope

pytestmark = [pytest.mark.domain_orchestration]

NOW = datetime(2026, 1, 15, 12, 0, 0, tzinfo=timezone.utc)


@pytest.fixture
def profile():
    return SquadProfile(
        profile_id="full-squad",
        name="Full Squad",
        description="All agents",
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


class TestPlanOnlyNoBuildSteps:
    """Default behavior: no build_tasks → only 5 plan steps."""

    def test_plan_only_no_build_steps(self, run, profile):
        cycle = _make_cycle({"build_strategy": "fresh"})
        envelopes = generate_task_plan(cycle, run, profile)

        assert len(envelopes) == 5
        task_types = [e.task_type for e in envelopes]
        assert task_types == [s[0] for s in CYCLE_TASK_STEPS]

    def test_plan_only_explicit_plan_tasks_true(self, run, profile):
        cycle = _make_cycle({"plan_tasks": True})
        envelopes = generate_task_plan(cycle, run, profile)
        assert len(envelopes) == 5

    def test_plan_only_empty_build_tasks(self, run, profile):
        """Empty build_tasks list is falsy → no build steps."""
        cycle = _make_cycle({"build_tasks": []})
        envelopes = generate_task_plan(cycle, run, profile)
        assert len(envelopes) == 5


class TestPlanPlusBuild:
    """build_tasks present → 5 plan + 2 build = 7 envelopes."""

    def test_plan_plus_build_7_envelopes(self, run, profile):
        cycle = _make_cycle({
            "build_tasks": ["development.develop", "qa.test"],
        })
        envelopes = generate_task_plan(cycle, run, profile)

        assert len(envelopes) == 7
        task_types = [e.task_type for e in envelopes]
        expected = [s[0] for s in CYCLE_TASK_STEPS] + [s[0] for s in BUILD_TASK_STEPS]
        assert task_types == expected

    def test_causation_chain_continues_through_build(self, run, profile):
        cycle = _make_cycle({
            "build_tasks": ["development.develop", "qa.test"],
        })
        envelopes = generate_task_plan(cycle, run, profile)

        # Step 0: causation = correlation
        assert envelopes[0].causation_id == envelopes[0].correlation_id
        # Each subsequent step chains from previous
        for i in range(1, len(envelopes)):
            assert envelopes[i].causation_id == envelopes[i - 1].task_id

    def test_build_steps_have_correct_roles(self, run, profile):
        cycle = _make_cycle({
            "build_tasks": ["development.develop", "qa.test"],
        })
        envelopes = generate_task_plan(cycle, run, profile)

        # Last two are build steps
        assert envelopes[5].metadata["role"] == "dev"
        assert envelopes[6].metadata["role"] == "qa"

    def test_build_steps_have_correct_agent_ids(self, run, profile):
        cycle = _make_cycle({
            "build_tasks": ["development.develop", "qa.test"],
        })
        envelopes = generate_task_plan(cycle, run, profile)

        assert envelopes[5].agent_id == "neo"  # dev role
        assert envelopes[6].agent_id == "eve"  # qa role

    def test_step_indices_are_sequential(self, run, profile):
        cycle = _make_cycle({
            "build_tasks": ["development.develop", "qa.test"],
        })
        envelopes = generate_task_plan(cycle, run, profile)

        for i, env in enumerate(envelopes):
            assert env.metadata["step_index"] == i


class TestBuildOnly:
    """plan_tasks=false + build_tasks → only 2 build envelopes."""

    def test_build_only_2_envelopes(self, run, profile):
        cycle = _make_cycle({
            "plan_tasks": False,
            "build_tasks": ["development.develop", "qa.test"],
        })
        envelopes = generate_task_plan(cycle, run, profile)

        assert len(envelopes) == 2
        task_types = [e.task_type for e in envelopes]
        assert task_types == ["development.develop", "qa.test"]

    def test_build_only_causation_chain(self, run, profile):
        cycle = _make_cycle({
            "plan_tasks": False,
            "build_tasks": ["development.develop", "qa.test"],
        })
        envelopes = generate_task_plan(cycle, run, profile)

        assert envelopes[0].causation_id == envelopes[0].correlation_id
        assert envelopes[1].causation_id == envelopes[0].task_id


class TestGateBetweenPlanAndBuild:
    """Gate after governance.review fires between plan and build phases."""

    def test_gate_after_governance_review(self, run, profile):
        cycle = Cycle(
            cycle_id="cyc_001",
            project_id="test_project",
            created_at=NOW,
            created_by="system",
            prd_ref="Build a CLI tool",
            squad_profile_id="full-squad",
            squad_profile_snapshot_ref="sha256:abc",
            task_flow_policy=TaskFlowPolicy(
                mode="sequential",
                gates=(
                    Gate(
                        name="plan-review",
                        description="Review before build",
                        after_task_types=("governance.review",),
                    ),
                ),
            ),
            build_strategy="fresh",
            applied_defaults={
                "build_tasks": ["development.develop", "qa.test"],
            },
            execution_overrides={},
        )
        envelopes = generate_task_plan(cycle, run, profile)

        # governance.review is step 4 (index 4), build starts at step 5
        assert envelopes[4].task_type == "governance.review"
        assert envelopes[5].task_type == "development.develop"
        assert len(envelopes) == 7


class TestAllSharedIdsConsistent:
    def test_all_envelopes_share_correlation_and_trace(self, run, profile):
        cycle = _make_cycle({
            "build_tasks": ["development.develop", "qa.test"],
        })
        envelopes = generate_task_plan(cycle, run, profile)

        correlation_ids = {e.correlation_id for e in envelopes}
        trace_ids = {e.trace_id for e in envelopes}
        assert len(correlation_ids) == 1
        assert len(trace_ids) == 1
