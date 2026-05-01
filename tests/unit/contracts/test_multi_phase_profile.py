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
        assert types == ["framing", "implementation", "wrapup"]


class TestMultiPhaseGates:
    def test_has_one_named_gate(self):
        profile = load_profile("multi-phase")
        gates = profile.defaults["task_flow_policy"]["gates"]
        assert len(gates) == 1

    def test_gate_name(self):
        profile = load_profile("multi-phase")
        gates = profile.defaults["task_flow_policy"]["gates"]
        assert gates[0]["name"] == "progress_approval_required"

    def test_planning_workload_has_named_gate(self):
        profile = load_profile("multi-phase")
        seq = profile.defaults["workload_sequence"]
        assert seq[0]["gate"] == "progress_approval_required"

    def test_implementation_workload_has_auto_gate(self):
        profile = load_profile("multi-phase")
        seq = profile.defaults["workload_sequence"]
        assert seq[1]["gate"] == "auto"

    def test_wrapup_has_no_gate(self):
        profile = load_profile("multi-phase")
        seq = profile.defaults["workload_sequence"]
        assert seq[2]["gate"] is None
