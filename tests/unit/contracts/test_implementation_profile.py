"""
Unit tests for the implementation cycle request profile (SIP-0079 Phase 4).

Validates that implementation.yaml loads, passes schema validation,
and contains the expected bounded execution keys.
"""

import pytest

from squadops.contracts.cycle_request_profiles import list_profiles, load_profile
from squadops.contracts.cycle_request_profiles.schema import CycleRequestProfile

pytestmark = [pytest.mark.domain_contracts]


class TestImplementationProfile:
    def test_profile_loads(self):
        """implementation.yaml loads and passes schema validation."""
        profile = load_profile("implementation")
        assert isinstance(profile, CycleRequestProfile)
        assert profile.name == "implementation"

    def test_defaults_contain_bounded_execution_keys(self):
        """All 6 bounded execution keys present in defaults."""
        profile = load_profile("implementation")
        defaults = profile.defaults
        for key in (
            "max_task_retries",
            "max_task_seconds",
            "max_consecutive_failures",
            "max_correction_attempts",
            "time_budget_seconds",
            "implementation_pulse_checks",
        ):
            assert key in defaults, f"Missing key: {key}"

    def test_workload_sequence_has_implementation(self):
        """workload_sequence contains an implementation entry."""
        profile = load_profile("implementation")
        sequence = profile.defaults["workload_sequence"]
        types = [entry["type"] for entry in sequence]
        assert "implementation" in types

    def test_pulse_check_suites(self):
        """Two pulse check suites with correct suite_ids."""
        profile = load_profile("implementation")
        suites = profile.defaults["implementation_pulse_checks"]
        suite_ids = [s["suite_id"] for s in suites]
        assert "impl_progress" in suite_ids
        assert "impl_cadence" in suite_ids

    def test_profile_appears_in_listing(self):
        """implementation appears in list_profiles()."""
        names = list_profiles()
        assert "implementation" in names
