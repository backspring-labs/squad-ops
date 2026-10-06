"""Watching a process a test started come to an end (#1983's group-stop tests).

One copy, because two drifted apart: the probe runner's tests read ``/proc/<pid>/stat`` without
catching ``ProcessLookupError``, which the kernel raises when the process exits between the
file's open and its read. That is the process ending, which is what the tests wait for, and it
failed main's lint + regression job (run 37395958188).
"""

from __future__ import annotations

import time
from pathlib import Path

#: The grandchild sleeps far longer than any stop may take, so a stop that waits for it is seen.
SLEEP_S = 60


def alive(pid: int) -> bool:
    """Running, and not a zombie awaiting its reaper (a container may have no init to reap it)."""
    try:
        state = Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()[0]
    except (FileNotFoundError, ProcessLookupError, IndexError):
        return False
    return state != "Z"


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
