"""Unit tests for the validation cycle request profile (SIP-0092 M1 → M2 gate).

The validation profile is the gate-cycle target referenced in
`docs/plans/SIP-0092-implementation-plan-improvement-plan.md` Milestone Gates.
It must run a plan-then-build sequence at implementation-profile depth with
M1 typed-acceptance active and M2/M3 disabled.
"""

import pytest

from squadops.contracts.cycle_request_profiles import list_profiles, load_profile
from squadops.contracts.cycle_request_profiles.schema import CycleRequestProfile

pytestmark = [pytest.mark.domain_contracts]


class TestValidationProfile:
    def test_profile_loads(self):
        profile = load_profile("validation")
        assert isinstance(profile, CycleRequestProfile)
        assert profile.name == "validation"

    def test_profile_appears_in_listing(self):
        assert "validation" in list_profiles()

    def test_workload_sequence_is_plan_then_build(self):
        """Gate evidence requires both planning and implementation behavior
        to surface, so the profile must run framing → gate → implementation
        (the same shape as `build`, not just `implementation`)."""
        profile = load_profile("validation")
        sequence = profile.defaults["workload_sequence"]
        types = [entry["type"] for entry in sequence]
        assert types == ["framing", "implementation"]

    def test_implementation_depth_self_eval_passes(self):
        """Distinct from `build` (max_self_eval_passes=1), the validation
        profile runs at implementation depth so typed checks fire enough
        per cycle to exercise the gate's `evaluator-error rate <5%` and
        `≥5/10 cycles change an outcome` criteria."""
        profile = load_profile("validation")
        assert profile.defaults["max_self_eval_passes"] == 2

    def test_implementation_depth_correction_attempts(self):
        """Gate's M2 → M3 `structural_plan_change_candidate` diagnostic
        is captured per correction-decision; need budget for ≥2 corrections
        per cycle to make the diagnostic measurable."""
        profile = load_profile("validation")
        assert profile.defaults["max_correction_attempts"] == 3

    def test_typed_acceptance_enabled(self):
        """SIP-0092 M1: master flag must be on in the gate profile."""
        profile = load_profile("validation")
        assert profile.defaults["typed_acceptance"] is True

    def test_command_acceptance_checks_enabled(self):
        """Distinct from `selftest` (which has command_acceptance_checks=false
        for safety in smoke runs), the gate profile exercises command checks."""
        profile = load_profile("validation")
        assert profile.defaults["command_acceptance_checks"] is True

    def test_long_cycle_time_budget(self):
        """Gate inclusion rule requires ≥2h wall-clock or natural termination.
        7200s matches the implementation profile's long-cycle budget."""
        profile = load_profile("validation")
        assert profile.defaults["time_budget_seconds"] >= 7200

    def test_distinct_from_build_profile(self):
        """The validation profile must differ from `build` on at least
        max_self_eval_passes — that's the load-bearing distinction per
        SIP-0092 §6.4.1 (build = shallow, validation = implementation-depth)."""
        validation = load_profile("validation")
        build = load_profile("build")
        assert validation.defaults["max_self_eval_passes"] > build.defaults["max_self_eval_passes"]

    def test_distinct_from_implementation_profile(self):
        """The validation profile must differ from `implementation` on the
        workload_sequence — `implementation` is implementation-only;
        `validation` runs framing → gate → implementation so plan-quality
        signal is part of the gate evidence."""
        validation = load_profile("validation")
        implementation = load_profile("implementation")
        validation_types = [entry["type"] for entry in validation.defaults["workload_sequence"]]
        impl_types = [entry["type"] for entry in implementation.defaults["workload_sequence"]]
        assert validation_types != impl_types
        assert "framing" in validation_types
        assert "framing" not in impl_types
