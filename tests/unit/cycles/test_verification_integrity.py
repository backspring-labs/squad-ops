"""Tests for the SIP-0096 Phase 1 verification-integrity core.

Covers the integrity invariant (§6.1/§6.2) property-style: only
executed-and-passed credits, not-executed never credits and always discloses,
required not-executed blocks as ``blocked_unverified``, requiredness is never
inferred, and the module stays pure. Each test names the bug it catches.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from squadops.cycles import verification_integrity as vi
from squadops.cycles.verification_integrity import (
    CheckResult,
    EvidenceFamily,
    NotExecutedReason,
    ResultStatus,
    RunVerdict,
    aggregate_verification,
    classify,
)


def _passed(check_id: str = "c", **kw) -> CheckResult:
    return CheckResult(check_id=check_id, status=ResultStatus.PASSED, **kw)


def _failed(check_id: str = "c", **kw) -> CheckResult:
    return CheckResult(check_id=check_id, status=ResultStatus.FAILED, **kw)


def _skipped(check_id: str = "c", reason=NotExecutedReason.MISSING_TOOLING, **kw) -> CheckResult:
    return CheckResult(check_id=check_id, status=ResultStatus.SKIPPED, reason=reason, **kw)


# --------------------------------------------------------------------------- #
# classify — the §6.1 mapping (bug caught: a status silently credited/miscredited)
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    ("status", "expected"),
    [
        (ResultStatus.PASSED, EvidenceFamily.EXECUTED_PASSED),
        (ResultStatus.FAILED, EvidenceFamily.EXECUTED_FAILED),
        (ResultStatus.ERROR, EvidenceFamily.EXECUTED_FAILED),  # §6.1.4: error blocks, never credits
        (ResultStatus.SKIPPED, EvidenceFamily.NOT_EXECUTED),
        ("not_executed", EvidenceFamily.NOT_EXECUTED),  # runner vocabulary → not-executed
        ("", EvidenceFamily.NOT_EXECUTED),  # empty → zero evidence, never a silent pass
        ("weird_unknown_token", EvidenceFamily.NOT_EXECUTED),  # unknown must not credit
        ("PASSED", EvidenceFamily.EXECUTED_PASSED),  # case-insensitive
    ],
)
def test_classify_status_to_family(status, expected):
    assert classify(CheckResult(check_id="c", status=status)) is expected


def test_classify_undisclosed_stub_pass_is_not_executed():
    """A stub reporting pass must NOT credit as executed-passed (§6.6.1)."""
    r = CheckResult(check_id="tests_pass", status=ResultStatus.PASSED, is_stub=True)
    assert classify(r) is EvidenceFamily.NOT_EXECUTED


def test_classify_disclosed_stub_pass_credits():
    """When the stub substitution IS the disclosed subject under test, pass credits (§6.6.1)."""
    r = CheckResult(
        check_id="stub_under_test", status=ResultStatus.PASSED, is_stub=True, stub_disclosed=True
    )
    assert classify(r) is EvidenceFamily.EXECUTED_PASSED


# --------------------------------------------------------------------------- #
# aggregate — verdicts (bug caught: wrong verdict lets a bad run read green)
# --------------------------------------------------------------------------- #


def test_all_passed_no_required_is_accepted():
    s = aggregate_verification([_passed("a"), _passed("b")])
    assert s.verdict is RunVerdict.ACCEPTED
    assert s.verified == ("a", "b")
    assert s.failed == ()
    assert s.pass_rate == 1.0


def test_executed_failure_is_rejected_not_blocked():
    s = aggregate_verification([_passed("a"), _failed("b")])
    assert s.verdict is RunVerdict.REJECTED
    assert s.failed == ("b",)
    assert s.required_unmet == ()


def test_required_not_executed_is_blocked_unverified():
    """A required check that didn't run blocks distinctly from a product failure (AC#2)."""
    s = aggregate_verification([_passed("a"), _skipped("b")], required_check_ids=["b"])
    assert s.verdict is RunVerdict.BLOCKED_UNVERIFIED
    assert s.required_unmet == ("b",)
    # distinct from rejected: nothing executed-failed here
    assert s.failed == ()


