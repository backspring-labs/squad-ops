"""
Unit tests for CycleRequestProfile (CRP) contract pack — SIP-0065 §5.

Tests schema validation, profile loading, override computation,
merge_config consistency, and hash determinism.
"""

import pytest

from squadops.contracts.cycle_request_profiles import (
    compute_overrides,
    list_profiles,
    load_profile,
    merge_config,
)
from squadops.contracts.cycle_request_profiles.schema import (
    CycleRequestProfile,
    PromptMeta,
)
from squadops.cycles.lifecycle import compute_config_hash


# =============================================================================
# Schema validation
# =============================================================================


class TestCRPSchema:
    """CycleRequestProfile Pydantic model validation."""

    def test_minimal_valid_profile(self):
        profile = CycleRequestProfile(name="test")
        assert profile.name == "test"
        assert profile.defaults == {}
        assert profile.prompts == {}

    def test_full_profile(self):
        profile = CycleRequestProfile(
            name="full",
            description="A full test profile",
            defaults={"build_strategy": "fresh"},
            prompts={
                "build_strategy": PromptMeta(
                    label="Build Strategy",
                    help_text="How to build",
                    choices=["fresh", "incremental"],
                )
            },
        )
        assert profile.description == "A full test profile"
        assert profile.defaults["build_strategy"] == "fresh"
        assert profile.prompts["build_strategy"].label == "Build Strategy"

    def test_unknown_default_key_rejected(self):
        """CRP defaults must only contain keys known to CycleCreateRequest (D9)."""
        with pytest.raises(ValueError, match="Unknown default keys"):
            CycleRequestProfile(
                name="bad",
                defaults={"totally_bogus_key": "nope"},
            )

    def test_known_default_keys_accepted(self):
        """All valid CycleCreateRequest fields pass validation."""
        profile = CycleRequestProfile(
            name="ok",
            defaults={
                "build_strategy": "incremental",
                "execution_overrides": {"foo": "bar"},
                "expected_artifact_types": ["code"],
                "experiment_context": {"x": 1},
                "notes": "test",
            },
        )
        assert profile.defaults["build_strategy"] == "incremental"


# =============================================================================
# Profile loading
# =============================================================================


class TestProfileLoading:
    """Loading CRP profiles from bundled YAML files."""

    def test_list_profiles_returns_all_bundled(self):
        names = list_profiles()
        assert "default" in names
        assert "benchmark" in names
        assert "selftest" in names
        assert len(names) >= 3

    def test_list_profiles_sorted(self):
        names = list_profiles()
        assert names == sorted(names)

    def test_load_default_profile(self):
        profile = load_profile("default")
        assert isinstance(profile, CycleRequestProfile)
        assert profile.name == "default"
        assert "build_strategy" in profile.defaults

    def test_load_benchmark_profile(self):
        profile = load_profile("benchmark")
        assert profile.name == "benchmark"
        assert "metrics" in profile.defaults["expected_artifact_types"]

    def test_load_selftest_profile(self):
        profile = load_profile("selftest")
        assert profile.name == "selftest"
        assert profile.defaults.get("experiment_context", {}).get("selftest") is True

    def test_load_nonexistent_raises_file_not_found(self):
        with pytest.raises(FileNotFoundError, match="nonexistent"):
            load_profile("nonexistent")

    def test_all_bundled_profiles_validate(self):
        """Every bundled profile must load and pass schema validation."""
        for name in list_profiles():
            profile = load_profile(name)
            assert isinstance(profile, CycleRequestProfile)
            assert profile.name == name


# =============================================================================
# Override computation (SIP-0065 §5.3)
# =============================================================================


