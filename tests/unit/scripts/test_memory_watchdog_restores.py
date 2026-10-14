"""The memory watchdog restores Ollama after it kills TensorFold (#2288).

What bug would this catch? A watchdog that kills TensorFold under memory pressure and stops there:
the clients stay on a dead engine and every cycle fails until someone runs the switch back. And a
restoration that failed logged as one that worked.
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "scripts" / "dev" / "ops"))
_spec = importlib.util.spec_from_file_location(
    "memory_watchdog", ROOT / "scripts/dev/ops/memory_watchdog.py"
)
watchdog = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(watchdog)


def _answering(restore):
    calls = []

    def run(cmd, **kw):
        calls.append(cmd[-1] if cmd[0] == sys.executable else " ".join(cmd[:2]))
        if cmd[0] == sys.executable:
            return restore(cmd)
        return subprocess.CompletedProcess(cmd, 0, "", "")

    return calls, run


def _restore_exits(code, said):
    return lambda cmd: subprocess.CompletedProcess(cmd, code, said, "")


def _restore_hangs(cmd):
    raise subprocess.TimeoutExpired(cmd, watchdog.RESTORE_TIMEOUT_SECONDS)


@pytest.mark.parametrize(
    ("restore", "event"),
    [
        (_restore_exits(0, '{"step": "done", "command": "restore"}'), "restored"),
        (_restore_exits(4, '{"step": "done", "command": "restore"}'), "restored"),
        (_restore_exits(3, '{"step": "RESTORATION_FAILED"}'), "restoration_failed"),
        (_restore_hangs, "restoration_failed"),
    ],
    ids=["restored", "restored, unrecorded", "restoration failed", "restoration hung"],
)
def test_a_kill_is_followed_by_the_restoration_and_its_outcome_is_logged(
    monkeypatch, tmp_path, restore, event
):
    monkeypatch.setattr(watchdog, "LOG", tmp_path / "watchdog.jsonl")
    calls, run = _answering(restore)
    monkeypatch.setattr(watchdog.subprocess, "run", run)

    watchdog.act("memory floor")

    lines = [json.loads(x) for x in (tmp_path / "watchdog.jsonl").read_text().splitlines()]
    assert calls == ["docker kill", "restore"]
    assert [x["event"] for x in lines] == ["killing_tensorfold", "killed_tensorfold", event]
    assert lines[0]["reason"] == "memory floor"


GIB = 2**30


@pytest.mark.parametrize(
    ("readings", "tensorfold", "acted"),
    [
        ([(10 * GIB, 0), (10 * GIB, 0)], True, ["memory floor"]),
        ([(10 * GIB, 0), (30 * GIB, 0)], True, []),  # one low reading is a dip, not a floor
        ([(10 * GIB, 0), (10 * GIB, 0)], False, []),  # Ollama serving: nothing of ours to stop
        ([(50 * GIB, 3 * GIB)], True, ["swap climb"]),
    ],
    ids=["two low readings", "one low reading", "on ollama", "swap climb"],
)
def test_the_watch_acts_only_on_a_held_floor_or_a_climb_while_tensorfold_runs(
    monkeypatch, readings, tensorfold, acted
):
    """Entered at ``watch_once``, the step the service's loop runs. Bug caught: the loop killing
    TensorFold without restoring (it calls ``act``, which restores), acting on Ollama, or on a
    single dip under the floor."""
    feed = iter([*readings, (50 * GIB, 0)])
    monkeypatch.setattr(watchdog, "meminfo", lambda: next(feed))
    monkeypatch.setattr(watchdog, "tensorfold_running", lambda: tensorfold)
    monkeypatch.setattr(watchdog.time, "sleep", lambda s: None)
    seen = []
    monkeypatch.setattr(watchdog, "act", seen.append)

    low, base = 0, 0
    for _ in readings:
        low, base = watchdog.watch_once(low, base, 12 * GIB, 2 * GIB)

    assert seen == acted
