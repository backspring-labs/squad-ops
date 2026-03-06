"""Tests for wrapup workload cycle request profile (SIP-0080 Phase 3).

Validates that wrapup.yaml loads, passes schema validation, contains
the expected gate, pulse check suites, cadence policy, and workload sequence.
"""

import pytest

from squadops.contracts.cycle_request_profiles import list_profiles, load_profile
from squadops.contracts.cycle_request_profiles.schema import CycleRequestProfile
from squadops.cycles.pulse_models import parse_pulse_checks

pytestmark = [pytest.mark.domain_contracts]


class TestWrapupProfileLoads:
    def test_load_profile_succeeds(self):
        profile = load_profile("wrapup")
        assert isinstance(profile, CycleRequestProfile)
        assert profile.name == "wrapup"

    def test_has_description(self):
        profile = load_profile("wrapup")
        assert "wrap-up" in profile.description.lower()

    def test_appears_in_listing(self):
        names = list_profiles()
        assert "wrapup" in names


class TestWrapupProfileGate:
    def test_has_progress_wrapup_review_gate(self):
        profile = load_profile("wrapup")
        gates = profile.defaults["task_flow_policy"]["gates"]
        assert len(gates) == 1
        assert gates[0]["name"] == "progress_wrapup_review"

    def test_gate_fires_after_publish_handoff(self):
        profile = load_profile("wrapup")
        gate = profile.defaults["task_flow_policy"]["gates"][0]
        assert "governance.publish_handoff" in gate["after_task_types"]


class TestWrapupProfileWorkloadSequence:
    def test_single_wrapup_workload(self):
        profile = load_profile("wrapup")
        seq = profile.defaults["workload_sequence"]
        assert len(seq) == 1
        assert seq[0]["type"] == "wrapup"

    def test_workload_gate_matches(self):
        profile = load_profile("wrapup")
        seq = profile.defaults["workload_sequence"]
        assert seq[0]["gate"] == "progress_wrapup_review"


class TestWrapupProfilePulseChecks:
    def test_has_three_pulse_suites(self):
        profile = load_profile("wrapup")
        defs = parse_pulse_checks(profile.defaults["pulse_checks"])
        assert len(defs) == 3

    def test_suite_ids(self):
        profile = load_profile("wrapup")
        defs = parse_pulse_checks(profile.defaults["pulse_checks"])
        suite_ids = {d.suite_id for d in defs}
        assert suite_ids == {
            "wrapup_evidence_guard",
            "wrapup_completeness",
            "wrapup_handoff_guard",
        }

    def test_all_suites_are_milestone(self):
        profile = load_profile("wrapup")
        defs = parse_pulse_checks(profile.defaults["pulse_checks"])
        for d in defs:
            assert d.binding_mode == "milestone", f"{d.suite_id} is not milestone"

    def test_evidence_guard_fires_after_gather_evidence(self):
        profile = load_profile("wrapup")
        defs = parse_pulse_checks(profile.defaults["pulse_checks"])
        guard = [d for d in defs if d.suite_id == "wrapup_evidence_guard"][0]
        assert "data.gather_evidence" in guard.after_task_types

    def test_completeness_fires_after_closeout_decision(self):
        profile = load_profile("wrapup")
        defs = parse_pulse_checks(profile.defaults["pulse_checks"])
        completeness = [d for d in defs if d.suite_id == "wrapup_completeness"][0]
        assert "governance.closeout_decision" in completeness.after_task_types

    def test_handoff_guard_fires_after_publish_handoff(self):
        profile = load_profile("wrapup")
        defs = parse_pulse_checks(profile.defaults["pulse_checks"])
        handoff = [d for d in defs if d.suite_id == "wrapup_handoff_guard"][0]
        assert "governance.publish_handoff" in handoff.after_task_types

    def test_evidence_guard_checks_evidence_inventory(self):
        profile = load_profile("wrapup")
        defs = parse_pulse_checks(profile.defaults["pulse_checks"])
        guard = [d for d in defs if d.suite_id == "wrapup_evidence_guard"][0]
        targets = [c.target for c in guard.checks]
        assert any("evidence_inventory.md" in t for t in targets)

    def test_completeness_checks_closeout_artifact(self):
        profile = load_profile("wrapup")
        defs = parse_pulse_checks(profile.defaults["pulse_checks"])
        completeness = [d for d in defs if d.suite_id == "wrapup_completeness"][0]
        targets = [c.target for c in completeness.checks]
        assert any("closeout_artifact.md" in t for t in targets)

    def test_handoff_guard_checks_handoff_artifact(self):
        profile = load_profile("wrapup")
        defs = parse_pulse_checks(profile.defaults["pulse_checks"])
        handoff = [d for d in defs if d.suite_id == "wrapup_handoff_guard"][0]
        targets = [c.target for c in handoff.checks]
        assert any("handoff_artifact.md" in t for t in targets)


class TestWrapupProfileCadencePolicy:
    def test_max_pulse_seconds(self):
        profile = load_profile("wrapup")
        policy = profile.defaults["cadence_policy"]
        assert policy["max_pulse_seconds"] == 3600

    def test_max_tasks_per_pulse(self):
        profile = load_profile("wrapup")
        policy = profile.defaults["cadence_policy"]
        assert policy["max_tasks_per_pulse"] == 5


class TestWrapupProfileNotes:
    def test_notes_document_impl_run_id_requirement(self):
        """Notes must mention impl_run_id so users know the required execution_override."""
        profile = load_profile("wrapup")
        assert "impl_run_id" in profile.defaults["notes"]
