"""
Unit tests for CRP schema extension with dev_capability (SIP-0072 Phase 1).
"""

import pytest

from squadops.contracts.cycle_request_profiles.schema import (
    _APPLIED_DEFAULTS_EXTRA_KEYS,
    CycleRequestProfile,
)

pytestmark = [pytest.mark.domain_contracts]


class TestAppliedDefaultsExtraKeys:
    def test_dev_capability_in_extra_keys(self):
        assert "dev_capability" in _APPLIED_DEFAULTS_EXTRA_KEYS

    def test_existing_keys_still_present(self):
        assert "build_tasks" in _APPLIED_DEFAULTS_EXTRA_KEYS
        assert "plan_tasks" in _APPLIED_DEFAULTS_EXTRA_KEYS
        assert "build_profile" in _APPLIED_DEFAULTS_EXTRA_KEYS
        assert "pulse_checks" in _APPLIED_DEFAULTS_EXTRA_KEYS
        assert "cadence_policy" in _APPLIED_DEFAULTS_EXTRA_KEYS

    def test_generation_timeout_in_extra_keys(self):
        """SIP-0073: generation_timeout is a valid applied_defaults key."""
        assert "generation_timeout" in _APPLIED_DEFAULTS_EXTRA_KEYS


class TestCycleRequestProfileWithDevCapability:
    def test_dev_capability_accepted_in_defaults(self):
        profile = CycleRequestProfile(
            name="fullstack-test",
            defaults={"dev_capability": "fullstack_fastapi_react"},
        )
        assert "dev_capability" in profile.defaults

    def test_dev_capability_with_build_profile(self):
        profile = CycleRequestProfile(
            name="fullstack-test",
            defaults={
                "dev_capability": "fullstack_fastapi_react",
                "build_profile": "fullstack_fastapi_react",
            },
        )
        assert profile.defaults["dev_capability"] == "fullstack_fastapi_react"
        assert profile.defaults["build_profile"] == "fullstack_fastapi_react"

    def test_unknown_key_still_rejected(self):
        with pytest.raises(Exception, match="Unknown"):
            CycleRequestProfile(
                name="bad",
                defaults={"totally_unknown_key": True},
            )