def test_required_check_with_no_result_blocks_and_is_disclosed():
    """A required check that produced NO result (#291) blocks and is never silently absent."""
    s = aggregate_verification([_passed("a")], required_check_ids=["required_files"])
    assert s.verdict is RunVerdict.BLOCKED_UNVERIFIED
    assert s.required_unmet == ("required_files",)
    disclosed = {u.check_id: u for u in s.unverified}
    assert "required_files" in disclosed
    assert disclosed["required_files"].reason == NotExecutedReason.SUBJECT_MISSING
    assert disclosed["required_files"].required is True


def test_blocked_takes_precedence_over_failure():
    """Required-not-executed AND a failure both present → blocked_unverified (AC#2 is unconditional)."""
    s = aggregate_verification(
        [_failed("a"), _skipped("b")],
        required_check_ids=["b"],
    )
    assert s.verdict is RunVerdict.BLOCKED_UNVERIFIED
    # the failure is still disclosed, just not the verdict driver
    assert s.failed == ("a",)


def test_stub_pass_on_required_check_blocks():
    """A required check whose only 'pass' is a stub is unverified, not accepted (§6.6.1 + §6.2)."""
    s = aggregate_verification(
        [CheckResult(check_id="tests_pass", status=ResultStatus.PASSED, is_stub=True)],
        required_check_ids=["tests_pass"],
    )
    assert s.verdict is RunVerdict.BLOCKED_UNVERIFIED
    assert s.required_unmet == ("tests_pass",)


# --------------------------------------------------------------------------- #
# aggregate — the AC#1 "zero evidence, never 100%" property
# --------------------------------------------------------------------------- #


def test_zero_of_zero_executed_is_zero_evidence_not_100_percent():
    """AC#1: '0 failed of 0 executed' is zero evidence, never 100%."""
    s = aggregate_verification([])
    assert s.executed_count == 0
    assert s.passed_count == 0
    assert s.pass_rate == 0.0  # NOT 1.0
    assert s.verdict is RunVerdict.ACCEPTED  # inert: no required checks, nothing failed


# --------------------------------------------------------------------------- #
# #388 — a run that did not succeed must never read `accepted` on zero evidence
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    ("run_succeeded", "expected"),
    [
        (True, RunVerdict.ACCEPTED),  # completed run: inert Phase-1 behavior preserved
        (False, RunVerdict.BLOCKED_UNVERIFIED),  # #388: FAILED + zero evidence ≠ accepted
    ],
)
def test_zero_evidence_verdict_tracks_run_success(run_succeeded, expected):
    """Zero-of-zero is zero evidence for the *verdict*, not an endorsement (#388).

    Catches the field bug (cyc_60eb5a481b5b): a run that FAILED inside the builder
    correction loop before any check ran displayed `Verdict: accepted` next to
    `Status: FAILED`.
    """
    s = aggregate_verification([], run_succeeded=run_succeeded)
    assert s.executed_count == 0
    assert s.verdict is expected


def test_failed_run_with_only_passed_checks_is_not_accepted():
    """A run that died for a non-check reason after some checks passed still cannot
    read `accepted` — verification never completed (#388)."""
    s = aggregate_verification([_passed("a"), _passed("b")], run_succeeded=False)
    assert s.passed_count == 2
    assert s.verdict is RunVerdict.BLOCKED_UNVERIFIED


def test_failed_run_with_a_failed_check_is_rejected_not_blocked():
    """A genuine executed-failure on a failed run is a product `rejected`, not a
    harness `blocked_unverified`: the failed-check branch keeps precedence over the
    run-success gate (#388) — reordering the two would regress this."""
    s = aggregate_verification([_failed("a")], run_succeeded=False)
    assert s.verdict is RunVerdict.REJECTED
    assert s.failed == ("a",)


