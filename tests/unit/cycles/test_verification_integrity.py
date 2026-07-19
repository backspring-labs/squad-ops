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
    CycleOutcome,
    EvidenceFamily,
    NotExecutedReason,
    ResultStatus,
    RunVerdict,
    RunVerificationSummary,
    UnverifiedCheck,
    WaivedCheck,
    aggregate_cycle_outcome,
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


# --------------------------------------------------------------------------- #
# Phase 3 slice 1 — aggregate_cycle_outcome (the durable per-cycle roll-up, §10)
# --------------------------------------------------------------------------- #


def _run_summary(
    verdict, *, verified=(), failed=(), unverified=(), required_unmet=()
) -> RunVerificationSummary:
    return RunVerificationSummary(
        verdict=verdict,
        verified=tuple(verified),
        failed=tuple(failed),
        unverified=tuple(unverified),
        required_unmet=tuple(required_unmet),
        executed_count=len(verified) + len(failed),
        passed_count=len(verified),
    )


@pytest.mark.parametrize(
    ("run_verdicts", "expected"),
    [
        ([RunVerdict.ACCEPTED, RunVerdict.ACCEPTED], RunVerdict.ACCEPTED),
        ([RunVerdict.ACCEPTED, RunVerdict.REJECTED], RunVerdict.REJECTED),
        # blocked wins over rejected — the incomplete-evidence signal is never
        # hidden behind a product failure (§6.2 precedence, at cycle scope).
        ([RunVerdict.REJECTED, RunVerdict.BLOCKED_UNVERIFIED], RunVerdict.BLOCKED_UNVERIFIED),
        ([RunVerdict.ACCEPTED, RunVerdict.BLOCKED_UNVERIFIED], RunVerdict.BLOCKED_UNVERIFIED),
    ],
)
def test_cycle_verdict_is_worst_of_runs(run_verdicts, expected):
    """Cycle verdict = worst per-run verdict; reordering precedence would regress this."""
    outcome = aggregate_cycle_outcome([_run_summary(v) for v in run_verdicts])
    assert outcome.verdict is expected
    assert outcome.run_count == len(run_verdicts)


def test_empty_cycle_rolls_up_to_accepted():
    """Zero runs = zero adverse evidence → accepted, run_count 0 (inert default)."""
    outcome = aggregate_cycle_outcome([])
    assert outcome.verdict is RunVerdict.ACCEPTED
    assert outcome.run_count == 0
    assert outcome.verified == () and outcome.failed == () and outcome.unverified == ()


def test_evidence_unions_across_runs_deduped():
    """Every run's verified/failed/unverified is disclosed at cycle scope, deduped."""
    r1 = _run_summary(RunVerdict.ACCEPTED, verified=["tests_pass", "shared"])
    r2 = _run_summary(RunVerdict.REJECTED, verified=["shared"], failed=["frontend_build"])
    outcome = aggregate_cycle_outcome([r1, r2])
    assert outcome.verified == ("tests_pass", "shared")  # 'shared' collapsed to one
    assert outcome.failed == ("frontend_build",)
    assert outcome.verdict is RunVerdict.REJECTED


def test_check_failed_in_one_run_passed_in_another_disclosed_in_both():
    """Runs are distinct evidence contexts — a check that failed once and passed once
    is honestly in BOTH lists; the roll-up must not collapse cross-run outcomes."""
    r1 = _run_summary(RunVerdict.REJECTED, failed=["tests_pass"])
    r2 = _run_summary(RunVerdict.ACCEPTED, verified=["tests_pass"])
    outcome = aggregate_cycle_outcome([r1, r2])
    assert "tests_pass" in outcome.failed
    assert "tests_pass" in outcome.verified


def test_required_unmet_derived_from_unverified_disclosure():
    """cycle.required_unmet is derived from the unverified records, so the required
    set and its disclosure can never drift apart (roll-up integrity, violation #3)."""
    unmet = UnverifiedCheck(
        check_id="required_files", reason=NotExecutedReason.SUBJECT_MISSING, required=True
    )
    optional = UnverifiedCheck(
        check_id="opt", reason=NotExecutedReason.CONFIG_DISABLED, required=False
    )
    outcome = aggregate_cycle_outcome(
        [_run_summary(RunVerdict.BLOCKED_UNVERIFIED, unverified=[unmet, optional])]
    )
    assert outcome.required_unmet == ("required_files",)  # only the required one
    assert {u.check_id for u in outcome.unverified} == {"required_files", "opt"}  # both disclosed


def test_waiver_recorded_but_never_alters_verdict():
    """A waiver sits beside the evidence and does not flip a blocked verdict (§6.5):
    the result stands un-loosened; the operator decision is recorded above it."""
    waiver = WaivedCheck(
        check_id="required_files", reason="known-good manual build", waived_by="op"
    )
    unmet = UnverifiedCheck(
        check_id="required_files", reason=NotExecutedReason.SUBJECT_MISSING, required=True
    )
    outcome = aggregate_cycle_outcome(
        [_run_summary(RunVerdict.BLOCKED_UNVERIFIED, unverified=[unmet])], waived=[waiver]
    )
    assert outcome.verdict is RunVerdict.BLOCKED_UNVERIFIED  # unaltered by the waiver
    assert outcome.waived == (waiver,)


