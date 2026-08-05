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
        profile_id="full",
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
        squad_profile_id="full",
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
        assert IMPLEMENTATION_TASK_STEPS[0] == ("governance.define_done", "lead")
        assert IMPLEMENTATION_TASK_STEPS[1] == ("development.develop", "dev")
        assert IMPLEMENTATION_TASK_STEPS[2] == ("qa.test", "qa")

    def test_prepends_contract_before_build(self, impl_cycle, impl_run, profile):
        plan = generate_task_plan(impl_cycle, impl_run, profile)
        task_types = [e.task_type for e in plan]
        assert task_types[0] == "governance.define_done"
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
        # Issue #556: no qa.validate_repair step — repair acceptance is
        # deterministic (patch verification #389 + retest #456).
        assert REPAIR_TASK_STEPS == [
            ("development.correction_repair", "dev"),
        ]


class TestRepairStepsFor:
    def test_dev_develop_uses_dev_repair_steps(self):
        assert repair_steps_for("development.develop") == [
            ("development.correction_repair", "dev"),
        ]

    def test_builder_assemble_routes_to_builder_repair_handler(self):
        # Regression: previously a failed builder.assemble silently routed
        # to development.correction_repair (dev role) because the executor
        # always looped REPAIR_TASK_STEPS.
        assert repair_steps_for("builder.assemble") == [
            ("builder.assemble_repair", "builder"),
        ]

    def test_no_repair_sequence_contains_validate_repair(self):
        # Issue #556 regression: an LLM validate step must not sneak back
        # into any repair sequence — acceptance is deterministic-only.
        for failed_task_type in ("development.develop", "builder.assemble", "unknown", ""):
            assert all(
                task_type != "qa.validate_repair"
                for task_type, _ in repair_steps_for(failed_task_type)
            )

    def test_unknown_failed_task_type_falls_back_to_dev_steps(self):
        assert repair_steps_for("strategy.frame_objective") == REPAIR_TASK_STEPS
        assert repair_steps_for("") == REPAIR_TASK_STEPS


class TestRepairStepsForFailureLocus:
    """#568: the own-artifact locus routes qa.test repairs to the qa role;
    every other locus keeps the default dev chain — a behavioral failure
    routed to qa re-authoring would be the test-gaming false green."""

    def test_qa_test_own_artifact_routes_to_qa_repair(self):
        from squadops.cycles.failure_evidence import FailureLocus

        assert repair_steps_for("qa.test", FailureLocus.OWN_ARTIFACT) == [
            ("qa.test_repair", "qa"),
        ]

    def test_qa_test_subject_and_unknown_stay_on_dev_chain(self):
        from squadops.cycles.failure_evidence import FailureLocus

        assert repair_steps_for("qa.test", FailureLocus.SUBJECT) == REPAIR_TASK_STEPS
        assert repair_steps_for("qa.test", FailureLocus.UNKNOWN) == REPAIR_TASK_STEPS
        assert repair_steps_for("qa.test", None) == REPAIR_TASK_STEPS
        assert repair_steps_for("qa.test") == REPAIR_TASK_STEPS

    def test_own_artifact_without_specialized_entry_uses_default(self):
        from squadops.cycles.failure_evidence import FailureLocus

        assert repair_steps_for("development.develop", FailureLocus.OWN_ARTIFACT) == (
            REPAIR_TASK_STEPS
        )

    def test_qa_test_repair_joins_repair_task_types(self):
        # Fix E composition: the candidate type derives from the table, so the
        # provenance filter and #389 re-typing cover it with zero bookkeeping.
        from squadops.cycles.task_plan import REPAIR_TASK_TYPES

        assert "qa.test_repair" in REPAIR_TASK_TYPES


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
        assert plan[0].task_id.endswith("governance.define_done")
        assert plan[1].task_id.endswith("development.develop")
        assert plan[2].task_id.endswith("qa.test")


class TestPlanRequiredNoStaticFallback:
    """#424: an implementation_plan/typed_acceptance cycle whose plan is absent
    must refuse dispatch — the static-step fallback ran the whole cycle with
    the profile's instrumentation contract silently missing (cyc_7d2f505e5e8f:
    caught only by the required-check throttle after the full run was spent)."""

    @staticmethod
    def _gated_cycle(impl_cycle, **defaults):
        import dataclasses

        return dataclasses.replace(impl_cycle, applied_defaults=dict(defaults))

    def test_absent_plan_raises_for_implementation_plan_cycle(self, impl_cycle, impl_run, profile):
        from squadops.cycles.models import CycleError

        cycle = self._gated_cycle(impl_cycle, implementation_plan=True, build_tasks=True)
        with pytest.raises(CycleError) as exc_info:
            generate_task_plan(cycle, impl_run, profile, plan=None)
        assert "implementation plan required but absent" in str(exc_info.value)

    def test_absent_plan_raises_for_typed_acceptance_cycle(self, impl_cycle, impl_run, profile):
        from squadops.cycles.models import CycleError

        cycle = self._gated_cycle(impl_cycle, typed_acceptance=True, build_tasks=True)
        with pytest.raises(CycleError):
            generate_task_plan(cycle, impl_run, profile, plan=None)

    def test_unflagged_cycle_keeps_static_fallback(self, impl_cycle, impl_run, profile):
        """Legacy/plan-less profiles (smoke, selftest) still get static steps."""
        cycle = self._gated_cycle(impl_cycle, build_tasks=True)
        envelopes = generate_task_plan(cycle, impl_run, profile, plan=None)
        assert envelopes  # static build steps materialized, no raise

    def test_framing_workload_unaffected(self, impl_cycle, profile):
        """Framing has no build steps — the guard must not fire there."""
        from squadops.cycles.models import Run, WorkloadType

        cycle = self._gated_cycle(impl_cycle, implementation_plan=True)
        framing_run = Run(
            run_id="run_framing",
            cycle_id="cyc_impl",
            run_number=1,
            status="queued",
            initiated_by="api",
            resolved_config_hash="hash",
            workload_type=WorkloadType.FRAMING,
        )
        envelopes = generate_task_plan(cycle, framing_run, profile, plan=None)
        assert envelopes
