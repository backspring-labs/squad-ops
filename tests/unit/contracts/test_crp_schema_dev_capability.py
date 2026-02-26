"""
Unit tests for CRP schema extension with dev_capability (SIP-0072 Phase 1).
"""

import pytest

from squadops.contracts.cycle_request_profiles.schema import (
    _APPLIED_DEFAULTS_EXTRA_KEYS,
    CycleRequestProfile,
    PromptMeta,
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


class TestPromptMeta:
    """SIP-0074 §5.8: PromptMeta type and required fields."""

    def test_minimal_prompt(self):
        meta = PromptMeta(label="Build Strategy")
        assert meta.label == "Build Strategy"
        assert meta.help_text == ""
        assert meta.choices == []
        assert meta.type is None
        assert meta.required is False

    def test_choice_prompt(self):
        meta = PromptMeta(
            label="Build Strategy",
            choices=["fresh", "incremental"],
            type="choice",
            required=True,
        )
        assert meta.type == "choice"
        assert meta.required is True
        assert meta.choices == ["fresh", "incremental"]

    def test_text_prompt(self):
        meta = PromptMeta(label="Custom Notes", type="text")
        assert meta.type == "text"
        assert meta.choices == []

    def test_bool_prompt(self):
        meta = PromptMeta(label="Enable Pulse Checks", type="bool")
        assert meta.type == "bool"

    def test_profile_with_typed_prompts(self):
        profile = CycleRequestProfile(
            name="test-profile",
            defaults={"dev_capability": "python_cli"},
            prompts={
                "build_strategy": PromptMeta(
                    label="Build Strategy",
                    choices=["fresh", "incremental"],
                    type="choice",
                    required=True,
                ),
                "notes": PromptMeta(label="Notes", type="text"),
            },
        )
        assert profile.prompts["build_strategy"].required is True
        assert profile.prompts["build_strategy"].type == "choice"
        assert profile.prompts["notes"].type == "text"

    def test_help_text_preserved(self):
        meta = PromptMeta(
            label="Strategy",
            help_text="Choose how to build the project",
        )
        assert meta.help_text == "Choose how to build the project"
