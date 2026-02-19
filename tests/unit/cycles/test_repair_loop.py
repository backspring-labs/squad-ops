"""Tests for repair task builder and repair loop logic (SIP-0070 Phase 3).

Covers:
- REPAIR_TASK_STEPS: correct step order and roles
- build_repair_task_envelopes(): envelope structure, shared IDs, chaining
"""

from __future__ import annotations

import pytest

from squadops.cycles.pulse_verification import (
    REPAIR_TASK_STEPS,
    build_repair_task_envelopes,
)

pytestmark = [pytest.mark.domain_pulse_checks]


# ---------------------------------------------------------------------------
# REPAIR_TASK_STEPS constant
# ---------------------------------------------------------------------------


class TestRepairTaskSteps:
    def test_exactly_four_steps(self):
        assert len(REPAIR_TASK_STEPS) == 4

    def test_step_order(self):
        expected = [
            ("data.analyze_verification", "data"),
            ("governance.root_cause_analysis", "lead"),
            ("strategy.corrective_plan", "strat"),
            ("development.repair", "dev"),
        ]
        assert REPAIR_TASK_STEPS == expected

    def test_all_steps_are_tuples_of_str(self):
        for step in REPAIR_TASK_STEPS:
            assert isinstance(step, tuple)
            assert len(step) == 2
            assert isinstance(step[0], str)
            assert isinstance(step[1], str)


# ---------------------------------------------------------------------------
# build_repair_task_envelopes
# ---------------------------------------------------------------------------


class TestBuildRepairTaskEnvelopes:
    def _build(self, **overrides):
        defaults = {
            "cycle_id": "cyc_001",
            "project_id": "proj_001",
            "pulse_id": "pulse_1",
            "correlation_id": "corr_1",
            "trace_id": "trace_1",
            "causation_id": "task_last",
            "run_id": "run_001",
            "repair_attempt": 1,
        }
        defaults.update(overrides)
        return build_repair_task_envelopes(**defaults)

    def test_returns_four_envelopes(self):
        envelopes = self._build()
        assert len(envelopes) == 4

    def test_task_types_match_steps(self):
        envelopes = self._build()
        task_types = [e.task_type for e in envelopes]
        assert task_types == [s[0] for s in REPAIR_TASK_STEPS]

    def test_roles_match_steps(self):
        envelopes = self._build()
        roles = [e.metadata["role"] for e in envelopes]
        assert roles == [s[1] for s in REPAIR_TASK_STEPS]

    def test_shared_trace_and_correlation(self):
        envelopes = self._build(trace_id="t_shared", correlation_id="c_shared")
        for env in envelopes:
            assert env.trace_id == "t_shared"
            assert env.correlation_id == "c_shared"

    def test_shared_cycle_and_project(self):
        envelopes = self._build(cycle_id="cyc_x", project_id="proj_x")
        for env in envelopes:
            assert env.cycle_id == "cyc_x"
            assert env.project_id == "proj_x"

    def test_shared_pulse_id(self):
        envelopes = self._build(pulse_id="pulse_shared")
        for env in envelopes:
            assert env.pulse_id == "pulse_shared"

    def test_causation_id_chaining(self):
        """First task gets causation from caller; subsequent chain from previous."""
        envelopes = self._build(causation_id="parent_task")
        assert envelopes[0].causation_id == "parent_task"
        for i in range(1, len(envelopes)):
            assert envelopes[i].causation_id == envelopes[i - 1].task_id

    def test_unique_task_ids(self):
        envelopes = self._build()
        task_ids = [e.task_id for e in envelopes]
        assert len(set(task_ids)) == 4

    def test_unique_span_ids(self):
        envelopes = self._build()
        span_ids = [e.span_id for e in envelopes]
        assert len(set(span_ids)) == 4

    def test_repair_attempt_in_metadata(self):
        envelopes = self._build(repair_attempt=2)
        for env in envelopes:
            assert env.metadata["repair_attempt"] == 2
            assert env.metadata["repair_chain"] is True

    def test_step_index_in_metadata(self):
        envelopes = self._build()
        for i, env in enumerate(envelopes):
            assert env.metadata["step_index"] == i

    def test_agent_resolver_uses_role_as_default(self):
        envelopes = self._build()
        assert envelopes[0].agent_id == "data"
        assert envelopes[1].agent_id == "lead"
        assert envelopes[2].agent_id == "strat"
        assert envelopes[3].agent_id == "dev"

    def test_agent_resolver_overrides(self):
        resolver = {"data": "data-agent", "lead": "max", "strat": "nat", "dev": "neo"}
        envelopes = self._build(agent_resolver=resolver)
        assert envelopes[0].agent_id == "data-agent"
        assert envelopes[1].agent_id == "max"
        assert envelopes[2].agent_id == "nat"
        assert envelopes[3].agent_id == "neo"

    def test_empty_inputs(self):
        """Repair envelopes start with empty inputs (executor enriches later)."""
        envelopes = self._build()
        for env in envelopes:
            assert env.inputs == {}

    def test_deterministic_per_invocation(self):
        """Each invocation produces different task_ids."""
        envelopes_a = self._build()
        envelopes_b = self._build()
        ids_a = {e.task_id for e in envelopes_a}
        ids_b = {e.task_id for e in envelopes_b}
        assert ids_a.isdisjoint(ids_b)

    def test_boundary_id_in_metadata(self):
        """boundary_id propagated to all envelope metadata (D10)."""
        envelopes = self._build(boundary_id="post_dev")
        for env in envelopes:
            assert env.metadata["boundary_id"] == "post_dev"

    def test_cadence_interval_id_in_metadata(self):
        """cadence_interval_id propagated to all envelope metadata (D10)."""
        envelopes = self._build(cadence_interval_id=3)
        for env in envelopes:
            assert env.metadata["cadence_interval_id"] == 3

    def test_failed_suite_ids_in_metadata(self):
        """failed_suite_ids propagated to all envelope metadata (D10)."""
        envelopes = self._build(failed_suite_ids=("s1", "s2"))
        for env in envelopes:
            assert env.metadata["failed_suite_ids"] == ["s1", "s2"]

    def test_boundary_context_defaults(self):
        """boundary_id, cadence_interval_id, failed_suite_ids default to empty."""
        envelopes = self._build()
        for env in envelopes:
            assert env.metadata["boundary_id"] == ""
            assert env.metadata["cadence_interval_id"] == 0
            assert env.metadata["failed_suite_ids"] == []
