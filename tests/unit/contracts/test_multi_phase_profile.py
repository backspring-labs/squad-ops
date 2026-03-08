"""Tests for multi-phase cycle request profile (SIP-0083 §5.11).

Validates that multi-phase.yaml loads, has the correct 3-workload
sequence (planning → implementation → wrapup), and defines
the expected inter-workload gates.
"""

import pytest

from squadops.contracts.cycle_request_profiles import list_profiles, load_profile
from squadops.contracts.cycle_request_profiles.schema import CycleRequestProfile

pytestmark = [pytest.mark.domain_contracts]


class TestMultiPhaseProfileLoads:
    def test_load_profile_succeeds(self):
        profile = load_profile("multi-phase")
        assert isinstance(profile, CycleRequestProfile)
        assert profile.name == "multi-phase"

    def test_appears_in_listing(self):
        names = list_profiles()
        assert "multi-phase" in names


class TestMultiPhaseWorkloadSequence:
    def test_has_three_workloads(self):
        profile = load_profile("multi-phase")
        seq = profile.defaults["workload_sequence"]
        assert len(seq) == 3

    def test_workload_types(self):
        profile = load_profile("multi-phase")
        seq = profile.defaults["workload_sequence"]
        types = [w["type"] for w in seq]
        assert types == ["planning", "implementation", "wrapup"]


class TestMultiPhaseGates:
    def test_has_two_gates(self):
        profile = load_profile("multi-phase")
        gates = profile.defaults["task_flow_policy"]["gates"]
        assert len(gates) == 2

    def test_gate_names(self):
        profile = load_profile("multi-phase")
        gates = profile.defaults["task_flow_policy"]["gates"]
        names = [g["name"] for g in gates]
        assert "progress_plan_review" in names
        assert "progress_impl_review" in names

    def test_plan_review_gate_on_planning_workload(self):
        profile = load_profile("multi-phase")
        seq = profile.defaults["workload_sequence"]
        assert seq[0]["gate"] == "progress_plan_review"

    def test_impl_review_gate_on_implementation_workload(self):
        profile = load_profile("multi-phase")
        seq = profile.defaults["workload_sequence"]
        assert seq[1]["gate"] == "progress_impl_review"

    def test_wrapup_has_no_gate(self):
        profile = load_profile("multi-phase")
        seq = profile.defaults["workload_sequence"]
        assert seq[2]["gate"] is None
