"""Tests for SIP-0080 wrap-up domain models (Phase 1).

Covers constants classes, ALLOWED_SUGGESTED_OWNERS, WorkloadType.WRAPUP,
and REQUIRED_WRAPUP_ROLES.
"""

from __future__ import annotations

import enum

import pytest

from squadops.cycles.models import REQUIRED_WRAPUP_ROLES, WorkloadType
from squadops.cycles.wrapup_models import (
    ALLOWED_SUGGESTED_OWNERS,
    CloseoutRecommendation,
    ConfidenceClassification,
    NextCycleRecommendation,
    UnresolvedIssueSeverity,
    UnresolvedIssueType,
)


def _get_constant_values(cls):
    """Extract all public string constant values from a constants class."""
    return {
        v
        for k, v in vars(cls).items()
        if not k.startswith("_") and isinstance(v, str)
    }


# ---------------------------------------------------------------------------
# ConfidenceClassification (SIP-0080 §7.4)
# ---------------------------------------------------------------------------


class TestConfidenceClassification:
    def test_has_6_values(self):
        assert len(_get_constant_values(ConfidenceClassification)) == 6

    def test_no_duplicate_values(self):
        values = [
            ConfidenceClassification.VERIFIED_COMPLETE,
            ConfidenceClassification.COMPLETE_WITH_CAVEATS,
            ConfidenceClassification.PARTIAL_COMPLETION,
            ConfidenceClassification.NOT_SUFFICIENTLY_VERIFIED,
            ConfidenceClassification.INCONCLUSIVE,
            ConfidenceClassification.FAILED,
        ]
        assert len(values) == len(set(values))

    def test_values_are_lowercase_strings(self):
        for val in _get_constant_values(ConfidenceClassification):
            assert val == val.lower()
            assert isinstance(val, str)

    def test_not_an_enum(self):
        assert not issubclass(ConfidenceClassification, enum.Enum)

    @pytest.mark.parametrize(
        "attr,expected",
        [
            ("VERIFIED_COMPLETE", "verified_complete"),
            ("COMPLETE_WITH_CAVEATS", "complete_with_caveats"),
            ("PARTIAL_COMPLETION", "partial_completion"),
            ("NOT_SUFFICIENTLY_VERIFIED", "not_sufficiently_verified"),
            ("INCONCLUSIVE", "inconclusive"),
            ("FAILED", "failed"),
        ],
    )
    def test_specific_values(self, attr, expected):
        assert getattr(ConfidenceClassification, attr) == expected


# ---------------------------------------------------------------------------
# CloseoutRecommendation (SIP-0080 §7.6)
# ---------------------------------------------------------------------------


class TestCloseoutRecommendation:
    def test_has_4_values(self):
        assert len(_get_constant_values(CloseoutRecommendation)) == 4

    def test_no_duplicate_values(self):
        values = [
            CloseoutRecommendation.PROCEED,
            CloseoutRecommendation.HARDEN,
            CloseoutRecommendation.REPLAN,
            CloseoutRecommendation.HALT,
        ]
        assert len(values) == len(set(values))

    def test_not_an_enum(self):
        assert not issubclass(CloseoutRecommendation, enum.Enum)


# ---------------------------------------------------------------------------
# UnresolvedIssueType (SIP-0080 §7.5)
# ---------------------------------------------------------------------------


class TestUnresolvedIssueType:
    def test_has_7_values(self):
        assert len(_get_constant_values(UnresolvedIssueType)) == 7

    def test_no_duplicate_values(self):
        values = [
            UnresolvedIssueType.DEFECT,
            UnresolvedIssueType.DESIGN_DEBT,
            UnresolvedIssueType.TEST_GAP,
            UnresolvedIssueType.ENVIRONMENTAL,
            UnresolvedIssueType.DEPENDENCY,
            UnresolvedIssueType.OPERATOR_DECISION_PENDING,
            UnresolvedIssueType.DEFERRED_ENHANCEMENT,
        ]
        assert len(values) == len(set(values))

    def test_not_an_enum(self):
        assert not issubclass(UnresolvedIssueType, enum.Enum)


# ---------------------------------------------------------------------------
# UnresolvedIssueSeverity (SIP-0080 §7.5)
# ---------------------------------------------------------------------------


class TestUnresolvedIssueSeverity:
    def test_has_4_values(self):
        assert len(_get_constant_values(UnresolvedIssueSeverity)) == 4

    def test_no_duplicate_values(self):
        values = [
            UnresolvedIssueSeverity.CRITICAL,
            UnresolvedIssueSeverity.HIGH,
            UnresolvedIssueSeverity.MEDIUM,
            UnresolvedIssueSeverity.LOW,
        ]
        assert len(values) == len(set(values))

    def test_not_an_enum(self):
        assert not issubclass(UnresolvedIssueSeverity, enum.Enum)


# ---------------------------------------------------------------------------
# NextCycleRecommendation (SIP-0080 §7.7)
# ---------------------------------------------------------------------------


class TestNextCycleRecommendation:
    def test_has_5_values(self):
        assert len(_get_constant_values(NextCycleRecommendation)) == 5

    def test_includes_none(self):
        assert NextCycleRecommendation.NONE == "none"

    def test_no_duplicate_values(self):
        values = [
            NextCycleRecommendation.PLANNING,
            NextCycleRecommendation.IMPLEMENTATION,
            NextCycleRecommendation.HARDENING,
            NextCycleRecommendation.RESEARCH,
            NextCycleRecommendation.NONE,
        ]
        assert len(values) == len(set(values))

    def test_not_an_enum(self):
        assert not issubclass(NextCycleRecommendation, enum.Enum)


# ---------------------------------------------------------------------------
# ALLOWED_SUGGESTED_OWNERS (SIP-0080 §7.5)
# ---------------------------------------------------------------------------


class TestAllowedSuggestedOwners:
    def test_has_7_entries(self):
        assert len(ALLOWED_SUGGESTED_OWNERS) == 7

    def test_contains_agent_roles(self):
        for role in ("lead", "qa", "dev", "data", "strat", "builder"):
            assert role in ALLOWED_SUGGESTED_OWNERS

    def test_contains_operator(self):
        assert "operator" in ALLOWED_SUGGESTED_OWNERS

    def test_is_frozenset(self):
        assert isinstance(ALLOWED_SUGGESTED_OWNERS, frozenset)


# ---------------------------------------------------------------------------
# WorkloadType.WRAPUP and REQUIRED_WRAPUP_ROLES (models.py additions)
# ---------------------------------------------------------------------------


class TestWorkloadTypeWrapup:
    def test_wrapup_value(self):
        assert WorkloadType.WRAPUP == "wrapup"


class TestRequiredWrapupRoles:
    def test_exact_roles(self):
        assert REQUIRED_WRAPUP_ROLES == frozenset({"data", "qa", "lead"})

    def test_excludes_strategy_and_dev(self):
        assert "strat" not in REQUIRED_WRAPUP_ROLES
        assert "dev" not in REQUIRED_WRAPUP_ROLES
        assert "builder" not in REQUIRED_WRAPUP_ROLES
