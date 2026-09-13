"""Correction failure-signature model + progress-aware termination (#435, 1.5 A4).

The ruled principle: termination may depend on progress, not only on count.
Typed acceptance gives every failure a machine-comparable identity; this module
turns a round's ``failure_evidence`` into a normalized signature, classifies
round-over-round movement, and decides the one termination the 1.5 bounded
lever authorizes — ``plan_defect`` when a round carried failures from the round
before it without reducing the count (an exact repeat is the simplest case), and
both rounds' decisions carried a structural-plan-change candidate (#1501).

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

from squadops.cycles.failure_evidence import FailureEvidenceCategory, derive_failure_category
from squadops.cycles.verification_integrity import ResultStatus
from squadops.cycles.verification_normalize import derived_failure_reason, row_is_blocking_failure

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

    #878 (full): when the row carries ``failing_tests``, the suite contributes
    **one element per failing test** rather than a single aggregate element.
    This is what makes the movement table reachable inside a suite: a repair
    that fixes three of eight failures yields a strict subset, which is
    ``MOVEMENT_PROGRESS`` and resets the repeat condition, where the aggregate
    form produced a byte-identical ``tests_pass||failed`` both rounds and read
    as an exact repeat. Roll 2 of the SIP-0104 window (run_6cb3563d3291) is the
    canonical loss: round 0 failed on error-envelope assertions, round 1 on five
    unfilled scaffold slots — two unrelated defects, one collapsed signature, a
    converging run terminated at round 1. Absent (pytest, which emits no machine
    report, and every legacy row) falls back to the aggregate element byte-identically.

    #761: two further machine facts join the token, both already on the row and
    both previously unread. ``runner`` and ``exit_code`` are what remain when a
    runner emits no machine report — pytest today — so the per-test split above
    cannot fire and the whole suite collapses to one element. ``exit_code``
    separates "tests failed" (1) from "no tests collected" (5) and "usage error"
    (4): three different defects that produced one signature, which is the
    REPEAT-vs-SHIFTED blindness #761 reported. Note the report it was filed from
    (``tests_pass||failed``, shk-6 roll-4) predates #626 and #878; those closed
    the vitest half, and this closes the half that was left.

    #761 also folds the round's ``derive_failure_category`` into every element.
    It is deterministic, machine-derived and round-level, so it never varies
    within a round and a true repeat stays byte-identical — shk-4's three
    identical rounds still fire the A4 termination. What it buys is the one
    distinction the row fields cannot make: a round whose app ERRORED and a
    round whose assertions merely failed are different failures, and both
    rendered as ``tests_pass||failed``.

    Deliberately NOT included: ``classify_failure_locus``. It is largely derived
    from the same signals as the category, and every added token raises the odds
    that a genuine repeat reads as a shift — whose failure mode is that A4 never
    terminates and the run burns its whole budget. Over-discrimination is the
    expensive direction here, so the marginal token has to earn its place.

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
    # Round-level and constant across the round's elements (see #761 above).
    category = derive_failure_category(failure_evidence)
    checks = (failure_evidence.get("validation_result") or {}).get("checks") or []
    for row in checks:
        if not isinstance(row, dict):
            continue
        if not row_is_blocking_failure(row):
            continue
        check_id = str(row.get("check", ""))
        if not check_id:
            continue
        subject = str(row.get("file") or row.get("subject") or "")
        reason_token = _reason_token(row, category)
        failing_tests = row.get("failing_tests") or ()
        if failing_tests:
            for identity in failing_tests:
                test_file, _, title = str(identity).partition("::")
                elements.add((check_id, test_file, f"{reason_token};test={title}"))
        else:
            elements.add((check_id, subject, reason_token))
    return frozenset(elements) if elements else None


def _reason_token(row: dict[str, Any], category: str) -> str:
    """One failing row's reason token: machine facts only, in a stable order.

    Extracted when the #761 additions pushed ``failure_signature`` past the
    complexity gate — and it belongs apart anyway, because the ordering here IS
    the contract. Two rounds must build the token the same way or every
    comparison is a shift, so the sequence is fixed and append-only rather than
    conditional on which fields happen to be present.
    """
    # #1472: the same derivation the record uses. THIS PATH READS THE RAW ROW, never the
    # normalized CheckResult, so a fallback applied only in verification_normalize would fix
    # the record and leave the signature collapsing — which is the half that actually cost
    # the 1.7.5 deploy-A rolls. One helper, both consumers, or they drift.
    reason = row.get("reason")
    if not (isinstance(reason, str) and reason):
        reason = derived_failure_reason(row)
    token = (
        str(reason)
        if isinstance(reason, str) and reason
        else str(row.get("status", ResultStatus.FAILED))
    )
    suite_broken = row.get("suite_broken")
    if suite_broken is not None:
        token += f";suite_health={'broken' if suite_broken else 'ran'}"
    # #761: what a runner with no machine report still supplies. `runner` keeps a
    # pytest failure from colliding with a vitest one; `exit` separates "tests
    # failed" (1) from "no tests collected" (5) and "usage error" (4).
    runner = row.get("runner")
    if runner:
        token += f";runner={runner}"
    exit_code = row.get("exit_code")
    if isinstance(exit_code, int):
        token += f";exit={exit_code}"
    # The ordinary category is the baseline and is OMITTED, so a row carrying none of
    # the newer fields still renders byte-identically to its pre-#626/#878 form — the
    # invariant `test_legacy_rows_without_verdict_are_byte_identical` and its siblings
    # pin, and which a token appended unconditionally would have quietly voided. Only
    # an EXCEPTIONAL category is worth a token: it is precisely the case where two
    # rounds differ in a way no row field records.
    if category != FailureEvidenceCategory.EXECUTED_AND_FAILED:
        token += f";cat={category}"
    return token


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
    being fixed. The classes are the event vocabulary and do not decide
    termination on their own: ``carried_failures`` does (#1501), and it treats
    REPEAT, EXPANSION and a SHIFTED round that kept some failures without
    reducing the count alike.
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


def carried_failures(
    previous: frozenset[tuple[str, str, str]] | None,
    current: frozenset[tuple[str, str, str]] | None,
) -> frozenset[tuple[str, str, str]]:
    """The failures a round carried from the round before it without making progress (#1501).

    Non-empty when the two signatures share at least one element AND the round did not
    reduce the failure count; the shared elements are the stable core. Empty otherwise.

    **Why exact equality was not enough.** 1.7.5 React roll 3 (``cyc_89153929749f``) spent
    three correction rounds and 103 minutes on a qa suite whose failing set went 7, 9, 5, 8:
    five tests failed in every attempt, but the set around them churned, so no two adjacent
    signatures were equal and the rule never fired. The per-test split (#878) is what made
    this reachable. A finer signature raises the odds that a genuine repeat reads as a shift,
    the failure mode the ``failure_signature`` docstring warns about: 1.6.5 React roll 3
    ended ``plan_defect`` at round 1 on the aggregate element, and today its re-authored
    suite's renamed test makes the same two rounds a shift.

    **Why the count, and not any overlap.** Partial reduction is progress and resets the
    repeat condition, the #435 decision table's principle: a repair that fixes three of
    eight failures leaves five in common and must not terminate. So a round that reduced
    the count never fires, whether the rest is a strict subset or the round also broke
    something new. What fires is a round that cleared nothing (a repeat, or everything
    still failing plus more) or cleared some and broke as many (the churn roll 3 shows).
    A disjoint round shares nothing and never fires either; #878's roll 2 fixed unrelated
    defects in sequence.

    **What the stored evidence says, and what it cannot.** Replayed over every correction
    chain in the vault with suite reports on two adjacent rounds and candidates on both
    (20 chains, 2026-09-13): this rule fires in 15 and the exact rule in 9, and none of the
    15 went on to pass its suite. One of the 15 is 1.6.5 React roll 6, whose previous repair
    was refused; ``repair_refused_in_round`` clears that round before this rule is asked
    (#1129), and the replay did not model refusals. No stored chain converged after a round
    that kept any failure, so the corpus cannot show the false-positive side. The principle
    above is what protects it.
    """
    if not previous or not current:
        return frozenset()
    shared = previous & current
    if not shared or len(current) < len(previous):
        return frozenset()
    return shared


def should_terminate_plan_defect(
    previous: frozenset[tuple[str, str, str]] | None,
    current: frozenset[tuple[str, str, str]] | None,
    previous_candidate: str | None,
    current_candidate: str | None,
) -> bool:
    """The A4.3 default rule — the ONLY termination this lever authorizes.

    Two ADJACENT rounds, failures CARRIED between them without progress
    (``carried_failures``; an exact repeat is the simplest case), and BOTH rounds'
    decisions carrying a non-``none`` structural candidate. Candidate presence
    alone can never fire this (it is true of ~89% of deltas); a missing signature
    on either side can never fire it (infra rounds cleared the state upstream).
    """
    if not carried_failures(previous, current):
        return False
    return bool(
        previous_candidate
        and previous_candidate != CANDIDATE_NONE
        and current_candidate
        and current_candidate != CANDIDATE_NONE
    )


#: The executor's wording for a repair that patch verification REFUSED — never applied to
#: the tree. One constant, two readers: the executor writes it into the run-lived
#: rejection carry (#870), and the terminal below reads it to know that the previous
#: round's failure signature was measured against an UNREPAIRED tree (#1129).
REPAIR_REFUSED_MARKER = "repair REJECTED by patch verification"


def repair_refused_in_round(repair_rejections: list[str] | None, round_no: int) -> bool:
    """Whether round ``round_no``'s repair was refused by patch verification (#1129).

    A refused patch is not a round the signature rule may count: no retest ran, the failed
    task was re-dispatched against the unrepaired tree, and the failure signature repeated
    *by construction*. Reading that repeat as "the repair did not help" is how 1.6.5
    FastAPI+React rolls 5 and 6 ended as ``plan_defect`` after zero applied repairs — roll
    6's refused patch carried the correct fix. The carry entry is the executor's own
    ``"correction attempt N: <REPAIR_REFUSED_MARKER> …"`` line; a retest that ran and
    FAILED is a different entry and stays informative.
    """
    prefix = f"correction attempt {round_no}: {REPAIR_REFUSED_MARKER}"
    return any(str(entry).startswith(prefix) for entry in repair_rejections or [])


def render_signature(signature: frozenset[tuple[str, str, str]]) -> tuple[str, ...]:
    """Stable human/artifact rendering: sorted ``check|subject|reason`` strings."""
    return tuple(sorted("|".join(element) for element in signature))
