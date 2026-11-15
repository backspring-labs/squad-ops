"""Studio as an app on the worker's Mac: finding it, quitting it and opening a place in it
(SIP-0117 R3.6's reset; #3039).

# Platform: dev-mac (Roblox Studio runs only on the worker's Mac)

The reset quits Studio, puts the baseline file in the place file's stead, and opens it again, with
no person involved. These are the three things it asks of the Mac, behind :class:`StudioApp` so a
test can stand in for them. :class:`MacStudioApp` is the real one: ``pgrep``, a signal, and
``open -a``.
"""

from __future__ import annotations

import os
import signal
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

#: Studio's process name on macOS.
PROCESS = "RobloxStudio"


@dataclass(frozen=True)
class PlaceFiles:
    """What a reset restores, as the worker is configured with it.

    ``baseline`` is the read-only place file a reset copies from, pinned by ``baseline_sha256``.
    ``baseline_digest`` is the non-script baseline (the harness's ``baseline`` program) the
    reopened place must hold."""

    place: Path
    baseline: Path
    baseline_sha256: str
    baseline_digest: str

    @property
    def lock(self) -> Path:
        """The lock Studio keeps beside an open place: its first line is Studio's pid."""
        return self.place.with_name(self.place.name + ".lock")


class StudioApp(Protocol):
    def pids(self) -> list[int]:
        """Every running Studio process's id."""
        ...

    def alive(self, pid: int) -> bool: ...

    def quit(self, pid: int, *, force: bool) -> None:
        """Ask the process to quit, or kill it when ``force``."""
        ...

    def open(self, place: Path) -> None:
        """Open ``place`` in Studio, starting it."""
        ...


class MacStudioApp:
    """Studio on macOS, at ``app`` (``/Applications/RobloxStudio.app``)."""

    def __init__(self, app: Path) -> None:
        self._app = app

    def pids(self) -> list[int]:
        found = subprocess.run(
            ["pgrep", "-x", PROCESS], capture_output=True, text=True, timeout=10, check=False
        )
        if found.returncode not in (0, 1):  # 1: no process matched
            raise OSError(f"pgrep -x {PROCESS} failed: {found.stderr.strip()}")
        return [int(line) for line in found.stdout.split()]

    def alive(self, pid: int) -> bool:
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return False
        except PermissionError:
            return True  # another user's process: running, and not ours to touch
        return True

    def quit(self, pid: int, *, force: bool) -> None:
        try:
            os.kill(pid, signal.SIGKILL if force else signal.SIGTERM)
        except ProcessLookupError:
            pass  # already gone, which is what was asked

    def open(self, place: Path) -> None:
        subprocess.run(["open", "-a", str(self._app), str(place)], check=True, timeout=30)
