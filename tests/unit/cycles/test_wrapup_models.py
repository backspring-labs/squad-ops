"""Tests for SIP-0080 wrap-up domain models (Phase 1).

Covers count guards, duplicate detection, convention enforcement,
and cross-constant consistency for constants classes, ALLOWED_SUGGESTED_OWNERS,
and REQUIRED_WRAPUP_ROLES.
"""

from __future__ import annotations

import pytest

from squadops.cycles.models import REQUIRED_WRAPUP_ROLES
from squadops.cycles.wrapup_models import (
    ALLOWED_SUGGESTED_OWNERS,
    CloseoutRecommendation,
    ConfidenceClassification,
    NextCycleRecommendation,
    UnresolvedIssueSeverity,
    UnresolvedIssueType,
)

pytestmark = [pytest.mark.domain_orchestration]


def _get_constant_values(cls):
    """Extract all public string constant values from a constants class."""
    return {v for k, v in vars(cls).items() if not k.startswith("_") and isinstance(v, str)}


# ---------------------------------------------------------------------------
# Count guards — catch accidental addition/removal of constants
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "cls,expected_count",
    [
        (ConfidenceClassification, 6),
        (CloseoutRecommendation, 4),
        (UnresolvedIssueType, 7),
        (UnresolvedIssueSeverity, 4),
        (NextCycleRecommendation, 5),
    ],
    ids=lambda x: x.__name__ if isinstance(x, type) else str(x),
)
def test_constants_class_value_count(cls, expected_count):
    """Each constants class has exactly the specified number of values.

    Bug caught: accidental addition or removal of a constant.
    """
    assert len(_get_constant_values(cls)) == expected_count


# ---------------------------------------------------------------------------
# Duplicate guards — catch copy-paste errors where two constants share a value
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "cls",
    [
        ConfidenceClassification,
        CloseoutRecommendation,
        UnresolvedIssueType,
        UnresolvedIssueSeverity,
        NextCycleRecommendation,
    ],
    ids=lambda x: x.__name__,
)
def test_constants_class_no_duplicate_values(cls):
    """No two constants in the same class share a string value.

    Bug caught: copy-paste error where a new constant reuses an existing value.
    """
    values = _get_constant_values(cls)
    attrs = [v for k, v in vars(cls).items() if not k.startswith("_") and isinstance(v, str)]
    assert len(attrs) == len(values), f"Duplicate values detected in {cls.__name__}"


# ---------------------------------------------------------------------------
# Convention guard — all values must be lowercase strings
# ---------------------------------------------------------------------------


def test_confidence_values_are_lowercase_strings():
    """Convention: all ConfidenceClassification values must be lowercase strings.

    Bug caught: mixed-case value breaks case-sensitive comparisons downstream.
    """
    for val in _get_constant_values(ConfidenceClassification):
        assert val == val.lower(), f"Non-lowercase value: {val}"
        assert isinstance(val, str)


# ---------------------------------------------------------------------------
# ALLOWED_SUGGESTED_OWNERS count guard (SIP-0080 §7.5)
# ---------------------------------------------------------------------------


def test_allowed_suggested_owners_count():
    """ALLOWED_SUGGESTED_OWNERS has exactly 7 entries (6 agent roles + operator).

    Bug caught: accidental addition or removal of an allowed owner.
    """
    assert len(ALLOWED_SUGGESTED_OWNERS) == 7


# ---------------------------------------------------------------------------
# Cross-constant consistency
# ---------------------------------------------------------------------------


def test_required_wrapup_roles_are_allowed_owners():
    """All required wrap-up roles must appear in ALLOWED_SUGGESTED_OWNERS.

    Bug caught: adding a role to REQUIRED_WRAPUP_ROLES that isn't recognized
    as a valid issue owner, causing downstream validation failures.
    """
    assert REQUIRED_WRAPUP_ROLES <= ALLOWED_SUGGESTED_OWNERS


# ---------------------------------------------------------------------------
# REQUIRED_WRAPUP_ROLES scope guard
# ---------------------------------------------------------------------------


def test_wrapup_roles_exclude_non_wrapup_roles():
    """Wrap-up does not require strat, dev, or builder roles (SIP-0080 §7.1).

    Bug caught: scope creep adding planning/build roles to a wrap-up-only workload.
    """
    assert "strat" not in REQUIRED_WRAPUP_ROLES
    assert "dev" not in REQUIRED_WRAPUP_ROLES
    assert "builder" not in REQUIRED_WRAPUP_ROLES