def test_cycle_outcome_is_frozen():
    """The roll-up is an immutable value object — no post-hoc mutation of the verdict."""
    outcome = aggregate_cycle_outcome([_run_summary(RunVerdict.ACCEPTED)])
    assert isinstance(outcome, CycleOutcome)
    with pytest.raises(Exception):
        outcome.verdict = RunVerdict.REJECTED  # type: ignore[misc]


# --------------------------------------------------------------------------- #
# #444 — per-check reconciliation (§10 amendment)
# --------------------------------------------------------------------------- #


def _subject_missing(check_id: str, *, required: bool = True) -> UnverifiedCheck:
    return UnverifiedCheck(
        check_id=check_id, reason=NotExecutedReason.SUBJECT_MISSING, required=required
    )


class TestCycleOutcomeReconciliation:
    """A framing run's subject_missing rows must not veto later real evidence —
    the cyc_17bdc66c1669 contradiction (required_files simultaneously verified
    and required_unmet; cycle blocked while run 2's honest verdict was rejected)."""

    def test_attempt_35_reproduction_rejected_not_blocked(self):
        framing = _run_summary(
            RunVerdict.BLOCKED_UNVERIFIED,
            unverified=[
                _subject_missing("frontend_build"),
                _subject_missing("required_files"),
                _subject_missing("tests_pass"),
            ],
        )
        impl = _run_summary(
            RunVerdict.REJECTED,
            verified=["required_files", "non_stub_files"],
            failed=["frontend_build", "tests_pass"],
        )
        outcome = aggregate_cycle_outcome([framing, impl])
        assert outcome.verdict is RunVerdict.REJECTED
        assert outcome.required_unmet == ()  # everything required was executed
        assert "required_files" in outcome.verified
        assert {u.check_id for u in outcome.unverified} == set()

    def test_fully_verified_impl_after_blocked_framing_accepted(self):
        framing = _run_summary(
            RunVerdict.BLOCKED_UNVERIFIED,
            unverified=[_subject_missing("frontend_build"), _subject_missing("tests_pass")],
        )
        impl = _run_summary(
            RunVerdict.ACCEPTED, verified=["frontend_build", "tests_pass", "required_files"]
        )
        outcome = aggregate_cycle_outcome([framing, impl])
        assert outcome.verdict is RunVerdict.ACCEPTED
        assert outcome.required_unmet == ()
        assert outcome.unverified == ()

    def test_never_executed_required_check_still_blocks(self):
        framing = _run_summary(
            RunVerdict.BLOCKED_UNVERIFIED, unverified=[_subject_missing("tests_pass")]
        )
        impl = _run_summary(RunVerdict.ACCEPTED, verified=["frontend_build"])
        outcome = aggregate_cycle_outcome([framing, impl])
        assert outcome.verdict is RunVerdict.BLOCKED_UNVERIFIED
        assert outcome.required_unmet == ("tests_pass",)

    def test_later_execution_supersedes_earlier_failure(self):
        r1 = _run_summary(RunVerdict.REJECTED, failed=["tests_pass"])
        r2 = _run_summary(RunVerdict.ACCEPTED, verified=["tests_pass"])
        outcome = aggregate_cycle_outcome([r1, r2])
        assert outcome.verdict is RunVerdict.ACCEPTED
        # disclosure keeps both sides of the story
        assert "tests_pass" in outcome.failed and "tests_pass" in outcome.verified

    def test_opaque_blocked_run_still_blocks_cycle(self):
        """#388 abort: adverse verdict with no evidence rows cannot be reconciled away."""
        aborted = _run_summary(RunVerdict.BLOCKED_UNVERIFIED)  # no unverified rows
        impl = _run_summary(RunVerdict.ACCEPTED, verified=["frontend_build"])
        outcome = aggregate_cycle_outcome([aborted, impl])
        assert outcome.verdict is RunVerdict.BLOCKED_UNVERIFIED

    def test_executed_failure_never_superseded_by_non_evidence(self):
        r1 = _run_summary(RunVerdict.REJECTED, failed=["frontend_build"])
        r2 = _run_summary(
            RunVerdict.BLOCKED_UNVERIFIED, unverified=[_subject_missing("frontend_build")]
        )
        outcome = aggregate_cycle_outcome([r1, r2])
        assert outcome.verdict is RunVerdict.REJECTED
        assert outcome.required_unmet == ()


# ---------------------------------------------------------------------------
# SIP-0098 98.4: contract-criterion coverage accounting
# ---------------------------------------------------------------------------