def test_not_executed_excluded_from_denominator():
    """A skipped check cannot inflate pass_rate: 1 passed + 1 skipped is 1/1, not 1/2."""
    s = aggregate_verification([_passed("a"), _skipped("b")])
    assert s.executed_count == 1
    assert s.passed_count == 1
    assert s.pass_rate == 1.0  # skipped excluded from denominator, not counted as 0.5


def test_not_executed_never_improves_pass_count():
    """Not-executed results add nothing to passed_count (they are non-creditable)."""
    s = aggregate_verification([_skipped("a"), _skipped("b")])
    assert s.passed_count == 0
    assert s.executed_count == 0
    assert s.pass_rate == 0.0


def test_optional_not_executed_disclosed_but_non_blocking():
    """Optional (non-required) not-executed is disclosed but never blocks (§6.2 'never invisible')."""
    s = aggregate_verification([_passed("a"), _skipped("opt")])  # 'opt' not required
    assert s.verdict is RunVerdict.ACCEPTED
    disclosed = {u.check_id for u in s.unverified}
    assert "opt" in disclosed
    assert s.required_unmet == ()


def test_missing_reason_disclosed_not_masked():
    """A not-executed result with no reason is disclosed as 'unspecified', never a fake diagnosis."""
    s = aggregate_verification(
        [CheckResult(check_id="b", status=ResultStatus.SKIPPED, reason=None)]
    )
    disclosed = {u.check_id: u for u in s.unverified}
    assert disclosed["b"].reason == vi.UNSPECIFIED_REASON


# --------------------------------------------------------------------------- #
# AC#5 — requiredness is declared, never inferred
# --------------------------------------------------------------------------- #


def test_requiredness_not_inferred_from_name():
    """A check whose name looks 'required' does NOT block unless explicitly declared (AC#5)."""
    # names that a naive heuristic might treat as required
    for name in ("required_files", "test_must_pass", "critical_check"):
        s = aggregate_verification([_skipped(name)], required_check_ids=[])
        assert s.verdict is RunVerdict.ACCEPTED, name
        assert s.required_unmet == ()


def test_only_declared_ids_block():
    """Only the check_ids in required_check_ids drive blocking — nothing else."""
    s = aggregate_verification(
        [_skipped("declared"), _skipped("undeclared")],
        required_check_ids=["declared"],
    )
    assert s.required_unmet == ("declared",)
    assert s.verdict is RunVerdict.BLOCKED_UNVERIFIED


# --------------------------------------------------------------------------- #
# Final-state resolution — the repaired-and-re-run check (§6.5, #379)
# --------------------------------------------------------------------------- #


def test_same_subject_failed_then_passed_supersedes_to_accepted():
    """The #379 core bug: a check that FAILED then re-ran and PASSED (same producing
    task) must resolve to its FINAL state — verdict ``accepted``, not the union that
    would pin ``rejected`` forever. This is the coupled half of #374's re-run-to-green.
    """
    s = aggregate_verification(
        [_failed("tests_pass", subject="task-A"), _passed("tests_pass", subject="task-A")]
    )
    assert s.verdict is RunVerdict.ACCEPTED
    assert s.failed == ()
    assert s.verified == ("tests_pass",)
    assert (s.executed_count, s.passed_count) == (1, 1)


def test_same_subject_passed_then_failed_stays_rejected():
    """Supersession is order-sensitive, not fail-masking: a check that passed then
    regressed (final = FAILED) must stay ``rejected`` — the fix must not swallow a
    real later failure."""
    s = aggregate_verification(
        [_passed("tests_pass", subject="task-A"), _failed("tests_pass", subject="task-A")]
    )
    assert s.verdict is RunVerdict.REJECTED
    assert s.failed == ("tests_pass",)
    assert s.verified == ()


