"""Tests for the SIP-0096 Phase 2 task-result → CheckResult normalizer.

The load-bearing correctness points: tests_pass is synthesized from the
always-present test_result (the checks[] row is failure-only), the §6.6.1 stub
signal flows onto that synthesized pass, typed-acceptance status passes through
verbatim, and a malformed row is skipped rather than raised. Each test names the
bug it catches.
"""

from __future__ import annotations

import pytest

from squadops.cycles.verification_integrity import (
    EvidenceFamily,
    NotExecutedReason,
    ResultStatus,
    RunVerdict,
    aggregate_verification,
    classify,
)
from squadops.cycles.verification_normalize import (
    CHECK_NO_STUB,
    CHECK_TESTS_PASS,
    normalize_task_checks,
)


def _by_id(results):
    return {r.check_id: r for r in results}


# --------------------------------------------------------------------------- #
# tests_pass synthesis from test_result (the failure-only-row trap)
# --------------------------------------------------------------------------- #


def test_passing_run_synthesizes_tests_pass_even_with_no_checks_row():
    """A green run appends no tests_pass row; synthesis from test_result is the
    only thing that keeps the passing evidence from vanishing (and later falsely
    blocking once tests_pass is required)."""
    out = {"test_result": {"executed": True, "exit_code": 0, "tests_passed": True}}
    r = _by_id(normalize_task_checks(out))
    assert CHECK_TESTS_PASS in r
    assert r[CHECK_TESTS_PASS].status == ResultStatus.PASSED
    assert classify(r[CHECK_TESTS_PASS]) is EvidenceFamily.EXECUTED_PASSED


def test_failed_tests_synthesized_as_failed():
    out = {"test_result": {"executed": True, "exit_code": 1, "tests_passed": False}}
    r = _by_id(normalize_task_checks(out))
    assert r[CHECK_TESTS_PASS].status == ResultStatus.FAILED
    assert r[CHECK_TESTS_PASS].provenance.exit_code == 1


def test_not_executed_tests_are_not_executed_with_mapped_reason():
    out = {"test_result": {"executed": False, "error": "ImportError: no module named app"}}
    r = _by_id(normalize_task_checks(out))
    assert r[CHECK_TESTS_PASS].status == ResultStatus.SKIPPED
    assert r[CHECK_TESTS_PASS].reason == NotExecutedReason.IMPORT_ERROR
    assert classify(r[CHECK_TESTS_PASS]) is EvidenceFamily.NOT_EXECUTED


@pytest.mark.parametrize(
    ("error", "expected"),
    [
        ("ImportError somewhere", NotExecutedReason.IMPORT_ERROR),
        ("bash: pytest: command not found", NotExecutedReason.MISSING_TOOLING),
        ("no module named x", NotExecutedReason.MISSING_TOOLING),
        ("weird runner blowup", NotExecutedReason.SUBJECT_MISSING),
        ("", NotExecutedReason.SUBJECT_MISSING),
    ],
)
def test_not_executed_reason_mapping(error, expected):
    out = {"test_result": {"executed": False, "error": error}}
    assert _by_id(normalize_task_checks(out))[CHECK_TESTS_PASS].reason == expected


def test_tests_passed_falls_back_to_exit_code_when_flag_absent():
    out = {"test_result": {"executed": True, "exit_code": 0}}  # no tests_passed key
    assert _by_id(normalize_task_checks(out))[CHECK_TESTS_PASS].status == ResultStatus.PASSED


# --------------------------------------------------------------------------- #
# Stub cross-signal (§6.6.1)
# --------------------------------------------------------------------------- #


def test_stub_offenders_mark_tests_pass_as_stub_and_record_stub_check():
    """no_stub_fallback_tests failing must (a) record itself as executed-failed and
    (b) flag the synthesized tests_pass as a stub so its green cannot credit."""
    out = {
        "test_result": {"executed": True, "exit_code": 0, "tests_passed": True},
        "validation_result": {
            "checks": [{"check": CHECK_NO_STUB, "offenders": ["test_app.py"], "passed": False}]
        },
    }
    r = _by_id(normalize_task_checks(out))
    assert r[CHECK_NO_STUB].status == ResultStatus.FAILED
    assert r[CHECK_TESTS_PASS].is_stub is True
    # the stub-backed pass is non-creditable
    assert classify(r[CHECK_TESTS_PASS]) is EvidenceFamily.NOT_EXECUTED