class TestContractCriteriaCoverage:
    def test_run_coverage_counts_passed_criteria(self):
        results = [
            _passed("acceptance:import_present", criterion_id="vc-a", subject="t1"),
            _passed("acceptance:endpoint_defined", criterion_id="vc-b", subject="t1"),
            _failed("vc-probe-x", criterion_id="vc-probe-x", subject="t2"),
        ]
        s = aggregate_verification(results)
        assert s.criteria_verified == ("vc-a", "vc-b")
        assert s.criteria_total == ("vc-a", "vc-b", "vc-probe-x")
        assert s.criteria_coverage == (2, 3)

    def test_checks_without_criterion_id_are_excluded(self):
        # author-mode / framework checks carry no criterion_id -> zero coverage
        s = aggregate_verification([_passed("tests_pass", subject="t")])
        assert s.criteria_coverage == (0, 0)
        assert s.criteria_total == ()

    def test_adverse_criterion_never_credited_within_a_run(self):
        # a criterion with any adverse result in the run is not credited (adverse wins)
        results = [
            _failed("vc-x", criterion_id="vc-x", subject="t1"),
            _passed("vc-x", criterion_id="vc-x", subject="t2"),
        ]
        s = aggregate_verification(results)
        assert s.criteria_verified == ()
        assert s.criteria_total == ("vc-x",)

    def test_skipped_criterion_is_counted_but_uncredited(self):
        s = aggregate_verification([_skipped("vc-p", criterion_id="vc-p", subject="t")])
        assert s.criteria_verified == ()
        assert s.criteria_total == ("vc-p",)

    def test_cycle_union_credits_criterion_verified_in_any_run(self):
        # a probe that failed in run 1 and passed in run 2 is verified at cycle scope
        run1 = aggregate_verification([_failed("vc-p", criterion_id="vc-p", subject="t")])
        run2 = aggregate_verification([_passed("vc-p", criterion_id="vc-p", subject="t")])
        outcome = aggregate_cycle_outcome([run1, run2])
        assert outcome.criteria_verified == ("vc-p",)
        assert outcome.criteria_total == ("vc-p",)
        assert outcome.criteria_coverage == (1, 1)


# --------------------------------------------------------------------------- #
# failed_detail (#500) — bug caught: a failed contract probe's reason died at
# aggregation (failed = bare names), so evidence couldn't say WHY vc-probe-runs
# failed and diagnosis required manually re-running the probe.
# --------------------------------------------------------------------------- #


def test_aggregate_carries_failed_reasons_in_failed_detail():
    s = aggregate_verification(
        [_passed("a"), _failed("vc-probe-runs", reason="status 422 != expected 200")],
        required_check_ids=["vc-probe-runs"],
    )
    assert s.failed == ("vc-probe-runs",)
    assert len(s.failed_detail) == 1
    d = s.failed_detail[0]
    assert d.check_id == "vc-probe-runs"
    assert d.reason == "status 422 != expected 200"
    assert d.required is True


def test_aggregate_failed_without_reason_yields_empty_string_not_crash():
    s = aggregate_verification([_failed("b")])
    assert s.failed_detail[0].reason == ""
    assert s.failed_detail[0].required is False


# --------------------------------------------------------------------------- #
# contract_criteria denominator (#508) — bug caught: a bound contract with 6
# criteria whose run died after dispatching checks for only 3 reported coverage
# 2/3 instead of 2/6 (criteria_total derived from evidence, not the contract),
# overstating coverage exactly when the run failed early.
# --------------------------------------------------------------------------- #


def test_bound_contract_supplies_full_denominator():
    contract_ids = ["vc-a", "vc-b", "vc-frontend", "vc-suite", "vc-probes", "vc-c"]
    s = aggregate_verification(
        [
            _passed("acceptance:import_present", criterion_id="vc-a"),
            _passed("acceptance:command_exit_zero", criterion_id="vc-b"),
            _failed("acceptance:endpoint_defined", criterion_id="vc-c"),
        ],
        contract_criteria=contract_ids,
    )
    assert s.criteria_verified == ("vc-a", "vc-b")
    assert s.criteria_total == tuple(sorted(contract_ids))
    assert s.criteria_coverage == (2, 6)


def test_no_contract_keeps_evidence_derived_denominator():
    s = aggregate_verification(
        [
            _passed("x", criterion_id="vc-a"),
            _failed("y", criterion_id="vc-b"),
        ]
    )
    assert s.criteria_total == ("vc-a", "vc-b")
    assert s.criteria_coverage == (1, 2)


def test_evidence_outside_contract_still_counted_in_denominator():
    # A criterion id on a check row that the contract does not declare must not
    # vanish from the totals — unexpected evidence is disclosed, never dropped.
    s = aggregate_verification(
        [_passed("x", criterion_id="vc-rogue")],
        contract_criteria=["vc-a", "vc-b"],
    )
    assert s.criteria_total == ("vc-a", "vc-b", "vc-rogue")
    assert s.criteria_verified == ("vc-rogue",)


def test_bound_contract_with_zero_evidence_reports_zero_of_m():
    # Run died before any criterion-bound check dispatched: coverage must read
    # 0/m against the contract, not 0/0.
    s = aggregate_verification([_passed("framework_check")], contract_criteria=["vc-a", "vc-b"])
    assert s.criteria_verified == ()
    assert s.criteria_total == ("vc-a", "vc-b")
    assert s.criteria_coverage == (0, 2)
