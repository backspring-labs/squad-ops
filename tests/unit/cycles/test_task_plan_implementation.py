"""Tests for implementation workload task plan (SIP-0079).

Covers IMPLEMENTATION_TASK_STEPS, CORRECTION_TASK_STEPS, REPAIR_TASK_STEPS,
deterministic task IDs (RC-1), and backward compat for non-implementation runs.
"""

from datetime import UTC, datetime

import pytest

from squadops.cycles.models import (
    AgentProfileEntry,
    Cycle,
    Run,
    SquadProfile,
    TaskFlowPolicy,
    WorkloadType,
)
from squadops.cycles.task_plan import (
    CORRECTION_TASK_STEPS,
    IMPLEMENTATION_TASK_STEPS,
    REPAIR_TASK_STEPS,
    generate_task_plan,
    repair_steps_for,
)

pytestmark = [pytest.mark.domain_orchestration]

NOW = datetime(2026, 3, 1, 12, 0, 0, tzinfo=UTC)


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
            AgentProfileEntry(agent_id="data-agent", role="data", model="gpt-4", enabled=True),
            AgentProfileEntry(agent_id="max", role="lead", model="gpt-4", enabled=True),
        ),
        created_at=NOW,
    )


@pytest.fixture
def impl_cycle():
    return Cycle(
        cycle_id="cyc_impl",
        project_id="proj_001",
        created_at=NOW,
        created_by="system",
        prd_ref="prd_ref",
        squad_profile_id="full-squad",
        squad_profile_snapshot_ref="sha256:abc",
        task_flow_policy=TaskFlowPolicy(mode="sequential"),
        build_strategy="fresh",
        applied_defaults={},
        execution_overrides={},
    )


@pytest.fixture
def impl_run():
    return Run(
        run_id="run_impl_001",
        cycle_id="cyc_impl",
        run_number=1,
        status="queued",
        initiated_by="api",
        resolved_config_hash="hash",
        workload_type=WorkloadType.IMPLEMENTATION,
    )


@pytest.fixture
def legacy_run():
    return Run(
        run_id="run_legacy_001",
        cycle_id="cyc_impl",
        run_number=1,
        status="queued",
        initiated_by="api",
        resolved_config_hash="hash",
    )


class TestImplementationTaskSteps:
    def test_constants_defined(self):
        assert len(IMPLEMENTATION_TASK_STEPS) == 3
        assert IMPLEMENTATION_TASK_STEPS[0] == ("governance.establish_contract", "lead")
        assert IMPLEMENTATION_TASK_STEPS[1] == ("development.develop", "dev")
        assert IMPLEMENTATION_TASK_STEPS[2] == ("qa.test", "qa")

    def test_prepends_contract_before_build(self, impl_cycle, impl_run, profile):
        plan = generate_task_plan(impl_cycle, impl_run, profile)
        task_types = [e.task_type for e in plan]
        assert task_types[0] == "governance.establish_contract"
        assert "development.develop" in task_types
        assert "qa.test" in task_types

    def test_implementation_plan_length(self, impl_cycle, impl_run, profile):
        plan = generate_task_plan(impl_cycle, impl_run, profile)
        assert len(plan) == 3


class TestCorrectionAndRepairSteps:
    def test_correction_steps_defined(self):
        assert CORRECTION_TASK_STEPS == [
            ("data.analyze_failure", "data"),
            ("governance.correction_decision", "lead"),
        ]

    def test_repair_steps_defined(self):
        # Issue #100: development.correction_repair, NOT development.repair
        # (the latter belongs to the pulse-check chain in pulse_verification.py).
        assert REPAIR_TASK_STEPS == [
            ("development.correction_repair", "dev"),
            ("qa.validate_repair", "qa"),
        ]


class TestRepairStepsFor:
    def test_dev_develop_uses_dev_repair_pair(self):
        assert repair_steps_for("development.develop") == [
            ("development.correction_repair", "dev"),
            ("qa.validate_repair", "qa"),
        ]

    def test_builder_assemble_routes_to_builder_repair_handler(self):
        # Regression: previously a failed builder.assemble silently routed
        # to development.correction_repair (Neo) because the executor
        # always looped REPAIR_TASK_STEPS.
        steps = repair_steps_for("builder.assemble")
        assert steps[0] == ("builder.assemble_repair", "builder")
        assert steps[-1] == ("qa.validate_repair", "qa")

    def test_unknown_failed_task_type_falls_back_to_dev_pair(self):
        assert repair_steps_for("strategy.frame_objective") == REPAIR_TASK_STEPS
        assert repair_steps_for("") == REPAIR_TASK_STEPS


class TestDeterministicTaskIds:
    def test_implementation_uses_deterministic_ids(self, impl_cycle, impl_run, profile):
        plan = generate_task_plan(impl_cycle, impl_run, profile)
        for i, envelope in enumerate(plan):
            expected_prefix = f"task-{impl_run.run_id[:12]}-{i:03d}-"
            assert envelope.task_id.startswith(expected_prefix), (
                f"Expected task_id to start with {expected_prefix!r}, got {envelope.task_id!r}"
            )

    def test_deterministic_ids_stable_across_calls(self, impl_cycle, impl_run, profile):
        """RC-1: Same inputs produce same task IDs."""
        plan_a = generate_task_plan(impl_cycle, impl_run, profile)
        plan_b = generate_task_plan(impl_cycle, impl_run, profile)
        ids_a = [e.task_id for e in plan_a]
        ids_b = [e.task_id for e in plan_b]
        assert ids_a == ids_b

    def test_non_implementation_uses_uuid_ids(self, impl_cycle, legacy_run, profile):
        """Non-implementation runs still use UUID-based task IDs (backward compat)."""
        plan = generate_task_plan(impl_cycle, legacy_run, profile)
        for envelope in plan:
            # UUID hex is 32 chars, no hyphens
            assert not envelope.task_id.startswith("task-")

    def test_deterministic_ids_include_task_type(self, impl_cycle, impl_run, profile):
        plan = generate_task_plan(impl_cycle, impl_run, profile)
        assert plan[0].task_id.endswith("governance.establish_contract")
        assert plan[1].task_id.endswith("development.develop")
        assert plan[2].task_id.endswith("qa.test")
