"""Tests for planning workload cycle request profile (SIP-0078 §5.13).

Validates that planning.yaml loads, passes schema validation, contains
the expected workload_sequence, pulse check suites, cadence policy,
and gate configuration.
"""

import pytest

from squadops.contracts.cycle_request_profiles import list_profiles, load_profile
from squadops.contracts.cycle_request_profiles.schema import CycleRequestProfile
from squadops.cycles.pulse_models import parse_pulse_checks

pytestmark = [pytest.mark.domain_contracts]


class TestPlanningProfileLoads:
    def test_load_profile_succeeds(self):
        profile = load_profile("framing")
        assert isinstance(profile, CycleRequestProfile)
        assert profile.name == "framing"

    def test_has_description(self):
        profile = load_profile("framing")
        assert "framing" in profile.description.lower()

    def test_appears_in_listing(self):
        names = list_profiles()
        assert "framing" in names


class TestPlanningProfileGate:
    def test_has_progress_plan_review_gate(self):
        profile = load_profile("framing")
        gates = profile.defaults["task_flow_policy"]["gates"]
        assert len(gates) == 1
        assert gates[0]["name"] == "progress_plan_review"

    def test_gate_fires_after_assess_readiness(self):
        profile = load_profile("framing")
        gate = profile.defaults["task_flow_policy"]["gates"][0]
        assert "governance.review_plan" in gate["after_task_types"]


class TestPlanningProfileWorkloadSequence:
    def test_has_workload_sequence(self):
        profile = load_profile("framing")
        seq = profile.defaults["workload_sequence"]
        assert len(seq) == 2

    def test_planning_then_implementation(self):
        profile = load_profile("framing")
        seq = profile.defaults["workload_sequence"]
        assert seq[0]["type"] == "framing"
        assert seq[1]["type"] == "implementation"

    def test_planning_gate_matches(self):
        profile = load_profile("framing")
        seq = profile.defaults["workload_sequence"]
        assert seq[0]["gate"] == "progress_plan_review"
        assert seq[1]["gate"] is None


class TestPlanningProfilePulseChecks:
    def test_has_two_pulse_suites(self):
        profile = load_profile("framing")
        defs = parse_pulse_checks(profile.defaults["pulse_checks"])
        assert len(defs) == 2

    def test_suite_ids(self):
        profile = load_profile("framing")
        defs = parse_pulse_checks(profile.defaults["pulse_checks"])
        suite_ids = {d.suite_id for d in defs}
        assert suite_ids == {"planning_scope_guard", "planning_completeness"}

    def test_scope_guard_is_milestone(self):
        profile = load_profile("framing")
        defs = parse_pulse_checks(profile.defaults["pulse_checks"])
        scope_guard = [d for d in defs if d.suite_id == "planning_scope_guard"][0]
        assert scope_guard.binding_mode == "milestone"
        assert "strategy" in scope_guard.after_task_types

    def test_completeness_is_milestone(self):
        profile = load_profile("framing")
        defs = parse_pulse_checks(profile.defaults["pulse_checks"])
        completeness = [d for d in defs if d.suite_id == "planning_completeness"][0]
        assert completeness.binding_mode == "milestone"
        assert "governance" in completeness.after_task_types

    def test_scope_guard_checks_objective_frame(self):
        profile = load_profile("framing")
        defs = parse_pulse_checks(profile.defaults["pulse_checks"])
        scope_guard = [d for d in defs if d.suite_id == "planning_scope_guard"][0]
        targets = [c.target for c in scope_guard.checks]
        assert any("objective_frame.md" in t for t in targets)

    def test_completeness_checks_planning_artifact(self):
        profile = load_profile("framing")
        defs = parse_pulse_checks(profile.defaults["pulse_checks"])
        completeness = [d for d in defs if d.suite_id == "planning_completeness"][0]
        targets = [c.target for c in completeness.checks]
        assert any("planning_artifact.md" in t for t in targets)


class TestPlanningProfileCadencePolicy:
    def test_has_cadence_policy(self):
        profile = load_profile("framing")
        assert "cadence_policy" in profile.defaults

    def test_max_pulse_seconds(self):
        profile = load_profile("framing")
        policy = profile.defaults["cadence_policy"]
        assert policy["max_pulse_seconds"] == 5400

    def test_max_tasks_per_pulse(self):
        profile = load_profile("framing")
        policy = profile.defaults["cadence_policy"]
        assert policy["max_tasks_per_pulse"] == 5
