"""The recovery diagnostics' verdicts (#1803): each reads a record field, and each fails on the
shape it exists to catch. The decision shapes are the ones a live campaign wrote
(``cmp_9757603322b1``): a healthy increment cycle has two ``decide`` rows, its end heard into
``evaluating`` and its continuation out of it."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

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


#: An increment cycle decided as cmp_9757603322b1's seq 12–14 were.
_DECIDED = [
    _row(12, "decide", prior="building", nxt="evaluating", target="cyc_1"),
    _row(13, "decide", prior="evaluating", nxt="at_proposal", target="cyc_1", launch="lnc_a"),
    _row(
        14, "mark_launched", prior="at_proposal", nxt="at_proposal", target="lnc_a", launch="lnc_a"
    ),
]


def test_a_restart_that_loses_a_row_or_resumes_elsewhere_fails():
    """Bug caught: a ruling lost across a restart (§12a: a ruling is committed before it is
    acknowledged), or a campaign that comes back in a state its log never committed."""
    before = [_row(1, "submit", nxt="awaiting_ruling"), _row(2, "rule", prior="awaiting_ruling")]

    kept = diag.restart_kept_the_log(
        "restart-at-gate", before, [*before, _row(3, "lease_acquire")], "building"
    )
    lost = diag.restart_kept_the_log("restart-at-gate", before, before[:1], "building")
    elsewhere = diag.restart_kept_the_log(
        "restart-at-gate", before, [*before, _row(3, "decide", prior="at_proposal")], "building"
    )
    stale = diag.restart_kept_the_log("restart-at-gate", before, before, "awaiting_ruling")

    assert (kept.passed, lost.passed) == (True, False)
    assert "a ruling was lost" in lost.failures
    assert elsewhere.failures == ["resumed from at_proposal, not the last committed building"]
    assert stale.failures == ["the campaign is awaiting_ruling, not the last committed building"]


def test_a_healthy_decision_passes_and_a_cycle_heard_twice_fails():
    """Bug caught: the startup re-hearing deciding a cycle the completion hook already decided,
    which launches a second cycle. The healthy shape is two decide rows: the first verdict
    written read it as a double decision and would have failed every live increment."""
    reheard = [
        *_DECIDED,
        _row(15, "decide", prior="evaluating", nxt="at_proposal", target="cyc_1", launch="lnc_b"),
    ]

    assert diag.decided_once(_DECIDED, {"lnc_a": 1}) == []
    assert diag.decided_once(reheard, {"lnc_a": 1, "lnc_b": 1}) == [
        "cyc_1: the decision from evaluating taken 2 times",
        "cyc_1: 2 continuation decisions",
    ]
    assert diag.decided_once(_DECIDED, {"lnc_a": 2}) == ["lnc_a: launched as 2 cycles"]


def test_the_re_heard_cycle_needs_its_one_continuation_launched_once():
    """Bug caught: a restart between the decision and the launch that loses the launch (the
    intent never becomes a cycle), or a re-hearing that stops before the continuation."""
    healthy = diag.duplicate_completion_verdict(_DECIDED, "cyc_1", {"lnc_a": 1})
    unlaunched = diag.duplicate_completion_verdict(_DECIDED, "cyc_1", {})
    undecided = diag.duplicate_completion_verdict(_DECIDED[:1], "cyc_1", {})

    assert healthy.passed is True
    assert unlaunched.failures == ["lnc_a: launched as 0 cycles, not 1"]
    assert undecided.failures == ["0 continuation decisions for cyc_1, not 1"]


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


def test_an_identity_moved_without_a_promote_row_or_a_missed_window_fails():
    """Bug caught: an interrupted promotion that left a new accepted identity with no promotion
    transition (§12a); and a kill that landed after the promotion committed, read as a pass."""
    assert diag.no_partial_promotion_verdict("sha-a", "sha-a", [], True).passed is True
    assert diag.no_partial_promotion_verdict("sha-a", "sha-b", [_row(4, "promote")], True).passed
    assert diag.no_partial_promotion_verdict("sha-a", "sha-b", [], True).failures == [
        "the accepted identity changed with no promote row"
    ]
    assert diag.no_partial_promotion_verdict("sha-a", "sha-a", [], False).failures == [
        "the promotion committed before the kill: the window was not hit"
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


@pytest.mark.parametrize(
    "spec", ["restart-pasued", "restart-at:awaiting-ruling", "restart-at:completed"]
)
def test_a_mistyped_sequence_is_refused_before_the_first_injection(spec, monkeypatch):
    """Bug caught: a typo found only when the sequence reaches it, after earlier diagnostics
    restarted the runtime mid-campaign; or a state no campaign restarts in, waited on for
    hours."""
    monkeypatch.setattr(diag, "restart_runtime", lambda: pytest.fail("injected"))
    monkeypatch.setattr(diag, "campaign_state", lambda _c: pytest.fail("read the deploy"))

    with pytest.raises(SystemExit) as exit_:
        diag.main(["cmp_abc", "restart-at:building", spec])

    assert exit_.value.code == 2
