"""#1956: the supervisor's instruments, tracked. Each decides a verdict a release record cites, so
the predicate that decides it is what these hold."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

_DEV = Path(__file__).resolve().parents[3] / "scripts" / "dev"


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, _DEV / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod  # a dataclass resolves its module by name
    spec.loader.exec_module(mod)
    return mod


watch = _load("campaign_watch")
lease = _load("campaign_lease_proof")
replay = _load("campaign_binding_replay")
loaded = _load("verify_loaded")


def _snap(state="running", runs=(("framing", "running"),), gate=None):
    return watch.Snapshot(state=state, outcome=None, cycle="cyc_1", runs=runs, gate_open=gate)


@pytest.mark.parametrize(
    ("snap", "gate_seen", "why"),
    [
        (_snap(), False, None),
        (_snap(state="escalated"), False, "campaign escalated"),
        (_snap(state="launch_blocked"), False, "campaign launch_blocked"),
        # A gate is the supervisor's only once it stays open across two polls.
        (_snap(runs=(("proposal", "completed"),), gate="proposal"), False, None),
        (
            _snap(runs=(("proposal", "completed"),), gate="proposal"),
            True,
            "a gate is open on the proposal run",
        ),
        (_snap(runs=(("framing", "failed"),)), False, "a framing run failed"),
    ],
)
def test_the_watcher_exits_exactly_when_the_supervisor_is_needed(snap, gate_seen, why):
    """Bugs caught: a watcher that sleeps through an escalation or a failed run, and one that
    wakes the supervisor for a gate in the instant before its decision is recorded."""
    assert watch.needs_supervisor(snap, gate_seen) == why


_HOLDS = {
    "step1_create": "refused: supervisor_holds_the_box",
    "step2_create": "refused: box_not_quiet",
    "step3_framing": "run_f queued",
    "step3_waiting": True,
    "step4_framing": "run_f queued",
    "step4_create": "refused: box_not_quiet",
    "step5_framing": "run_f running",
    "step5_free": True,
    "audit_refusals": ["t1 supervisor_holds_the_box", "t2 box_not_quiet", "t3 box_not_quiet"],
}


@pytest.mark.parametrize(
    ("change", "failed_step"),
    [
        ({}, None),
        ({"step1_create": "cycle created"}, "step 1"),
        ({"step4_framing": "run_f running"}, "step 4"),
        ({"step5_free": False}, "step 5"),
        ({"audit_refusals": ["t1 x"]}, "audit"),
    ],
)
def test_the_lease_proof_names_every_step_that_did_not_hold(change, failed_step):
    """Bug caught: a proof that reports "holds" when the lease let a launch through or the run
    started beside a resident model, which is the record #1908 cites."""
    failures = lease.verdict({**_HOLDS, **change})

    assert (failures == []) is (failed_step is None)
    if failed_step:
        assert any(f.startswith(failed_step) for f in failures)


def test_the_binding_replay_reports_each_criterion_that_recomputes_differently():
    frozen = [
        {"criterion_id": "T1", "statement": "sorted by date", "surface": "GET /runs"},
        {"criterion_id": "T2", "statement": "a full run refuses", "surface": "POST /join"},
    ]
    stated = {"T1": {"statement": "sorted by date", "surface": "GET /runs"}, "T2": {}}

    found = replay.mismatches(frozen, stated)

    assert [m.split(":")[0] for m in found] == ["T2"]


@pytest.mark.parametrize(
    ("expect", "code", "out", "ok"),
    [
        ("True", 0, "warning: x\nTrue\n", True),
        ("True", 0, "False\n", False),
        ("nothing_to_build", 1, "", False),
    ],
)
def test_a_loaded_check_passes_only_on_the_expected_last_line(expect, code, out, ok):
    """Bug caught: a snippet that crashed, or printed the old code's answer, read as loaded."""
    assert (loaded.judge(expect, code, out, "Traceback\nImportError: x") is None) is ok


def test_an_only_id_that_names_no_row_runs_nothing_and_says_so(capsys):
    """Bug caught: ``--only`` with a misspelt or not-yet-merged id printed "1 loaded, 0 not" having
    run nothing, so a deploy read as carrying a fix it lacked (found 2026-10-09, row 2188 checked
    from a checkout whose file did not hold it)."""
    assert loaded.main(["--only", "no-such-row"]) == 2
    out = capsys.readouterr()
    assert "no loaded check has id 'no-such-row'" in out.err
    assert "loaded" not in out.out


def test_every_loaded_check_row_is_complete():
    import yaml

    rows = yaml.safe_load(loaded.CHECKS.read_text())["checks"]
    assert rows and all({"id", "what", "container", "code", "expect"} <= set(r) for r in rows)
