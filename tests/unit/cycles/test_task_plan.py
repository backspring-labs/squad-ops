"""
Tests for the task plan generator (SIP-0066 Phase 4).

Validates that generate_task_plan produces a deterministic 5-step task sequence
with correct lineage chaining, input payloads, and agent resolution.
"""

from datetime import datetime, timezone

import pytest

from squadops.cycles.models import (
    AgentProfileEntry,
    Cycle,
    Run,
    SquadProfile,
    TaskFlowPolicy,
)
from squadops.cycles.task_plan import CYCLE_TASK_STEPS, generate_task_plan
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


@pytest.fixture
def envelopes(cycle, run, profile):
    return generate_task_plan(cycle, run, profile)


class TestTaskPlanLength:
    def test_returns_exactly_five_envelopes(self, envelopes):
        assert len(envelopes) == 5

    def test_all_items_are_task_envelopes(self, envelopes):
        for env in envelopes:
            assert isinstance(env, TaskEnvelope)


class TestTaskTypes:
    def test_task_types_match_cycle_task_steps_order(self, envelopes):
        expected = [step[0] for step in CYCLE_TASK_STEPS]
        actual = [env.task_type for env in envelopes]
        assert actual == expected


class TestCorrelationAndTrace:
    def test_all_envelopes_share_same_correlation_id(self, envelopes):
        ids = {env.correlation_id for env in envelopes}
        assert len(ids) == 1

    def test_all_envelopes_share_same_trace_id(self, envelopes):
        ids = {env.trace_id for env in envelopes}
        assert len(ids) == 1


class TestUniqueIds:
    def test_each_envelope_has_unique_task_id(self, envelopes):
        task_ids = [env.task_id for env in envelopes]
        assert len(set(task_ids)) == 5

    def test_each_envelope_has_unique_pulse_id(self, envelopes):
        pulse_ids = [env.pulse_id for env in envelopes]
        assert len(set(pulse_ids)) == 5

    def test_each_envelope_has_unique_span_id(self, envelopes):
        span_ids = [env.span_id for env in envelopes]
        assert len(set(span_ids)) == 5


class TestCausationChaining:
    def test_step_zero_causation_id_equals_correlation_id(self, envelopes):
        assert envelopes[0].causation_id == envelopes[0].correlation_id

    def test_step_n_plus_one_causation_id_equals_step_n_task_id(self, envelopes):
        for i in range(1, len(envelopes)):
            assert envelopes[i].causation_id == envelopes[i - 1].task_id


class TestInputs:
    def test_each_envelope_inputs_has_prd_key(self, envelopes, cycle):
        for env in envelopes:
            assert env.inputs["prd"] == cycle.prd_ref

    def test_each_envelope_inputs_has_resolved_config(self, envelopes, cycle):
        expected_config = {**cycle.applied_defaults, **cycle.execution_overrides}
        for env in envelopes:
            assert env.inputs["resolved_config"] == expected_config

    def test_each_envelope_inputs_has_config_hash(self, envelopes, run):
        for env in envelopes:
            assert env.inputs["config_hash"] == run.resolved_config_hash


class TestAgentResolution:
    def test_agent_ids_resolved_from_profile(self, envelopes):
        expected_agents = ["nat", "neo", "eve", "data-agent", "max"]
        actual_agents = [env.agent_id for env in envelopes]
        assert actual_agents == expected_agents


class TestMetadata:
    def test_metadata_has_step_index(self, envelopes):
        for i, env in enumerate(envelopes):
            assert env.metadata["step_index"] == i

    def test_metadata_has_role_matching_cycle_task_steps(self, envelopes):
        expected_roles = [step[1] for step in CYCLE_TASK_STEPS]
        actual_roles = [env.metadata["role"] for env in envelopes]
        assert actual_roles == expected_roles


class TestCycleAndProjectIds:
    def test_all_envelopes_share_cycle_id_and_project_id(self, envelopes, cycle):
        for env in envelopes:
            assert env.cycle_id == cycle.cycle_id
            assert env.project_id == cycle.project_id


class TestDeterminism:
    def test_same_inputs_produce_same_task_types_in_same_order(self, cycle, run, profile):
        result_a = generate_task_plan(cycle, run, profile)
        result_b = generate_task_plan(cycle, run, profile)
        types_a = [env.task_type for env in result_a]
        types_b = [env.task_type for env in result_b]
        assert types_a == types_b