def test_no_stub_row_means_tests_pass_credits_normally():
    out = {"test_result": {"executed": True, "exit_code": 0, "tests_passed": True}}
    assert _by_id(normalize_task_checks(out))[CHECK_TESTS_PASS].is_stub is False


def test_failure_only_tests_pass_row_is_not_double_recorded():
    """The handler's failure-only tests_pass row must not produce a second
    CheckResult alongside the synthesized one."""
    out = {
        "test_result": {"executed": True, "exit_code": 1, "tests_passed": False},
        "validation_result": {
            "checks": [
                {"check": CHECK_TESTS_PASS, "executed": True, "exit_code": 1, "passed": False}
            ]
        },
    }
    tests_pass_results = [r for r in normalize_task_checks(out) if r.check_id == CHECK_TESTS_PASS]
    assert len(tests_pass_results) == 1


# --------------------------------------------------------------------------- #
# Typed-acceptance rows (status passthrough)
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("status", ["passed", "failed", "skipped", "error"])
def test_typed_acceptance_status_passes_through(status):
    out = {
        "validation_result": {
            "checks": [
                {"check": "acceptance:file_exists", "status": status, "reason": "r", "passed": True}
            ]
        }
    }
    r = _by_id(normalize_task_checks(out))
    assert r["acceptance:file_exists"].status == status


def test_typed_skipped_carries_reason_for_disclosure():
    out = {
        "validation_result": {
            "checks": [
                {"check": "acceptance:x", "status": "skipped", "reason": "unsupported_stack"}
            ]
        }
    }
    r = _by_id(normalize_task_checks(out))
    assert r["acceptance:x"].reason == "unsupported_stack"
    assert classify(r["acceptance:x"]) is EvidenceFamily.NOT_EXECUTED


def test_generic_passed_row_without_status():
    out = {"validation_result": {"checks": [{"check": "non_stub_files", "passed": True}]}}
    assert _by_id(normalize_task_checks(out))["non_stub_files"].status == ResultStatus.PASSED


def test_generic_row_executed_false_is_not_executed():
    out = {
        "validation_result": {"checks": [{"check": "custom", "executed": False, "passed": False}]}
    }
    assert _by_id(normalize_task_checks(out))["custom"].status == ResultStatus.SKIPPED


# --------------------------------------------------------------------------- #
# Robustness — must never raise in the executor hot path
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "out",
    [
        {},
        {"test_result": None, "validation_result": None},
        {"validation_result": {"checks": None}},
        {"validation_result": {"checks": ["not-a-dict", 42, {}]}},  # bad rows skipped
        {"validation_result": {"checks": [{"no_check_key": 1}]}},
        {"validation_result": "not-a-mapping"},
    ],
)
def test_malformed_outputs_never_raise(out):
    assert normalize_task_checks(out) == [] or isinstance(normalize_task_checks(out), list)


def test_non_verification_task_yields_nothing():
    """A strategy/governance task with no test_result or validation_result records
    no evidence (empty), so aggregation is unaffected by it."""
    assert normalize_task_checks({"artifacts": [{"filename": "prd.md"}]}) == []


# --------------------------------------------------------------------------- #
# End-to-end: normalize → aggregate (the point of the wiring)
# --------------------------------------------------------------------------- #


def test_stub_pass_on_required_tests_blocks_end_to_end():
    """The whole reason for the stub signal: a green-but-stubbed qa run, with
    tests_pass required, must aggregate to blocked_unverified — not accepted."""
    out = {
        "test_result": {"executed": True, "exit_code": 0, "tests_passed": True},
        "validation_result": {
            "checks": [{"check": CHECK_NO_STUB, "offenders": ["t.py"], "passed": False}]
        },
    }
    summary = aggregate_verification(
        normalize_task_checks(out), required_check_ids=[CHECK_TESTS_PASS]
    )
    assert summary.verdict is RunVerdict.BLOCKED_UNVERIFIED
    assert CHECK_TESTS_PASS in summary.required_unmet


def test_clean_pass_aggregates_accepted():
    out = {
        "test_result": {"executed": True, "exit_code": 0, "tests_passed": True},
        "validation_result": {
            "checks": [{"check": "acceptance:file_exists", "status": "passed", "passed": True}]
        },
    }
    summary = aggregate_verification(
        normalize_task_checks(out), required_check_ids=[CHECK_TESTS_PASS]
    )
    assert summary.verdict is RunVerdict.ACCEPTED
    assert CHECK_TESTS_PASS in summary.verified
