"""Tests for the run-report quality-notes narrative-override guard (SIP-0096 §6.6.4).

Bug caught: a run that reaches terminal COMPLETED while its verification verdict
is rejected/blocked_unverified must NOT render "All tasks completed
successfully" — the narrative cannot override the structured verdict (the
false-green shown live in #376).
"""

from __future__ import annotations

import pytest

from squadops.cycles.run_report_builder import _build_report_quality_lines
from squadops.cycles.verification_integrity import (
    CheckResult,
    ResultStatus,
    aggregate_verification,
)


def _notes(terminal_status, results=(), required=()):
    summary = aggregate_verification(list(results), required) if results or required else None
    return "\n".join(_build_report_quality_lines(terminal_status, summary))


def test_completed_and_accepted_still_says_success():
    text = _notes("COMPLETED", [CheckResult(check_id="a", status=ResultStatus.PASSED)])
    assert "All tasks completed successfully." in text


def test_completed_but_rejected_does_not_claim_success():
    text = _notes("COMPLETED", [CheckResult(check_id="a", status=ResultStatus.FAILED)])
    assert "All tasks completed successfully." not in text
    assert "REJECTED" in text


def test_completed_but_blocked_unverified_does_not_claim_success():
    text = _notes(
        "COMPLETED",
        [CheckResult(check_id="a", status=ResultStatus.SKIPPED, reason="missing_tooling")],
        required=["a"],
    )
    assert "All tasks completed successfully." not in text
    assert "BLOCKED_UNVERIFIED" in text


def test_completed_with_no_summary_uses_default_narrative():
    """Back-compat: without a verification summary (pre-wire callers), the old
    narrative stands."""
    assert "All tasks completed successfully." in _notes("COMPLETED")


def test_status_compare_is_case_robust():
    """The status compare is sourced from RunStatus and normalized, so a lowercase
    RunStatus value ('completed') can't silently miss the branch (#377 footgun)."""
    text = _notes("completed", [CheckResult(check_id="a", status=ResultStatus.FAILED)])
    assert "REJECTED" in text
    assert "All tasks completed successfully." not in text


@pytest.mark.parametrize(
    ("status", "expected"),
    [
        ("FAILED", "One or more tasks failed"),
        ("CANCELLED", "Run was cancelled"),
    ],
)
def test_non_completed_statuses_unchanged(status, expected):
    # a rejected verdict must not mask the real terminal reason on non-COMPLETED runs
    text = _notes(status, [CheckResult(check_id="a", status=ResultStatus.FAILED)])
    assert expected in text
