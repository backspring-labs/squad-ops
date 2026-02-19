"""
Unit tests for CRP schema extension with pulse_checks and cadence_policy (SIP-0070 Phase 1.5).
"""

import pytest

from squadops.contracts.cycle_request_profiles.schema import (
    _APPLIED_DEFAULTS_EXTRA_KEYS,
    CycleRequestProfile,
)

pytestmark = [pytest.mark.domain_pulse_checks, pytest.mark.domain_contracts]


class TestAppliedDefaultsExtraKeys:
    def test_pulse_checks_in_extra_keys(self):
        assert "pulse_checks" in _APPLIED_DEFAULTS_EXTRA_KEYS

    def test_cadence_policy_in_extra_keys(self):
        assert "cadence_policy" in _APPLIED_DEFAULTS_EXTRA_KEYS

    def test_existing_keys_still_present(self):
        assert "build_tasks" in _APPLIED_DEFAULTS_EXTRA_KEYS
        assert "plan_tasks" in _APPLIED_DEFAULTS_EXTRA_KEYS


class TestCycleRequestProfileWithPulseDefaults:
    def test_pulse_checks_accepted_in_defaults(self):
        """pulse_checks key is accepted in CRP defaults."""
        profile = CycleRequestProfile(
            name="pulse-test",
            defaults={
                "pulse_checks": [
                    {
                        "suite_id": "smoke",
                        "boundary_id": "post_dev",
                        "checks": [{"check_type": "file_exists", "target": "out.txt"}],
                    }
                ],
            },
        )
        assert "pulse_checks" in profile.defaults

    def test_cadence_policy_accepted_in_defaults(self):
        """cadence_policy key is accepted in CRP defaults."""
        profile = CycleRequestProfile(
            name="cadence-test",
            defaults={
                "cadence_policy": {"max_pulse_seconds": 300, "max_tasks_per_pulse": 3},
            },
        )
        assert "cadence_policy" in profile.defaults

    def test_unknown_key_still_rejected(self):
        """Unknown keys are still rejected by the validator."""
        with pytest.raises(Exception, match="Unknown"):
            CycleRequestProfile(
                name="bad",
                defaults={"totally_unknown_key": True},
            )
