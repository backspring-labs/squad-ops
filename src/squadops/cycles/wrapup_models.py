"""Wrap-up workload domain models (SIP-0080).

Constants classes for confidence classification, closeout recommendations,
unresolved issue taxonomy, and next-cycle recommendations.
"""

from __future__ import annotations

from squadops.cycles.verification_integrity import RunVerdict


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
ALLOWED_SUGGESTED_OWNERS = frozenset(
    {
        "lead",
        "qa",
        "dev",
        "data",
        "strat",
        "builder",
        "operator",
    }
)


# --------------------------------------------------------------------------- #
# #683 (SIP-0096 §10/§14): the CycleOutcome-derived confidence ceiling
# --------------------------------------------------------------------------- #

# Rank order for ceiling enforcement — a claimed confidence above the ceiling
# is clamped, never honored (§6.6(4): wrap-up prose cannot override the
# structured verdict).
CONFIDENCE_RANK: dict[str, int] = {
    ConfidenceClassification.VERIFIED_COMPLETE: 5,
    ConfidenceClassification.COMPLETE_WITH_CAVEATS: 4,
    ConfidenceClassification.PARTIAL_COMPLETION: 3,
    ConfidenceClassification.NOT_SUFFICIENTLY_VERIFIED: 2,
    ConfidenceClassification.INCONCLUSIVE: 1,
    ConfidenceClassification.FAILED: 0,
}


def confidence_ceiling(outcome: dict | None) -> tuple[str, str]:
    """The maximum honest confidence for a cycle's evidence, with its basis.

    Deterministic over the ``CycleOutcome.to_dict()`` wire shape (#683):

    - no outcome / zero runs → ``inconclusive`` (fail-closed: absent evidence
      can never support a stronger claim — "on every path", incl. replay and
      legacy dispatches that never threaded the outcome)
    - ``rejected`` → ``partial_completion`` (executed checks failed)
    - ``blocked_unverified`` fully waived → ``complete_with_caveats`` (the
      §6.5 operator accept-with-waiver IS the caveat)
    - ``blocked_unverified`` otherwise → ``not_sufficiently_verified``
    - ``accepted`` with unverified disclosures → ``complete_with_caveats``
    - ``accepted``, everything verified → ``verified_complete``
    """
    if not isinstance(outcome, dict) or not outcome:
        return ConfidenceClassification.INCONCLUSIVE, "verification outcome unavailable"
    if int(outcome.get("run_count", 0)) == 0:
        return ConfidenceClassification.INCONCLUSIVE, "no run evidence recorded"
    verdict = str(outcome.get("verdict", ""))
    if verdict == RunVerdict.REJECTED.value:
        failed = outcome.get("failed") or []
        return (
            ConfidenceClassification.PARTIAL_COMPLETION,
            f"verdict rejected — executed checks failed: {', '.join(map(str, failed)) or '?'}",
        )
    if verdict == RunVerdict.BLOCKED_UNVERIFIED.value:
        required_unmet = set(map(str, outcome.get("required_unmet") or []))
        waived_ids = {str(w.get("check_id")) for w in outcome.get("waived") or []}
        if required_unmet and required_unmet <= waived_ids:
            return (
                ConfidenceClassification.COMPLETE_WITH_CAVEATS,
                "blocked_unverified fully waived by operator gate decision (§6.5)",
            )
        unmet = ", ".join(sorted(required_unmet - waived_ids)) or "?"
        return (
            ConfidenceClassification.NOT_SUFFICIENTLY_VERIFIED,
            f"required checks unverified and unwaived: {unmet}",
        )
    if verdict == RunVerdict.ACCEPTED.value:
        unverified = outcome.get("unverified") or []
        if unverified:
            return (
                ConfidenceClassification.COMPLETE_WITH_CAVEATS,
                f"accepted with {len(unverified)} unverified check(s) disclosed",
            )
        return ConfidenceClassification.VERIFIED_COMPLETE, "accepted; all recorded checks verified"
    return ConfidenceClassification.INCONCLUSIVE, f"unrecognized verdict {verdict!r}"


def verification_evidence_summary(outcome: dict) -> str:
    """Deterministic evidence lines for the wrap-up prompts (data, not prose).

    Rides ``prior_outputs`` into every wrap-up task's prompt so the squad reads
    the same structured basis the closeout handler enforces — the #686 lesson:
    state the rule to the author, don't only spring it at validation.
    """
    ceiling, basis = confidence_ceiling(outcome)
    lines = [
        f"verdict: {outcome.get('verdict', 'unknown')}",
        f"runs: {outcome.get('run_count', 0)}",
        f"verified: {len(outcome.get('verified') or [])}",
        f"failed: {', '.join(map(str, outcome.get('failed') or [])) or 'none'}",
        f"unverified: {len(outcome.get('unverified') or [])}"
        + (
            " (" + ", ".join(str(u.get("check_id")) for u in outcome.get("unverified") or []) + ")"
            if outcome.get("unverified")
            else ""
        ),
        f"waived: {', '.join(str(w.get('check_id')) for w in outcome.get('waived') or []) or 'none'}",
        f"inert: {', '.join(map(str, outcome.get('inert') or [])) or 'none'}",
        f"maximum honest confidence: {ceiling} — {basis}",
    ]
    return "\n".join(lines)
