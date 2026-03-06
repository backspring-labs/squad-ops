"""Tests for wrap-up workload branching in task plan generator (SIP-0080).

Validates that generate_task_plan selects WRAPUP_TASK_STEPS when
run.workload_type is "wrapup", validates REQUIRED_WRAPUP_ROLES,
and does not regress existing behavior.
"""

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
    WRAPUP_TASK_STEPS,
    generate_task_plan,
)

pytestmark = [pytest.mark.domain_orchestration]

NOW = datetime(2026, 3, 6, 12, 0, 0, tzinfo=UTC)


# ---- Fixtures ----


@pytest.fixture
def wrapup_profile():
    """Profile with data, qa, and lead roles (minimum for wrap-up)."""
    return SquadProfile(
        profile_id="wrapup-squad",
        name="Wrap-Up Squad",
        description="Data + QA + Lead",
        version=1,
        agents=(
            AgentProfileEntry(agent_id="data-agent", role="data", model="gpt-4", enabled=True),
            AgentProfileEntry(agent_id="eve", role="qa", model="gpt-4", enabled=True),
            AgentProfileEntry(agent_id="max", role="lead", model="gpt-4", enabled=True),
        ),
        created_at=NOW,
    )


@pytest.fixture
def full_profile():
    """Full 5-agent squad profile (superset of wrapup roles)."""
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
def cycle():
    return Cycle(
        cycle_id="cyc_wrapup",
        project_id="hello_squad",
        created_at=NOW,
        created_by="system",
        prd_ref="prd_ref_123",
        squad_profile_id="wrapup-squad",
        squad_profile_snapshot_ref="sha256:abc",
        task_flow_policy=TaskFlowPolicy(mode="sequential"),
        build_strategy="fresh",
        applied_defaults={"build_strategy": "fresh"},
        execution_overrides={"impl_run_id": "run_impl_001"},
    )


def _run(workload_type=None):
    return Run(
        run_id="run_wrapup_001",
        cycle_id="cyc_wrapup",
        run_number=1,
        status="queued",
        initiated_by="api",
        resolved_config_hash="config_hash_abc",
        workload_type=workload_type,
    )


# ---- Wrap-up workload tests ----


class TestWrapupWorkload:
    def test_produces_5_wrapup_envelopes(self, cycle, wrapup_profile):
        envelopes = generate_task_plan(cycle, _run("wrapup"), wrapup_profile)
        assert len(envelopes) == 5

    def test_task_types_match_wrapup_steps(self, cycle, wrapup_profile):
        envelopes = generate_task_plan(cycle, _run("wrapup"), wrapup_profile)
        actual = [e.task_type for e in envelopes]
        expected = [s[0] for s in WRAPUP_TASK_STEPS]
        assert actual == expected

    def test_roles_match_wrapup_steps(self, cycle, wrapup_profile):
        envelopes = generate_task_plan(cycle, _run("wrapup"), wrapup_profile)
        actual = [e.metadata["role"] for e in envelopes]
        expected = [s[1] for s in WRAPUP_TASK_STEPS]
        assert actual == expected

    def test_shared_correlation_and_trace_ids(self, cycle, wrapup_profile):
        envelopes = generate_task_plan(cycle, _run("wrapup"), wrapup_profile)
        correlation_ids = {e.correlation_id for e in envelopes}
        trace_ids = {e.trace_id for e in envelopes}
        assert len(correlation_ids) == 1
        assert len(trace_ids) == 1

    def test_causation_chain(self, cycle, wrapup_profile):
        envelopes = generate_task_plan(cycle, _run("wrapup"), wrapup_profile)
        # First envelope's causation_id is the correlation_id
        assert envelopes[0].causation_id == envelopes[0].correlation_id
        # Subsequent envelopes chain to the previous task_id
        for i in range(1, len(envelopes)):
            assert envelopes[i].causation_id == envelopes[i - 1].task_id

    def test_works_with_full_profile(self, cycle, full_profile):
        """Wrap-up works when extra roles (strat, dev) are present."""
        envelopes = generate_task_plan(cycle, _run("wrapup"), full_profile)
        assert len(envelopes) == 5


# ---- Role validation tests ----


class TestWrapupRoleValidation:
    def test_missing_data_role_raises(self, cycle):
        profile = SquadProfile(
            profile_id="no-data",
            name="No Data",
            description="Missing data",
            version=1,
            agents=(
                AgentProfileEntry(agent_id="eve", role="qa", model="gpt-4", enabled=True),
                AgentProfileEntry(agent_id="max", role="lead", model="gpt-4", enabled=True),
            ),
            created_at=NOW,
        )
        with pytest.raises(CycleError, match="data"):
            generate_task_plan(cycle, _run("wrapup"), profile)

    def test_missing_qa_role_raises(self, cycle):
        profile = SquadProfile(
            profile_id="no-qa",
            name="No QA",
            description="Missing qa",
            version=1,
            agents=(
                AgentProfileEntry(agent_id="data-agent", role="data", model="gpt-4", enabled=True),
                AgentProfileEntry(agent_id="max", role="lead", model="gpt-4", enabled=True),
            ),
            created_at=NOW,
        )
        with pytest.raises(CycleError, match="qa"):
            generate_task_plan(cycle, _run("wrapup"), profile)

    def test_missing_lead_role_raises(self, cycle):
        profile = SquadProfile(
            profile_id="no-lead",
            name="No Lead",
            description="Missing lead",
            version=1,
            agents=(
                AgentProfileEntry(agent_id="data-agent", role="data", model="gpt-4", enabled=True),
                AgentProfileEntry(agent_id="eve", role="qa", model="gpt-4", enabled=True),
            ),
            created_at=NOW,
        )
        with pytest.raises(CycleError, match="lead"):
            generate_task_plan(cycle, _run("wrapup"), profile)


# ---- Backward compatibility ----


class TestWrapupBackwardCompat:
    def test_legacy_null_workload_type_unchanged(self, cycle, full_profile):
        """workload_type=None still uses legacy plan_tasks/build_tasks logic."""
        envelopes = generate_task_plan(cycle, _run(None), full_profile)
        # Legacy path defaults to CYCLE_TASK_STEPS (plan_tasks=True by default)
        assert len(envelopes) == 5
        assert envelopes[0].task_type == "strategy.analyze_prd"
