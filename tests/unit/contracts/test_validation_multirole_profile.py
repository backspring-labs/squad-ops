"""Unit tests for the validation-multirole cycle request profile (SIP-0093).

This profile is the first one to set `plan_authoring_contributors`, which is
what actually activates the multi-role plan authoring path (per-role
`*.propose_plan_tasks` → `governance.merge_plan`). Before this profile existed,
no request profile could turn the path on, so the merger always ran in
sole-author mode. These tests guard that activation.
"""

import pytest

from squadops.contracts.cycle_request_profiles import list_profiles, load_profile
from squadops.contracts.cycle_request_profiles.schema import (
    _ALL_ALLOWED_KEYS,
    CycleRequestProfile,
)

pytestmark = [pytest.mark.domain_contracts]


class TestValidationMultiroleProfile:
    def test_profile_loads(self):
        profile = load_profile("validation-multirole")
        assert isinstance(profile, CycleRequestProfile)
        assert profile.name == "validation-multirole"

    def test_profile_appears_in_listing(self):
        assert "validation-multirole" in list_profiles()

    def test_contributors_activate_all_three_authoring_roles(self):
        """The load-bearing assertion: the profile must enable dev, qa, and
        strategy as plan authors. If this key is dropped (or the schema
        allow-list rejects it), the merger silently falls back to sole-author
        and the multi-role path the profile exists to exercise never runs."""
        profile = load_profile("validation-multirole")
        assert profile.defaults["plan_authoring_contributors"] == [
            "development",
            "qa",
            "strategy",
        ]

    def test_plan_authoring_contributors_is_an_allowed_default_key(self):
        """Regression guard for the activation wiring: without this key in the
        CRP allow-list, `load_profile` raises and no profile can enable
        multi-role authoring."""
        assert "plan_authoring_contributors" in _ALL_ALLOWED_KEYS

    def test_workload_is_framing_then_implementation_with_gate(self):
        """B's output (merged plan + merge_decisions) is produced during
        framing; the gate must pause after framing so it can be inspected
        before any implementation work runs."""
        profile = load_profile("validation-multirole")
        sequence = profile.defaults["workload_sequence"]
        assert [entry["type"] for entry in sequence] == ["framing", "implementation"]
        assert sequence[0]["gate"] == "progress_plan_review"

    def test_distinct_from_validation_profile_on_authoring(self):
        """The stock `validation` profile does NOT set contributors (it runs
        sole-author); `validation-multirole` is precisely the one that adds the
        activation. If they ever converge, the multi-role distinction is lost."""
        validation = load_profile("validation")
        multirole = load_profile("validation-multirole")
        assert "plan_authoring_contributors" not in validation.defaults
        assert "plan_authoring_contributors" in multirole.defaults
