"""Tests for squad profile validation utilities (SIP-0075 §1.3)."""

from __future__ import annotations

import pytest

from squadops.cycles.models import ProfileValidationError
from squadops.cycles.profile_utils import (
    slugify_profile_name,
    validate_agent_entries,
    validate_config_overrides,
    validate_profile_id,
)

pytestmark = [pytest.mark.domain_orchestration]


class TestSlugifyProfileName:
    def test_simple_name(self):
        assert slugify_profile_name("Full Squad") == "full-squad"

    def test_special_characters(self):
        assert slugify_profile_name("My Profile (v2)!") == "my-profile-v2"

    def test_leading_trailing_hyphens_stripped(self):
        assert slugify_profile_name("--test--") == "test"

    def test_multiple_spaces_become_single_hyphen(self):
        assert slugify_profile_name("a   b   c") == "a-b-c"

    def test_max_length_truncated(self):
        long_name = "a" * 100
        result = slugify_profile_name(long_name)
        assert len(result) <= 64

    def test_empty_after_slugify_raises(self):
        with pytest.raises(ProfileValidationError, match="Cannot slugify"):
            slugify_profile_name("!!!")

    def test_already_slugified(self):
        assert slugify_profile_name("already-a-slug") == "already-a-slug"

    def test_uppercase_lowered(self):
        assert slugify_profile_name("TestProfile") == "testprofile"

    def test_numbers_preserved(self):
        assert slugify_profile_name("squad-v2") == "squad-v2"


class TestValidateProfileId:
    def test_valid_id(self):
        validate_profile_id("full-squad")

    def test_empty_raises(self):
        with pytest.raises(ProfileValidationError, match="must not be empty"):
            validate_profile_id("")

    def test_too_long_raises(self):
        with pytest.raises(ProfileValidationError, match="exceeds"):
            validate_profile_id("a" * 65)

    def test_uppercase_rejected(self):
        with pytest.raises(ProfileValidationError, match="lowercase"):
            validate_profile_id("Full-Squad")

    def test_spaces_rejected(self):
        with pytest.raises(ProfileValidationError, match="lowercase"):
            validate_profile_id("full squad")

    def test_single_char(self):
        with pytest.raises(ProfileValidationError, match="lowercase"):
            validate_profile_id("a")

    def test_two_chars_valid(self):
        validate_profile_id("ab")

    def test_leading_hyphen_rejected(self):
        with pytest.raises(ProfileValidationError, match="lowercase"):
            validate_profile_id("-test")


class TestValidateConfigOverrides:
    def test_all_known_keys(self):
        result = validate_config_overrides(
            {"temperature": 0.7, "max_completion_tokens": 1000, "timeout_seconds": 30}
        )
        assert result == []

    def test_unknown_keys_returned(self):
        result = validate_config_overrides({"temperature": 0.7, "bad_key": 1, "another_bad": 2})
        assert result == ["another_bad", "bad_key"]

    def test_empty_dict(self):
        assert validate_config_overrides({}) == []


class TestValidateAgentEntries:
    def test_valid_entries(self):
        agents = [
            {"agent_id": "neo", "role": "dev", "model": "qwen2.5:7b"},
            {"agent_id": "eve", "role": "qa", "model": "qwen2.5:7b"},
        ]
        assert validate_agent_entries(agents) == []

    def test_empty_agent_id(self):
        agents = [{"agent_id": "", "role": "dev", "model": "qwen2.5:7b"}]
        errors = validate_agent_entries(agents)
        assert any("agent_id must not be empty" in e for e in errors)

    def test_empty_model(self):
        agents = [{"agent_id": "neo", "role": "dev", "model": ""}]
        errors = validate_agent_entries(agents)
        assert any("model must not be empty" in e for e in errors)

    def test_duplicate_agent_ids(self):
        agents = [
            {"agent_id": "neo", "role": "dev", "model": "qwen2.5:7b"},
            {"agent_id": "neo", "role": "qa", "model": "qwen2.5:7b"},
        ]
        errors = validate_agent_entries(agents)
        assert any("duplicate agent_id" in e for e in errors)

    def test_unknown_config_overrides(self):
        agents = [
            {
                "agent_id": "neo",
                "role": "dev",
                "model": "qwen2.5:7b",
                "config_overrides": {"bad_key": 1},
            }
        ]
        errors = validate_agent_entries(agents)
        assert any("unknown config_overrides keys" in e for e in errors)

    def test_missing_fields_use_defaults(self):
        agents = [{"agent_id": "neo", "role": "dev", "model": "qwen2.5:7b"}]
        assert validate_agent_entries(agents) == []
