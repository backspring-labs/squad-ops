"""Studio as an app on the worker's Mac: finding it, quitting it and opening a place in it
(SIP-0117 R3.6's reset; #3039).

# Platform: dev-mac (Roblox Studio runs only on the worker's Mac)

The reset quits Studio, puts the baseline file in the place file's stead, and opens it again, with
no person involved. ``play_scenario`` asks one more thing: which app is in front, since Studio's
input tools act only on a Studio in front (#3040, found live: a click with Terminal in front never
answered). These are what the adapter asks of the Mac, behind :class:`StudioApp` so a test can
stand in for them. :class:`MacStudioApp` is the real one: ``pgrep``, a signal, ``open -a`` (to
open the place), ``lsappinfo``, ``lsof``, and ``osascript`` to bring the running Studio forward by
its process id.

**Whether a person is at the Mac** (#3193) is read here too, for a dedicated worker that brings
Studio to the front itself: how long since the last keyboard or mouse input, and whether the
screen is locked. Both come from ``ioreg``, which needs no macOS permission, so no prompt can wait
on a person who isn't there. A reading that can't be made raises: an activation is never made on
a guess.

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
#: The HID system's idle counter, in nanoseconds since the last keyboard, mouse or trackpad input.
_IDLE_LINE = re.compile(r'"HIDIdleTime" = (\d+)')
#: Whether the console session's screen is locked.
_LOCKED_LINE = re.compile(r'"IOConsoleLocked" = (Yes|No)\b')
#: Each console session's own keys, inside one entry of ``IOConsoleUsers``.
_ON_CONSOLE = re.compile(r'"kCGSSessionOnConsoleKey"=(Yes|No)\b')
_LOGIN_DONE = re.compile(r'"kCGSessionLoginDoneKey"=(Yes|No)\b')
_CONSOLE_USERS = '"IOConsoleUsers" = ('
#: Brings the process whose id is the one argument forward, and answers ``activated``,
#: ``refused`` or ``gone``. ``NSRunningApplication`` names only a running process, so nothing is
#: started. The options are ``NSApplicationActivateAllWindows`` and the (pre-14) ignoring of
#: other apps.
_ACTIVATE = """
function run(argv) {
  ObjC.import('AppKit');
  const app = $.NSRunningApplication.runningApplicationWithProcessIdentifier(parseInt(argv[0], 10));
  if (app.isNil()) { return 'gone'; }
  return app.activateWithOptions(3) ? 'activated' : 'refused';
}
"""


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

    def idle_seconds(self) -> float:
        """Seconds since the last keyboard, mouse or trackpad input (#3193). Raises ``OSError``
        when it can't be read."""
        ...

    def locked(self) -> bool:
        """Whether the screen is locked (#3193). Raises ``OSError`` when it can't be read."""
        ...

    def session_available(self) -> bool:
        """Whether the console session is on the console and logged in (#3193). Raises
        ``OSError`` when it can't be read."""
        ...

    def activate(self, pid: int, timeout_s: float) -> None:
        """Bring the running process ``pid`` to the front (#3193, R5.37), within ``timeout_s``.
        Never starts a process: a ``pid`` that isn't running raises ``OSError``, as does an
        activation the system refused or one that didn't answer in time."""
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

    def idle_seconds(self) -> float:
        return idle_seconds_in(_ioreg("-c", "IOHIDSystem"))

    def locked(self) -> bool:
        return locked_in(_ioreg("-n", "Root", "-d1"))

    def session_available(self) -> bool:
        return session_available_in(_ioreg("-n", "Root", "-d1"))

    def activate(self, pid: int, timeout_s: float) -> None:
        # R5.37: by the running process's id, through AppKit's NSRunningApplication, which
        # answers nil for a process that isn't running and so can't start one (``open -a``
        # did). JavaScript for Automation reaches AppKit with nothing installed.
        try:
            done = subprocess.run(
                ["osascript", "-l", "JavaScript", "-e", _ACTIVATE, str(pid)],
                capture_output=True, text=True, timeout=timeout_s, check=False,
            )  # fmt: skip
        except subprocess.TimeoutExpired as e:
            raise OSError(f"the activation didn't answer within {timeout_s:.1f}s") from e
        answer = done.stdout.strip()
        if done.returncode != 0 or answer != "activated":
            raise OSError(
                f"the activation of process {pid} answered {answer or done.returncode!r}"
                + (f": {done.stderr.strip()[:200]}" if done.stderr.strip() else "")
            )


def idle_seconds_in(ioreg: str) -> float:
    """The idle counter in ``ioreg -c IOHIDSystem``'s output, in seconds. Raises ``OSError``
    when the output holds no counter, or more than one that disagree: a reading of a person's
    absence is never guessed."""
    found = {int(n) for n in _IDLE_LINE.findall(ioreg)}
    if len(found) != 1:
        raise OSError(
            f"ioreg -c IOHIDSystem gave {len(found)} idle counters ({sorted(found)}), and the "
            "idle time is read from exactly one"
        )
    return found.pop() / 1_000_000_000


def session_available_in(ioreg: str) -> bool:
    """Whether ``ioreg -n Root -d1``'s output reads exactly one session on the console, and that
    same session finished logging in (R5.37). Each entry of ``IOConsoleUsers`` is read on its own,
    so one session's "on the console" is never paired with another's "logged in". Raises
    ``OSError`` when there is no ``IOConsoleUsers`` to read. No entry, two on the console, or an
    entry that doesn't say each once is unavailable."""
    on_console = []
    for entry in console_users_in(ioreg):
        on, done = _ON_CONSOLE.findall(entry), _LOGIN_DONE.findall(entry)
        if len(on) != 1 or len(done) != 1:
            return False  # a contradiction within one entry
        if on[0] == "Yes":
            on_console.append(done[0] == "Yes")
    return on_console == [True]


def console_users_in(ioreg: str) -> list[str]:
    """Each entry of ``IOConsoleUsers`` (``({...},{...})``), as its own text. Raises ``OSError``
    when the key is absent or its list doesn't close. Quoted text is skipped, so a brace in a
    value never splits an entry."""
    start = ioreg.find(_CONSOLE_USERS)
    if start < 0:
        raise OSError("ioreg -n Root names no IOConsoleUsers, so no session can be read")
    entries: list[str] = []
    depth, quoted, began = 0, False, -1
    for i in range(start + len(_CONSOLE_USERS), len(ioreg)):
        ch = ioreg[i]
        if quoted:
            quoted = ch != '"'
        elif ch == '"':
            quoted = True
        elif ch == "{":
            depth += 1
            if depth == 1:
                began = i
        elif ch == "}":
            depth -= 1
            if depth == 0:
                entries.append(ioreg[began : i + 1])
        elif ch == ")" and depth == 0:
            return entries
    raise OSError("ioreg -n Root's IOConsoleUsers list doesn't close, so it can't be read")


def locked_in(ioreg: str) -> bool:
    """Whether ``ioreg -n Root -d1``'s output reads the screen locked. Raises ``OSError`` when
    it doesn't say."""
    found = set(_LOCKED_LINE.findall(ioreg))
    if len(found) != 1:
        raise OSError(
            f"ioreg -n Root gave {sorted(found) or 'no'} IOConsoleLocked values, and the lock "
            "is read from exactly one"
        )
    return found.pop() == "Yes"


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


def _ioreg(*args: str) -> str:
    done = subprocess.run(["ioreg", *args], capture_output=True, text=True, timeout=10, check=False)
    if done.returncode != 0:
        raise OSError(f"ioreg {' '.join(args)} failed: {done.stderr.strip() or done.returncode}")
    return done.stdout


def _lsappinfo(*args: str) -> str:
    done = subprocess.run(
        ["lsappinfo", *args], capture_output=True, text=True, timeout=10, check=False
    )
    if done.returncode != 0:
        raise OSError(f"lsappinfo {' '.join(args)} failed: {done.stderr.strip()}")
    return done.stdout.strip()
