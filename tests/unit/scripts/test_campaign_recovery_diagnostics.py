"""The recovery diagnostics' verdicts (#1803): each reads a record field, and each fails on the
shape it exists to catch."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

_SPEC = importlib.util.spec_from_file_location(
    "campaign_recovery_diagnostics",
    Path(__file__).resolve().parents[3] / "scripts" / "dev" / "campaign_recovery_diagnostics.py",
)
diag = importlib.util.module_from_spec(_SPEC)
sys.modules["campaign_recovery_diagnostics"] = diag  # dataclasses resolve annotations via it
_SPEC.loader.exec_module(diag)
Row = diag.Row


def _row(
    seq, op, outcome="applied", prior="building", nxt="building", target="", key=None, launch=""
):
    return Row(seq, op, outcome, prior, nxt, target, key or f"k{seq}", launch)


def test_a_restart_that_loses_or_changes_a_row_fails():
    """Bug caught: a ruling lost across a restart (§12a: a ruling is committed before it is
    acknowledged), read as a pass because the state still looks plausible."""
    before = [_row(1, "submit", nxt="awaiting_ruling"), _row(2, "rule", prior="awaiting_ruling")]

    kept = diag.restart_kept_the_log("restart-at-gate", before, [*before, _row(3, "lease_acquire")])
    lost = diag.restart_kept_the_log("restart-at-gate", before, before[:1])

    assert (kept.passed, lost.passed) == (True, False)
    assert "a ruling was lost" in lost.failures


def test_a_repeated_ruling_is_one_row_and_its_conflict_one_refusal():
    """Bug caught: a repeat that writes a second ruling (two builds for one proposal), or a
    conflicting key applied instead of refused."""
    replayed = [_row(5, "rule", key="K"), _row(6, "rule", outcome="refused", key="K")]
    doubled = [_row(5, "rule", key="K"), _row(6, "rule", key="K")]

    assert diag.repeated_ruling_verdict(replayed, "K").passed is True
    assert diag.repeated_ruling_verdict(doubled, "K").failures == [
        "2 applied rows for the key, not 1",
        "0 refused rows for the conflicting key, not 1",
    ]


def test_a_cycle_heard_twice_decides_once():
    """Bug caught: the startup re-hearing deciding a cycle the completion hook already decided,
    which launches a second cycle."""
    once = [_row(9, "decide", prior="evaluating", nxt="repairing", target="cyc_1", launch="lnc_a")]
    twice = [
        *once,
        _row(11, "decide", prior="repairing", nxt="repairing", target="cyc_1"),
        _row(12, "decide", prior="evaluating", nxt="repairing", target="cyc_1", launch="lnc_b"),
    ]

    assert diag.one_decision_verdict(once, "cyc_1").passed is True
    assert diag.one_decision_verdict(twice, "cyc_1").passed is False


def test_an_identity_moved_without_a_promote_row_is_a_partial_promotion():
    """Bug caught: an interrupted evaluation that left a new accepted identity with no promotion
    transition recording its bundles (§12a)."""
    assert diag.no_partial_promotion_verdict("sha-a", "sha-a", []).passed is True
    assert diag.no_partial_promotion_verdict("sha-a", "sha-b", [_row(4, "promote")]).passed is True
    assert diag.no_partial_promotion_verdict("sha-a", "sha-b", []).failures == [
        "the accepted identity changed with no promote row"
    ]


def test_an_abort_followed_by_a_launch_fails():
    """Bug caught: a continuation after an abort, or an abort that left its cycle running."""
    aborted = [_row(7, "abort", prior="building", nxt="completed")]
    leaked = [*aborted, _row(8, "mark_launched", launch="lnc_c")]

    assert diag.abort_verdict(aborted, "completed", 1).passed is True
    assert diag.abort_verdict(leaked, "completed", 0).failures == [
        "1 launch intent(s) after the abort",
        "no run was cancelled",
    ]
