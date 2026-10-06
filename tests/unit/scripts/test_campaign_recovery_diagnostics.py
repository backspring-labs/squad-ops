"""The recovery diagnostics' verdicts (#1803): each reads a record field, and each fails on the
shape it exists to catch. The decision shapes are the ones a live campaign wrote
(``cmp_9757603322b1``): a healthy increment cycle has two ``decide`` rows, its end heard into
``evaluating`` and its continuation out of it."""

from __future__ import annotations

import importlib.util
import subprocess
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


def test_every_cli_call_logs_in_first(monkeypatch):
    """Bug caught: the 2026-10-03 increment legs, whose CLI session expired 45 minutes into a
    wait. A ruling, a pause or an abort made on it fails, and ``restart-paused`` then waits on a
    pause that never lands, which stops the sequence."""
    calls = []
    monkeypatch.setattr(diag, "login", lambda cli: calls.append(("login", cli)))
    monkeypatch.setattr(
        diag.subprocess,
        "run",
        lambda cmd, **kw: calls.append(("run", cmd[1:3])) or subprocess.CompletedProcess(cmd, 0),
    )

    diag.squadops("campaigns", "pause", "cmp_abc")

    assert calls == [("login", str(diag.SQUADOPS)), ("run", ["campaigns", "pause"])]


def test_the_kill_reads_the_records_while_the_process_is_down(monkeypatch):
    """Bug caught: the first live run read what was committed at the kill after the restart and
    its settle, and so counted the restarted process's own promotion as committed before the
    kill. A window it had hit was recorded as missed (2026-10-03, ``cmp_e39d5b9c24c6``)."""
    events: list[str] = []
    monkeypatch.setattr(
        diag.subprocess, "run", lambda cmd, **kw: events.append(" ".join(cmd[:2])) or None
    )
    monkeypatch.setattr(diag, "_healthy", lambda: events.append("healthy"))

    _since, read = diag.kill_runtime(lambda: events.append("read") or "rows at the kill")

    assert events == ["docker kill", "read", "docker start", "healthy"]
    assert read == "rows at the kill"


# ---- 2.1 rebuild 1: #1934, #2007 and #2042, read live --------------------------------------

#: A runtime line as the 2.0.1 deploy prints it, and the agent's replay line as #1929 writes it.
_DISPATCH = (
    "2026-10-05 00:22:12,601 INFO adapters.cycles.task_dispatcher: Dispatched task {id} "
    "({type}) to nat_comms, awaiting reply on nat_replies\n"
)
_REPLAY = (
    "2026-10-05 00:31:02,410 WARNING squadops.agents.entrypoint: task_reply_replayed: task={id} "
    "— finished here for an earlier runtime boot; a restarted runtime asked again, so it is "
    "answered with the reply sent, not run twice (#1929)\n"
)
_PROPOSAL = "task-run_c0de7fb7-000-strategy.propose_increment"


def test_the_logs_are_read_for_the_task_type_and_the_replays_they_name():
    """Bug caught: a parser that reads every dispatch as the proposal's, or none of them, so
    #1934's comparison is made on the wrong ids or on nothing."""
    log = _DISPATCH.format(
        id="task-run_c0de7fb7-001-development.design_plan", type="development.design_plan"
    ) + _DISPATCH.format(id=_PROPOSAL, type="strategy.propose_increment")

    assert diag.dispatched(log, "strategy.propose_increment") == [_PROPOSAL]
    assert diag.replayed(_REPLAY.format(id=_PROPOSAL) + "INFO unrelated\n") == [_PROPOSAL]
    assert diag.dispatched("INFO nothing dispatched\n", "strategy.propose_increment") == []


@pytest.mark.parametrize(
    ("before", "after", "from_store", "failures"),
    [
        ([_PROPOSAL], [_PROPOSAL], [_PROPOSAL], []),
        # Rebuild 18's shape: the re-attach minted a new id, so the proposer ran it again.
        (
            ["68de55e6f36b"],
            ["532815c18eb5"],
            [],
            ["re-dispatched as 532815c18eb5, an id the proposer was never sent"],
        ),
        (
            [_PROPOSAL],
            [_PROPOSAL],
            [],
            [f"{_PROPOSAL}: the proposer did not answer the copy from its stored reply"],
        ),
        (
            [],
            [_PROPOSAL],
            [],
            ["no proposal task was dispatched before the restart, so the window was missed"],
        ),
        ([_PROPOSAL], [], [], ["the re-attach dispatched no proposal task"]),
    ],
    ids=[
        "same-id-answered-from-store",
        "rebuild-18-new-id",
        "same-id-run-again",
        "window-missed",
        "never-redispatched",
    ],
)
def test_the_proposal_is_asked_for_by_its_id_and_answered_once(before, after, from_store, failures):
    """#1934: a window the restart missed fails rather than passing on nothing."""
    assert diag.proposal_answered_once(before, after, from_store) == failures


def _runs(*rows):
    return [("cyc_1", run, "implementation", status) for run, status in rows]


