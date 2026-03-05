"""Tests for SIP-0079 CRP schema extra keys (bounded execution limits)."""

import pytest

from squadops.contracts.cycle_request_profiles.schema import CycleRequestProfile

pytestmark = [pytest.mark.domain_contracts]


class TestSIP0079SchemaKeys:
    @pytest.mark.parametrize(
        "key",
        [
            "max_task_retries",
            "max_task_seconds",
            "max_consecutive_failures",
            "max_correction_attempts",
            "time_budget_seconds",
            "implementation_pulse_checks",
        ],
    )
    def test_new_key_accepted(self, key):
        """SIP-0079 bounded execution limit keys are accepted in CRP defaults."""
        profile = CycleRequestProfile(name="test", defaults={key: 42})
        assert profile.defaults[key] == 42

    def test_unknown_key_still_rejected(self):
        with pytest.raises(ValueError, match="Unknown default keys"):
            CycleRequestProfile(name="test", defaults={"not_a_real_key": 1})

    def test_multiple_new_keys_together(self):
        profile = CycleRequestProfile(
            name="impl",
            defaults={
                "max_task_retries": 2,
                "max_consecutive_failures": 3,
                "max_correction_attempts": 2,
                "time_budget_seconds": 7200,
            },
        )
        assert profile.defaults["time_budget_seconds"] == 7200