def test_different_subjects_same_check_id_accumulate():
    """Distinct producing tasks emitting the same check_id (``tests_pass`` once per
    develop task) are NOT collapsed: one failing → ``rejected``. Naive last-write-wins
    by bare check_id would wrongly drop the earlier task's real failure."""
    s = aggregate_verification(
        [_failed("tests_pass", subject="task-A"), _passed("tests_pass", subject="task-B")]
    )
    assert s.verdict is RunVerdict.REJECTED
    assert set(s.failed) == {"tests_pass"}
    assert set(s.verified) == {"tests_pass"}
    assert s.executed_count == 2  # both subjects counted, not deduped to one


def test_subjectless_results_are_never_collapsed():
    """``subject=None`` carries no producer identity — each result stays independent
    (the pre-#379 accumulate default), so two un-identified rows for one check_id
    still both count. Guards against silently collapsing legacy/un-subjected producers.
    """
    s = aggregate_verification([_failed("c"), _passed("c")])  # no subject on either
    assert s.verdict is RunVerdict.REJECTED
    assert s.executed_count == 2


def test_required_check_recovers_to_accepted_after_repair():
    """The re-run-to-green case #374 needs: a REQUIRED check that failed then passed
    on re-verification must reach ``accepted`` — the superseded FAILED attempt must
    not leave it stuck ``rejected`` (nor ``blocked_unverified``, since the final state
    IS executed-and-passed)."""
    s = aggregate_verification(
        [_failed("tests_pass", subject="task-A"), _passed("tests_pass", subject="task-A")],
        required_check_ids=["tests_pass"],
    )
    assert s.verdict is RunVerdict.ACCEPTED
    assert s.required_unmet == ()


def test_multiple_failed_attempts_then_pass_all_supersede():
    """Two failed attempts then a pass (same subject) all collapse to the final PASSED
    — bounded correction may retry more than once before converging."""
    s = aggregate_verification(
        [
            _failed("tests_pass", subject="task-A"),
            _failed("tests_pass", subject="task-A"),
            _passed("tests_pass", subject="task-A"),
        ]
    )
    assert s.verdict is RunVerdict.ACCEPTED
    assert (s.executed_count, s.passed_count) == (1, 1)


# --------------------------------------------------------------------------- #
# Drift + purity guards (AC#13)
# --------------------------------------------------------------------------- #


def test_result_status_tokens_match_check_outcome_vocabulary():
    """ResultStatus must stay in lock-step with what CheckOutcome actually emits.

    Bug caught: SIP-0092 renames a status literal and the classifier silently
    starts misclassifying that producer (e.g. a renamed 'passed' → not-executed).
    """
    from squadops.cycles.acceptance_checks import CheckOutcome

    assert CheckOutcome.passed().status == ResultStatus.PASSED
    assert CheckOutcome.failed("x").status == ResultStatus.FAILED
    assert CheckOutcome.skipped("x").status == ResultStatus.SKIPPED
    assert CheckOutcome.error("x").status == ResultStatus.ERROR


def test_module_is_pure_no_io_imports():
    """AC#13: the aggregation module imports no persistence/adapter/dispatch surface.

    Bug caught: someone adds a registry write or event emit inside the choke
    point, breaking the pure-decision-at-a-choke-point contract (§6.2).
    """
    src = Path(vi.__file__).read_text()
    tree = ast.parse(src)
    imported: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported += [n.name for n in node.names]
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.append(node.module)
    forbidden = ("adapters", "asyncpg", "aio_pika", "httpx", "requests")
    offenders = [m for m in imported if any(m == f or m.startswith(f + ".") for f in forbidden)]
    assert offenders == [], f"pure module must not import I/O surfaces: {offenders}"
    # Anything it does import from squadops must not reach into ports/persistence/api.
    squadops_imports = [m for m in imported if m.startswith("squadops.")]
    assert squadops_imports == [], f"pure core should import only stdlib, got {squadops_imports}"


def test_summary_is_frozen():
    """The summary is an immutable value object (references only, no post-hoc mutation)."""
    s = aggregate_verification([_passed("a")])
    with pytest.raises(Exception):
        s.verdict = RunVerdict.REJECTED  # type: ignore[misc]