@pytest.mark.parametrize(
    ("runs", "open_by_run", "failures"),
    [
        (_runs(("run_a", "completed"), ("run_b", "running")), {"run_b": ["fr_new"]}, []),
        # The 2.0 diagnostics' shape: an ended run beside the dead process's flow run.
        (
            _runs(("run_a", "completed")),
            {"run_a": ["fr_dead"]},
            ["run_a is completed and 1 flow run(s) of it are open: ['fr_dead']"],
        ),
        (
            _runs(("run_b", "running")),
            {"run_b": ["fr_dead", "fr_new"]},
            ["run_b is running and 2 flow runs of it are open: ['fr_dead', 'fr_new']"],
        ),
        (
            _runs(("run_a", "completed")),
            None,
            ["Prefect could not be read, so the open flow runs are unread"],
        ),
    ],
    ids=["clean", "ended-run-left-open", "re-attach-kept-the-dead-one", "prefect-unread"],
)
def test_no_flow_run_outlives_its_run(runs, open_by_run, failures):
    """#2007. Bug caught: a Prefect outage read as "none open", which is the tracker's own
    answer to a transport failure."""
    assert diag.flow_runs_left_open(runs, open_by_run) == failures


@pytest.mark.parametrize(
    ("successor", "queued_after", "starts", "at_position", "failures"),
    [
        ("run_f", True, 1, 1, []),
        ("run_f", True, 0, 1, ["run_f was never started after the restart: the cycle is stranded"]),
        (
            "run_f",
            True,
            2,
            2,
            ["run_f was started 2 times after the restart", "2 runs hold the successor's position"],
        ),
        (
            "run_f",
            False,
            1,
            1,
            ["run_f was not still queued after the restart, so the restart did not hold it"],
        ),
        (
            None,
            False,
            0,
            0,
            ["no successor was queued when the runtime went down, so the window was missed"],
        ),
    ],
    ids=["started-once", "stranded-2042", "started-twice", "not-held", "window-missed"],
)
def test_a_queued_successor_is_started_once_after_the_restart(
    successor, queued_after, starts, at_position, failures
):
    assert diag.queued_successor_verdict(successor, queued_after, starts, at_position) == failures


def test_the_foreign_model_is_unloaded_when_the_diagnostic_fails_inside(monkeypatch):
    """Bug caught: a diagnostic that times out waiting with the model resident leaves the box
    not quiet, so every launch after it is refused."""
    kept: list[object] = []
    monkeypatch.setattr(diag, "_ollama_keep", lambda model, keep: kept.append(keep))
    monkeypatch.setattr(diag, "_available_gb", lambda: 100)

    with pytest.raises(SystemExit), diag.box_held_by("llama3.1:8b"):
        raise SystemExit("timed out waiting for the successor")

    assert kept == ["2h", 0]


def test_every_record_reads_the_flow_runs_its_campaign_left_open(monkeypatch, tmp_path):
    """Wiring, entered at ``_record``, which every diagnostic's verdict goes through: a verdict
    that passed on its own fails when an ended run's flow run is still open."""
    monkeypatch.setattr(diag, "REPO", tmp_path)
    monkeypatch.setattr(diag, "runs_of", lambda _c: _runs(("run_a", "completed")))
    monkeypatch.setattr(diag, "open_flow_runs", lambda runs: {"run_a": ["fr_dead"]})
    monkeypatch.setattr(
        diag.subprocess, "run", lambda *a, **k: subprocess.CompletedProcess(a, 0, "sha256:x", "")
    )
    verdict = diag.Verdict("restart-at-building", True)

    path = diag._record("cmp_abc", verdict)

    assert verdict.passed is False
    assert verdict.failures == ["run_a is completed and 1 flow run(s) of it are open: ['fr_dead']"]
    assert '"flow_runs_left_open"' in path.read_text()


@pytest.mark.parametrize(
    ("terminal", "binding", "launch_id", "failures"),
    [
        ("infrastructure_failed", {"row": 10, "action": "retry"}, "lnc_1", []),
        (
            "other",
            {"row": 14, "action": "escalate"},
            "",
            [
                "the run ended as other, not infrastructure_failed",
                "the continuation was row 14 (escalate), not row 10 (retry)",
                "the retry decision launched nothing",
            ],
        ),
        (
            "",
            {"row": 10, "action": "retry"},
            "lnc_1",
            ["the run ended as nothing recorded, not infrastructure_failed"],
        ),
    ],
    ids=["retried", "escalated-as-before-1824", "no-summary"],
)
def test_a_run_the_box_refuses_is_retried_not_escalated(terminal, binding, launch_id, failures):
    """#1824. Bug caught: the refusal recorded as `other` and escalated to the owner (row 14), as
    every infrastructure failure was before; or a retry decided but never launched."""
    verdict = diag.infrastructure_retry_verdict(terminal, binding, launch_id)

    assert verdict.failures == failures
    assert verdict.passed is (not failures)
