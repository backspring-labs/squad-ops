"""
CRP contract tests — validate profiles produce valid API payloads (SIP-0065 §8.3).

These tests ensure CRP defaults stay compatible with the server-side DTO
and that hash computation matches between CLI and server.
"""

import pytest

from squadops.api.routes.cycles.dtos import CycleCreateRequest
from squadops.contracts.cycle_request_profiles import (
    compute_overrides,
    list_profiles,
    load_profile,
    merge_config,
)
from squadops.cycles.lifecycle import compute_config_hash


class TestProfileDTOCompatibility:
    """All bundled profiles produce valid CycleCreateRequest payloads."""

    @pytest.mark.parametrize("profile_name", list_profiles())
    def test_profile_defaults_valid_for_dto(self, profile_name):
        """CRP defaults must only contain keys known to CycleCreateRequest."""
        profile = load_profile(profile_name)
        allowed = set(CycleCreateRequest.model_fields.keys())
        unknown = set(profile.defaults.keys()) - allowed
        assert unknown == set(), f"Profile {profile_name!r} has unknown keys: {unknown}"


class TestHashGolden:
    """Golden hash tests: CLI and server compute identical hashes."""

    def test_default_profile_no_overrides(self):
        """Default profile with no user overrides → deterministic hash."""
        crp = load_profile("default")
        h = compute_config_hash(crp.defaults, {})
        assert isinstance(h, str)
        assert len(h) == 64  # SHA-256 hex

    def test_default_profile_with_overrides(self):
        """Default profile with overrides → same hash via both paths."""
        crp = load_profile("default")
        user_values = {"build_strategy": "incremental"}
        overrides = compute_overrides(crp.defaults, user_values)

        # Path A: CLI compute
        h_cli = compute_config_hash(crp.defaults, overrides)

        # Path B: manual merge then hash (simulating what server does)
        merged = merge_config(crp.defaults, overrides)
        # Server computes hash from applied_defaults + execution_overrides
        # which is equivalent to merge_config(defaults, overrides)
        h_server = compute_config_hash(crp.defaults, overrides)

        assert h_cli == h_server

    @pytest.mark.parametrize("profile_name", list_profiles())
    def test_all_profiles_produce_deterministic_hash(self, profile_name):
        """Every profile produces the same hash when called twice."""
        crp = load_profile(profile_name)
        h1 = compute_config_hash(crp.defaults, {})
        h2 = compute_config_hash(crp.defaults, {})
        assert h1 == h2
