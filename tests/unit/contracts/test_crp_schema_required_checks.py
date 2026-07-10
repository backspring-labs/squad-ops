"""CRP schema tests for the SIP-0096 ``required_checks`` declaration (§6.3).

The key is accepted in defaults and its shape is validated at load — a
malformed required list fails loud rather than silently mis-aggregating at run
end (the "no fallback that masks" rule).
"""

import pytest
from pydantic import ValidationError

from squadops.contracts.cycle_request_profiles.schema import (
    _APPLIED_DEFAULTS_EXTRA_KEYS,
    CycleRequestProfile,
)

pytestmark = [pytest.mark.domain_contracts]


def test_required_checks_is_an_allowed_default_key():
    assert "required_checks" in _APPLIED_DEFAULTS_EXTRA_KEYS


def test_valid_required_checks_list_loads():
    profile = CycleRequestProfile(
        name="req-test",
        defaults={"required_checks": ["tests_pass", "no_stub_fallback_tests"]},
    )
    assert profile.defaults["required_checks"] == ["tests_pass", "no_stub_fallback_tests"]


def test_absent_required_checks_is_fine():
    """Omitting the key means nothing is required — the Phase 1 default (throttle off)."""
    profile = CycleRequestProfile(name="none", defaults={})
    assert "required_checks" not in profile.defaults


def test_empty_required_checks_list_is_fine():
    profile = CycleRequestProfile(name="empty", defaults={"required_checks": []})
    assert profile.defaults["required_checks"] == []


@pytest.mark.parametrize(
    "bad",
    [
        "tests_pass",  # a bare string, not a list
        {"tests_pass": True},  # a dict, not a list
    ],
)
def test_non_list_required_checks_rejected(bad):
    with pytest.raises(ValidationError, match="required_checks must be a list"):
        CycleRequestProfile(name="bad", defaults={"required_checks": bad})


@pytest.mark.parametrize("bad_entry", ["", "   ", 3, None])
def test_non_string_or_empty_entries_rejected(bad_entry):
    with pytest.raises(ValidationError, match="required_checks entries must be non-empty strings"):
        CycleRequestProfile(name="bad", defaults={"required_checks": ["ok", bad_entry]})


def test_duplicate_check_ids_rejected():
    """A duplicate is a profile-authoring bug — surfaced at load, not tolerated."""
    with pytest.raises(ValidationError, match="duplicate check-id"):
        CycleRequestProfile(name="dup", defaults={"required_checks": ["a", "a"]})