class TestComputeOverrides:
    """Override diff computation — §5.3 critical rule."""

    def test_empty_when_values_match_defaults(self):
        defaults = {"build_strategy": "fresh", "notes": "hello"}
        user_values = {"build_strategy": "fresh", "notes": "hello"}
        assert compute_overrides(defaults, user_values) == {}

    def test_returns_only_changed_fields(self):
        defaults = {"build_strategy": "fresh", "notes": "hello"}
        user_values = {"build_strategy": "incremental", "notes": "hello"}
        overrides = compute_overrides(defaults, user_values)
        assert overrides == {"build_strategy": "incremental"}
        assert "notes" not in overrides

    def test_new_field_not_in_defaults_is_override(self):
        defaults = {"build_strategy": "fresh"}
        user_values = {"build_strategy": "fresh", "notes": "added"}
        overrides = compute_overrides(defaults, user_values)
        assert overrides == {"notes": "added"}

    def test_empty_defaults_all_values_are_overrides(self):
        defaults = {}
        user_values = {"build_strategy": "fresh"}
        overrides = compute_overrides(defaults, user_values)
        assert overrides == {"build_strategy": "fresh"}

    def test_empty_user_values_no_overrides(self):
        defaults = {"build_strategy": "fresh"}
        user_values = {}
        assert compute_overrides(defaults, user_values) == {}

    def test_bidirectional_rule(self):
        """§5.3: fields equal to default MUST NOT appear; different MUST appear."""
        defaults = {"a": 1, "b": 2, "c": 3}
        user_values = {"a": 1, "b": 99, "c": 3, "d": 4}
        overrides = compute_overrides(defaults, user_values)
        # b changed (2→99), d is new — both must appear
        assert overrides == {"b": 99, "d": 4}
        # a and c match defaults — must NOT appear
        assert "a" not in overrides
        assert "c" not in overrides


# =============================================================================
# merge_config
# =============================================================================


class TestMergeConfig:
    """Canonical merge helper — used everywhere, never inline {**d, **o}."""

    def test_overrides_win(self):
        result = merge_config({"a": 1, "b": 2}, {"b": 99})
        assert result == {"a": 1, "b": 99}

    def test_empty_overrides(self):
        result = merge_config({"a": 1}, {})
        assert result == {"a": 1}

    def test_empty_defaults(self):
        result = merge_config({}, {"a": 1})
        assert result == {"a": 1}

    def test_both_empty(self):
        assert merge_config({}, {}) == {}


# =============================================================================
# Hash determinism golden tests
# =============================================================================


class TestHashDeterminism:
    """compute_config_hash consistency — CRP + lifecycle must agree."""

    def test_same_inputs_same_hash(self):
        defaults = {"build_strategy": "fresh", "notes": "test"}
        overrides = {"build_strategy": "incremental"}
        h1 = compute_config_hash(defaults, overrides)
        h2 = compute_config_hash(defaults, overrides)
        assert h1 == h2

    def test_merge_config_matches_hash_merge(self):
        """merge_config() produces same merged dict as compute_config_hash uses."""
        defaults = {"a": 1, "b": 2}
        overrides = {"b": 99}
        merged = merge_config(defaults, overrides)
        # compute_config_hash does {**defaults, **overrides} internally
        assert merged == {**defaults, **overrides}

    def test_round_trip_with_compute_overrides(self):
        """Full round-trip: defaults → user_values → compute_overrides → hash."""
        defaults = {"build_strategy": "fresh", "notes": "hello"}
        user_values = {"build_strategy": "incremental", "notes": "hello"}
        overrides = compute_overrides(defaults, user_values)
        # Hash from overrides
        h1 = compute_config_hash(defaults, overrides)
        # Hash from direct diff (same thing manually)
        h2 = compute_config_hash(defaults, {"build_strategy": "incremental"})
        assert h1 == h2

    def test_order_independent(self):
        """Hash is order-independent due to sort_keys=True in canonical JSON."""
        defaults = {"z": 1, "a": 2}
        overrides = {"m": 3}
        h1 = compute_config_hash(defaults, overrides)
        h2 = compute_config_hash({"a": 2, "z": 1}, {"m": 3})
        assert h1 == h2
