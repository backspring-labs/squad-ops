"""Correction failure-signature model + progress-aware termination (#435, 1.5 A4).

The ruled principle: termination may depend on progress, not only on count.
Typed acceptance gives every failure a machine-comparable identity; this module
turns a round's ``failure_evidence`` into a normalized signature, classifies
round-over-round movement, and decides the one termination the 1.5 bounded
lever authorizes — ``plan_defect`` on an exact adjacent repeat where both
rounds' decisions carried a structural-plan-change candidate.

Design-gate bindings (decision table on #435; M2→M3 gate evaluation):
candidates appear in ~89% of deltas, so candidate presence is context — ALL
selectivity comes from the repeat-signature condition. shk-4 (three identical
``tighten_acceptance/patch`` rounds against one unwinnable qa task) is the
canonical true positive; single-round candidate cycles that then converged are
the false-positive population the rule must never touch.

Pure functions over evidence dicts — the correction runner owns state,
artifacts, and the abort.
"""

from __future__ import annotations

from typing import Any

from squadops.cycles.verification_integrity import ResultStatus

#: The decision-handler vocabulary value meaning "no structural candidate".
CANDIDATE_NONE = "none"


def failure_signature(failure_evidence: dict[str, Any]) -> frozenset[tuple[str, str, str]] | None:
    """The round's normalized product-failure signature, or ``None``.

    One element per failing product check row: ``(check_id, subject_file,
    reason_token)``. Only those three fields participate — evidence text
    (tracebacks, snippets, summaries) never alters the signature, so a
    re-described identical failure still repeats. ``None`` when the round has
    no product signature: an infra round (``extraction_loss`` /
    ``emission_failure`` — the A3 categories own its routing) or no failing
    rows at all.

    #878 (minimum): the runner's structured ``suite_broken`` verdict joins the
    reason token when present. It is a machine fact, not prose, so the
    evidence-text rule above is intact — and without it a behavioral failure
    (suite ran, assertions failed) and a discovery failure (no collectable
    suite) collapse into one ``tests_pass||failed`` element: roll 15
    (run_783f50a2d564) was terminated as a false exact-repeat across exactly
    that pair, one round before the #886 own-artifact routing would have
    repaired the second failure. Absent/None (legacy rows, non-suite checks)
    leaves the token byte-identical to the pre-#878 form.
    """
    if not isinstance(failure_evidence, dict):
        return None
    if isinstance(failure_evidence.get("emission_failure"), dict):
        return None
    if failure_evidence.get("extraction_loss") is True:
        return None
    elements: set[tuple[str, str, str]] = set()
    checks = (failure_evidence.get("validation_result") or {}).get("checks") or []
    for row in checks:
        if not isinstance(row, dict):
            continue
        failed = row.get("passed") is False or row.get("status") in (
            ResultStatus.FAILED,
            ResultStatus.ERROR,
        )
        if not failed:
            continue
        check_id = str(row.get("check", ""))
        if not check_id:
            continue
        subject = str(row.get("file") or row.get("subject") or "")
        reason = row.get("reason")
        reason_token = (
            str(reason)
            if isinstance(reason, str) and reason
            else str(row.get("status", ResultStatus.FAILED))
        )
        suite_broken = row.get("suite_broken")
        if suite_broken is not None:
            health = "broken" if suite_broken else "ran"
            reason_token = f"{reason_token};suite_health={health}"
        elements.add((check_id, subject, reason_token))
    return frozenset(elements) if elements else None


# Movement classes (A4.2). Strings, not an enum — event-payload vocabulary.
MOVEMENT_NEW = "new"
MOVEMENT_REPEAT = "repeat"
MOVEMENT_PROGRESS = "progress"
MOVEMENT_EXPANSION = "expansion"
MOVEMENT_SHIFTED = "shifted"


def classify_movement(
    previous: frozenset[tuple[str, str, str]] | None,
    current: frozenset[tuple[str, str, str]],
) -> str:
    """Round-over-round movement per the A4.2 table.

    Partial signature reduction is PROGRESS and resets the repeat condition —
    a binary repeat/no-repeat rule would terminate while some failures are
    being fixed. Expansion (everything still failing plus more) is recorded
    but deliberately NOT a repeat: the default rule requires exact equality,
    and the attempt/budget bounds still apply.
    """
    if not previous:
        return MOVEMENT_NEW
    if current == previous:
        return MOVEMENT_REPEAT
    if current < previous:
        return MOVEMENT_PROGRESS
    if current > previous:
        return MOVEMENT_EXPANSION
    return MOVEMENT_SHIFTED


def should_terminate_plan_defect(
    previous: frozenset[tuple[str, str, str]] | None,
    current: frozenset[tuple[str, str, str]] | None,
    previous_candidate: str | None,
    current_candidate: str | None,
) -> bool:
    """The A4.3 default rule — the ONLY termination this lever authorizes.

    Two ADJACENT rounds, the SAME normalized complete signature, and BOTH
    rounds' decisions carrying a non-``none`` structural candidate. Candidate
    presence alone can never fire this (it is true of ~89% of deltas); a
    missing signature on either side can never fire it (infra rounds cleared
    the state upstream).
    """
    if not previous or not current:
        return False
    if classify_movement(previous, current) != MOVEMENT_REPEAT:
        return False
    return bool(
        previous_candidate
        and previous_candidate != CANDIDATE_NONE
        and current_candidate
        and current_candidate != CANDIDATE_NONE
    )


def render_signature(signature: frozenset[tuple[str, str, str]]) -> tuple[str, ...]:
    """Stable human/artifact rendering: sorted ``check|subject|reason`` strings."""
    return tuple(sorted("|".join(element) for element in signature))
