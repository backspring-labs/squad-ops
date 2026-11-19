"""Studio as an app on the worker's Mac: finding it, quitting it and opening a place in it
(SIP-0117 R3.6's reset; #3039).

# Platform: dev-mac (Roblox Studio runs only on the worker's Mac)

The reset quits Studio, puts the baseline file in the place file's stead, and opens it again, with
no person involved. ``play_scenario`` asks one more thing: which app is in front, since Studio's
input tools act only on a Studio in front (#3040, found live: a click with Terminal in front never
answered). These are what the adapter asks of the Mac, behind :class:`StudioApp` so a test can
stand in for them. :class:`MacStudioApp` is the real one: ``pgrep``, a signal, ``open -a``,
``lsappinfo`` and ``lsof``.

**Studio's release channel** (#3206) is read here too. Roblox's updater moves an install between
channels at one version number, and a channel can carry another build or flag set. The running
Studio names its channel once, in the startup log it holds open, so the channel read is the one
of the Studio a play would run on, and never of an earlier launch.
"""

from __future__ import annotations

import os
import re
import signal
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

#: Studio's process name on macOS.
PROCESS = "RobloxStudio"
#: Studio's startup log, as Studio names it: ``<version>_<UTC start>_Studio_<id>_last.log``.
_STARTUP_LOG = re.compile(r"_Studio_[0-9A-Za-z]+_last\.log$")
#: The line Studio names its channel on. The tag must be the line's own: a line a game script
#: printed is tagged ``FLog::Output``, whatever its text says.
_CHANNEL_LINE = re.compile(r"^[^\[]*\[FLog::ClientRunInfo\] The channel is (\S+)\s*$")


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

    def frontmost(self) -> int | None:
        """The process id of the app in front, or ``None`` when no app is."""
        ...

    def channel(self) -> str:
        """The release channel the one running Studio started on (#3206). Raises ``OSError``
        naming why it can't be read. Nothing stands in for a channel that wasn't read."""
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

    def frontmost(self) -> int | None:
        front = _lsappinfo("front")
        if not front or "NULL" in front:
            return None
        info = _lsappinfo("info", "-only", "pid", front)
        match = re.search(r'"pid"=(\d+)', info)
        if match is None:
            raise OSError(f"lsappinfo named no pid for the app in front ({front}): {info!r:.200}")
        return int(match.group(1))

    def channel(self) -> str:
        pids = self.pids()
        if len(pids) != 1:
            raise OSError(
                f"{len(pids)} Studio processes are running, and a channel is one Studio's"
            )
        [pid] = pids
        logs = _startup_logs(pid)
        if len(logs) != 1:
            raise OSError(
                f"Studio (pid {pid}) holds {len(logs)} startup logs open "
                f"({', '.join(log.name for log in logs) or 'none'}), and its channel is read "
                "from the one it started with"
            )
        return channel_in(logs[0])


def channel_in(log: Path) -> str:
    """The channel Studio's startup log names. Raises ``OSError`` for a log that can't be
    read or names none."""
    with log.open(encoding="utf-8", errors="replace") as lines:
        for line in lines:
            named = _CHANNEL_LINE.match(line)
            if named is not None:
                return named.group(1)
    raise OSError(f"Studio's startup log {log.name} names no channel")


def _startup_logs(pid: int) -> list[Path]:
    """The startup logs the process holds open, from ``lsof``: Studio writes its log for as
    long as it runs."""
    done = subprocess.run(
        ["lsof", "-a", "-p", str(pid), "-Fn"],
        capture_output=True, text=True, timeout=10, check=False,
    )  # fmt: skip
    names = {line[1:] for line in done.stdout.splitlines() if line.startswith("n")}
    logs = sorted(Path(name) for name in names if _STARTUP_LOG.search(name))
    if not logs and done.returncode != 0:
        raise OSError(f"lsof -p {pid} failed: {done.stderr.strip() or done.returncode}")
    return logs


def _lsappinfo(*args: str) -> str:
    done = subprocess.run(
        ["lsappinfo", *args], capture_output=True, text=True, timeout=10, check=False
    )
    if done.returncode != 0:
        raise OSError(f"lsappinfo {' '.join(args)} failed: {done.stderr.strip()}")
    return done.stdout.strip()
