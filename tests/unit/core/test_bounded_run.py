"""#1983: a timed-out or cancelled command is stopped with everything it started.

The bug these catch: killing only the direct child. ``npm`` and ``npx`` run their work in
grandchildren, which a parent-only SIGKILL leaves running in the agent's container. The grandchild
also holds the output pipe open, so the caller's ``await proc.wait()`` blocks until it exits on
its own: a timed-out install blocked its caller for as long as its tree kept running. Each test
starts a shell that forks a sleeping grandchild, and asks both whether the run came back within
the stop's bound and whether the grandchild is gone.
"""

from __future__ import annotations

import asyncio
import os
import signal
import subprocess
import time
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from squadops.core import bounded_run
from squadops.core.bounded_run import (
    TERM_GRACE_S,
    run_bounded,
    run_bounded_sync,
    signal_group,
    stop_group,
)
from tests.unit.core.process_watch import SLEEP_S, ended, forking

#: How long a stop may take: the grace period, and a margin for a loaded test machine.
_STOP_BOUND_S = TERM_GRACE_S + 5


async def _grandchild(pidfile: Path) -> int:
    for _ in range(100):
        if pidfile.exists() and pidfile.read_text().strip():
            return int(pidfile.read_text())
        await asyncio.sleep(0.02)
    raise AssertionError("the command never started its grandchild")


async def test_a_timeout_ends_the_grandchildren_too(tmp_path):
    pidfile = tmp_path / "pid"
    started = time.monotonic()

    run = await run_bounded(forking(pidfile), cwd=tmp_path, timeout=0.5)

    assert run.timed_out
    assert time.monotonic() - started < _STOP_BOUND_S
    assert ended(int(pidfile.read_text()))


async def test_a_cancelled_caller_ends_the_command_and_its_grandchildren(tmp_path):
    pidfile = tmp_path / "pid"
    task = asyncio.create_task(run_bounded(forking(pidfile), cwd=tmp_path, timeout=60))
    grandchild = await _grandchild(pidfile)

    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await asyncio.wait_for(task, timeout=_STOP_BOUND_S)

    assert ended(grandchild)


async def test_a_command_that_finishes_returns_its_code_and_output(tmp_path):
    run = await run_bounded(
        ["sh", "-c", "echo out; echo err >&2; exit 3"],
        cwd=tmp_path,
        timeout=10,
        env={**os.environ, "LC_ALL": "C"},
    )

    assert (run.returncode, run.stdout, run.stderr, run.timed_out) == (3, b"out\n", b"err\n", False)


async def test_a_missing_binary_raises_for_the_caller_to_name(tmp_path):
    """Each caller says what a missing tool means for its own check, so spawning still raises."""
    with pytest.raises(FileNotFoundError):
        await run_bounded(["no-such-binary-1983"], cwd=tmp_path, timeout=1)


# The synchronous pair: the probe runner and route rendering build, boot and browse from a thread.


def _grandchild_sync(pidfile: Path) -> int:
    for _ in range(100):
        if pidfile.exists() and pidfile.read_text().strip():
            return int(pidfile.read_text())
        time.sleep(0.02)
    raise AssertionError("the command never started its grandchild")


def test_a_sync_timeout_ends_the_grandchildren_too(tmp_path):
    pidfile = tmp_path / "pid"
    started = time.monotonic()

    run = run_bounded_sync(forking(pidfile), cwd=tmp_path, timeout=0.5)

    assert run.timed_out
    assert time.monotonic() - started < _STOP_BOUND_S
    assert ended(int(pidfile.read_text()))


def test_a_grandchild_that_ignores_sigterm_is_stopped_after_its_leader_exits(tmp_path):
    """The leader exits on SIGTERM; a grandchild that ignores it keeps the group alive. A stop
    that sends SIGKILL only when the leader outlives the grace period (route rendering's, before
    #1983) returns with that grandchild still running."""
    pidfile = tmp_path / "pid"
    proc = subprocess.Popen(
        ["sh", "-c", f"(trap '' TERM; exec sleep {SLEEP_S}) & echo $! > {pidfile}; wait"],
        start_new_session=True,
    )
    grandchild = _grandchild_sync(pidfile)

    stop_group(proc)

    assert proc.returncode is not None
    assert ended(grandchild)


def test_a_sync_missing_binary_raises_for_the_caller_to_name(tmp_path):
    with pytest.raises(FileNotFoundError):
        run_bounded_sync(["no-such-binary-1983"], cwd=tmp_path, timeout=1)


# ``killpg(pgid)`` is ``kill(-pgid)``: 1 is every process the caller may signal, 0 its own group.
# These replace ``os.killpg`` with a recorder BEFORE calling, so a broken guard fails the test
# rather than signalling the machine running it.


@pytest.fixture
def signalled(monkeypatch) -> list[tuple]:
    sent: list[tuple] = []
    monkeypatch.setattr(bounded_run.os, "killpg", lambda *a: sent.append(a))
    return sent


@pytest.mark.parametrize(
    "pgid", [MagicMock().pid, 1, 0, -1], ids=["mock-pid", "every-process", "own-group", "negative"]
)
def test_a_target_that_is_not_a_started_childs_group_is_refused(pgid, signalled):
    with pytest.raises(ValueError, match="refusing to signal process group"):
        signal_group(pgid, signal.SIGKILL)

    assert signalled == []


async def test_a_mocked_subprocess_that_times_out_signals_nothing(signalled, monkeypatch):
    """The 2026-10-05 path: a test mocks the subprocess, the run times out, and the group kill
    receives the mock's ``pid``. It must refuse, not become ``kill(-1, SIGKILL)``."""
    proc = MagicMock()
    proc.communicate = AsyncMock(side_effect=TimeoutError)
    proc.wait = AsyncMock()
    monkeypatch.setattr(bounded_run.asyncio, "create_subprocess_exec", AsyncMock(return_value=proc))

    with pytest.raises(ValueError, match="refusing to signal process group"):
        await run_bounded(["npm", "install"], cwd=None, timeout=1)

    assert signalled == []
