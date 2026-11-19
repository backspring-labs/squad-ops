"""Studio's release channel, as the worker's Mac reads it (SIP-0117 R5.29; #3206).

Entered at ``MacStudioApp.channel``. ``pgrep`` and ``lsof`` answer as the Mac's answered on
2026-11-18, and the startup log is written as Studio 0.748 wrote it. The live read of the real
Studio is in the PR.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from adapters.remote_execution.game_dev_roblox_studio import studio_app
from adapters.remote_execution.game_dev_roblox_studio.studio_app import MacStudioApp

APP = Path("/Applications/RobloxStudio.app")
#: A startup log's first lines, as Studio writes them. The channel is on the third.
_HEAD = (
    "[FLog::Output] All use of Roblox services must comply with Roblox's Terms of Use.\n"
    "2026-11-18T20:28:29.266Z,0.266726,f21c1e80,6,Info [FLog::StudioMain] RobloxGitHash: 4f22\n"
    "{channel}"
    "2026-11-18T20:28:29.616Z,0.616989,f21c1e80,6,Info [FLog::StartupUpdateUtils] "
    "interruptWithApplicationUpdateIfAvailable - Application is currently at version "
    "0.748.0.7481526 and channel {named}. Latest version 0.748.0.7481526 with guid unknown\n"
)
_CHANNEL = "2026-11-18T20:28:29.408Z,0.408822,f21c1e80,6 [FLog::ClientRunInfo] The channel is {}\n"
#: What a game script's ``print`` looks like in the same log.
_PRINTED = "2026-11-18T20:40:34.267Z,725.2677,6e233000,6 [FLog::Output] The channel is production\n"


def _log(directory: Path, started: str, channel: str | None, *, printed: bool = False) -> Path:
    """A startup log named as Studio names it. ``channel`` ``None`` writes no channel line."""
    log = directory / f"0.748.0.7481526_{started}_Studio_42ba7_last.log"
    line = _CHANNEL.format(channel) if channel is not None else ""
    log.write_text(
        _HEAD.format(channel=line, named=channel or "unknown") + (_PRINTED if printed else "")
    )
    return log


def _mac(monkeypatch, *, pids: str = "28417\n", holds: tuple[Path, ...] = (), lsof: int = 0):
    """The Mac's ``pgrep`` and ``lsof``. ``holds`` are the logs the process has open."""
    opened = [
        "p28417", "fcwd", "n/", "ftxt", f"n{APP}/Contents/MacOS/RobloxStudio",
        "f7", "n/Users/someone/Library/Logs/Roblox/log_0.748.0_Studio_42ba7_csg3.log",
        *(part for log in holds for part in ("f9", f"n{log}", "f31", f"n{log}")),
    ]  # fmt: skip

    def run(command, **_):
        if command[0] == "pgrep":
            return subprocess.CompletedProcess(command, 0 if pids else 1, pids, "")
        assert command == ["lsof", "-a", "-p", "28417", "-Fn"], command
        out = "" if lsof else "\n".join(opened) + "\n"
        return subprocess.CompletedProcess(command, lsof, out, "lsof: no process" if lsof else "")

    monkeypatch.setattr(studio_app.subprocess, "run", run)


def test_the_channel_is_the_one_the_running_studio_started_on(tmp_path, monkeypatch):
    """Found on 2026-11-18: the Mac's log directory held logs from five channels, and the
    newest launches at one version were on two of them. Bugs caught:
    - the channel read from another launch's log (the newest file, or the first found), so a
      Studio is held to a channel it isn't running on;
    - a line a game script printed read as Studio's own;
    - a log open on two descriptors counted as two logs, refusing every claim."""
    _log(tmp_path, "20261118T130630Z", "production")
    running = _log(tmp_path, "20261118T202829Z", "zluauordereddensehashmapcontrol", printed=True)
    _mac(monkeypatch, holds=(running,))

    assert MacStudioApp(APP).channel() == "zluauordereddensehashmapcontrol"


@pytest.mark.parametrize(
    ("pids", "logs", "lsof", "says"),
    [
        ("", ["zbeta"], 0, "0 Studio processes are running, and a channel is one Studio's"),
        ("28417\n28500\n", ["zbeta"], 0, "2 Studio processes are running"),
        ("28417\n", [], 0, "Studio (pid 28417) holds 0 startup logs open (none)"),
        ("28417\n", ["zbeta", "production"], 0, "Studio (pid 28417) holds 2 startup logs open"),
        ("28417\n", [None], 0, "names no channel"),
        ("28417\n", ["zbeta"], 1, "lsof -p 28417 failed: lsof: no process"),
    ],
    ids=["no-studio-running", "two-studios", "no-startup-log-held", "two-startup-logs-held",
         "a-log-with-only-a-printed-line", "lsof-fails"],
)  # fmt: skip
def test_a_channel_that_cant_be_read_is_an_error_naming_why(
    tmp_path, monkeypatch, pids, logs, lsof, says
):
    """The worker refuses a Studio whose channel it can't read (R5.29), so each way of not
    reading it must raise, and say which it was. Bugs caught: a default channel returned; a
    guess between two Studios or two logs; and a game script's printed line taken for
    Studio's when the log names no channel of its own."""
    held = tuple(
        _log(tmp_path, f"2026111{i}T202829Z", channel, printed=channel is None)
        for i, channel in enumerate(logs)
    )
    _mac(monkeypatch, pids=pids, holds=held, lsof=lsof)

    with pytest.raises(OSError, match=says.replace("(", r"\(").replace(")", r"\)")):
        MacStudioApp(APP).channel()
