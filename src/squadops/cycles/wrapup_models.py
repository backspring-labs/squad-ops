"""Wrap-up workload domain models (SIP-0080).

Constants classes for confidence classification, closeout recommendations,
unresolved issue taxonomy, and next-cycle recommendations.
"""

from __future__ import annotations


class ConfidenceClassification:
    """Confidence classification for wrap-up closeout decisions.

    Follows the constants-class pattern (WorkloadType, ArtifactType, EventType).
    """

    VERIFIED_COMPLETE = "verified_complete"
    COMPLETE_WITH_CAVEATS = "complete_with_caveats"
    PARTIAL_COMPLETION = "partial_completion"
    NOT_SUFFICIENTLY_VERIFIED = "not_sufficiently_verified"
    INCONCLUSIVE = "inconclusive"
    FAILED = "failed"


class CloseoutRecommendation:
    """Readiness recommendation for the closeout artifact.

    Follows the constants-class pattern.
    """

    PROCEED = "proceed"
    HARDEN = "harden"
    REPLAN = "replan"
    HALT = "halt"


class UnresolvedIssueType:
    """Type classification for unresolved items in wrap-up.

    Follows the constants-class pattern.
    """

    DEFECT = "defect"
    DESIGN_DEBT = "design_debt"
    TEST_GAP = "test_gap"
    ENVIRONMENTAL = "environmental"
    DEPENDENCY = "dependency"
    OPERATOR_DECISION_PENDING = "operator_decision_pending"
    DEFERRED_ENHANCEMENT = "deferred_enhancement"


class UnresolvedIssueSeverity:
    """Severity classification for unresolved items.

    Follows the constants-class pattern.
    """

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class NextCycleRecommendation:
    """Recommended next cycle type for handoff artifact.

    Follows the constants-class pattern.
    """

    PLANNING = "planning"
    IMPLEMENTATION = "implementation"
    HARDENING = "hardening"
    RESEARCH = "research"
    NONE = "none"


# Controlled vocabulary for suggested_owner field in unresolved items.
# First 6 are agent roles; "operator" indicates a human decision is required.
ALLOWED_SUGGESTED_OWNERS = frozenset({
    "lead",
    "qa",
    "dev",
    "data",
    "strat",
    "builder",
    "operator",
})
