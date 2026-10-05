"""Running a command with a time limit, and stopping everything it started (#1983).

``npm`` and ``npx`` do their work in grandchildren: node, install scripts, vitest workers. The
subprocess sites each killed the direct child on a timeout (``proc.kill()``), and SIGKILL to the
parent does not reach them, so a timed-out install or test run left its process tree running in
the agent's container, still consuming CPU and memory while the next attempt started.

Here the command runs in a session of its own, so it leads a process group, and a timeout ends
the whole group: SIGTERM, then SIGKILL for whatever is still there. A cancelled caller ends it
the same way before the cancellation goes on. ``route_rendering`` starts its servers this way for
the same reason (a stopped ``npx`` left its dev server serving), and stops them through
``signal_group``, which refuses any target that is not a started child's group.

Spawning still raises as ``asyncio.create_subprocess_exec`` does (``FileNotFoundError`` for a
missing binary), because each caller says what a missing tool means for its own check.

``run_bounded_sync`` and ``stop_group`` are the same for synchronous callers: the probe runner and
route rendering build, boot and browse from a worker thread, where ``subprocess.run(timeout=)``
and ``Popen.kill()`` likewise reached the direct child only.
"""

from __future__ import annotations

import asyncio
import contextlib
import os
import signal
import subprocess
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

#: How long the group has to exit after SIGTERM before it is killed outright.
TERM_GRACE_S = 5.0


@dataclass(frozen=True)
class BoundedRun:
    """What a bounded run produced. ``returncode`` is ``None`` when it timed out."""

    returncode: int | None
    stdout: bytes
    stderr: bytes

    @property
    def timed_out(self) -> bool:
        return self.returncode is None


async def run_bounded(
    argv: Sequence[str],
    *,
    cwd: str | Path | None,
    timeout: float | None,
    env: Mapping[str, str] | None = None,
) -> BoundedRun:
    """Run ``argv`` for at most ``timeout`` seconds (``None``: no limit), capturing its output.
    On a timeout, or when the caller is cancelled, every process the command started is ended."""
    proc = await asyncio.create_subprocess_exec(
        *argv,
        cwd=None if cwd is None else str(cwd),
        env=None if env is None else dict(env),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        start_new_session=True,
    )
    try:
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
    except TimeoutError:
        await end_group(proc)
        return BoundedRun(None, b"", b"")
    except asyncio.CancelledError:
        await end_group(proc)
        raise
    return BoundedRun(proc.returncode, stdout, stderr)


async def end_group(proc: asyncio.subprocess.Process) -> None:
    """End ``proc``'s process group: SIGTERM, a grace period, then SIGKILL; then reap ``proc``.
    A group already gone is not an error."""
    signal_group(proc.pid, signal.SIGTERM)
    try:
        await asyncio.wait_for(proc.wait(), timeout=TERM_GRACE_S)
    except TimeoutError:
        pass
    # The leader may have exited on SIGTERM while a grandchild ignored it: the group outlives
    # its leader, so it is killed whether or not ``proc`` has already gone.
    signal_group(proc.pid, signal.SIGKILL)
    with contextlib.suppress(ProcessLookupError):
        await proc.wait()


def run_bounded_sync(
    argv: Sequence[str],
    *,
    cwd: str | Path | None,
    timeout: float,
    env: Mapping[str, str] | None = None,
) -> BoundedRun:
    """``run_bounded`` for a synchronous caller. Spawning raises as ``subprocess.Popen`` does."""
    proc = subprocess.Popen(  # noqa: S603 — every caller passes a fixed argv
        list(argv),
        cwd=None if cwd is None else str(cwd),
        env=None if env is None else dict(env),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        start_new_session=True,
    )
    try:
        stdout, stderr = proc.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        stop_group(proc)
        # Close the pipes: the group is gone, so nothing holds them open any more.
        with contextlib.suppress(subprocess.TimeoutExpired):
            proc.communicate(timeout=TERM_GRACE_S)
        return BoundedRun(None, b"", b"")
    except BaseException:
        stop_group(proc)
        raise
    return BoundedRun(proc.returncode, stdout, stderr)


def stop_group(proc: subprocess.Popen) -> None:
    """End the group of a process started with ``start_new_session=True``, as ``end_group``
    does for an asyncio one: SIGTERM, a grace period, SIGKILL, then reap ``proc``. A process
    started without its own session leads no group, and this would signal nothing."""
    signal_group(proc.pid, signal.SIGTERM)
    with contextlib.suppress(subprocess.TimeoutExpired):
        proc.wait(timeout=TERM_GRACE_S)
    signal_group(proc.pid, signal.SIGKILL)
    with contextlib.suppress(subprocess.TimeoutExpired):
        proc.wait(timeout=TERM_GRACE_S)


def signal_group(pgid: int, sig: signal.Signals) -> None:
    """Send ``sig`` to the process group ``pgid`` leads. A group already gone is not an error.

    Only a started child's group is a target: an ``int`` above 1. ``os.killpg(pgid, sig)`` is
    ``kill(-pgid, sig)``, so a ``pgid`` of 1 signals every process the caller may signal: the
    login session, its terminal multiplexer, and any container running under the same uid. A
    mocked process's ``pid`` converts to 1, and this module's first draft did exactly that from
    a unit test that mocked the subprocess, twice on 2026-10-05. 0 is the caller's own group.
    """
    if type(pgid) is not int or pgid <= 1:
        raise ValueError(f"refusing to signal process group {pgid!r}: not a started child's")
    with contextlib.suppress(ProcessLookupError, PermissionError):
        os.killpg(pgid, sig)
