"""Watching a process a test started come to an end (#1983's group-stop tests).

One copy, because two drifted apart: the probe runner's tests read ``/proc/<pid>/stat`` without
catching ``ProcessLookupError``, which the kernel raises when the process exits between the
file's open and its read. That is the process ending, which is what the tests wait for, and it
failed main's lint + regression job (run 37395958188).

A process's state comes from ``/proc`` on Linux and from ``ps`` everywhere else (#2976). macOS has
no ``/proc``, and the read's ``FileNotFoundError`` is how a process that has ended looks, so there
every process read as ended and each ``assert ended(...)`` in the group-stop tests passed whether
or not the stop had worked.
"""

from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

#: The grandchild sleeps far longer than any stop may take, so a stop that waits for it is seen.
SLEEP_S = 60
#: Whether a process's state is read from ``/proc``. A test of one reading sets it.
READS_PROC = sys.platform.startswith("linux")


def alive(pid: int) -> bool:
    """Running, and not a zombie awaiting its reaper (a container may have no init to reap it)."""
    state = _state_from_proc(pid) if READS_PROC else _state_from_ps(pid)
    return state is not None and not state.startswith("Z")


def _state_from_proc(pid: int) -> str | None:
    """The state field of ``/proc/<pid>/stat``, or ``None`` once the process is gone."""
    try:
        return Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()[0]
    except (FileNotFoundError, ProcessLookupError, IndexError):
        return None


def _state_from_ps(pid: int) -> str | None:
    """What ``ps`` gives for the process's state, or ``None`` once the process is gone. ``ps``
    answers a pid it doesn't hold with exit 1 and nothing written; anything it writes to stderr
    is ``ps`` itself failing, and that is raised, since it says nothing about the process."""
    proc = subprocess.run(["ps", "-o", "stat=", "-p", str(pid)], capture_output=True, text=True)
    if proc.stderr.strip():
        raise RuntimeError(f"ps could not read process {pid}: {proc.stderr.strip()}")
    return proc.stdout.strip() or None


def ended(pid: int, within: float = 2.0) -> bool:
    """A signal is delivered asynchronously, so the process ends shortly after the kill returns."""
    deadline = time.monotonic() + within
    while alive(pid):
        if time.monotonic() > deadline:
            return False
        time.sleep(0.02)
    return True


def forking(pidfile: Path) -> tuple[str, ...]:
    """A launcher that starts the real work beneath it, as ``npm`` and ``npx`` do, and writes the
    work's pid to ``pidfile``."""
    return ("sh", "-c", f"sleep {SLEEP_S} & echo $! > {pidfile}; wait")
