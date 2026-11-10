"""A process's end reads as its end, however the kernel reports it.

Bug caught: main's run 37395958188. A process that exits between ``/proc/<pid>/stat``'s open and
its read raises ``ProcessLookupError``. The probe runner's copy of ``alive`` did not catch it, so
a test of a stop that had worked failed.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

from tests.unit.core import process_watch
from tests.unit.core.process_watch import alive, ended


@pytest.mark.parametrize("error", [FileNotFoundError, ProcessLookupError])
def test_a_process_whose_stat_vanishes_mid_read_has_ended(monkeypatch, error):
    """The ``/proc`` reading, which is Linux's. Run on every platform as Linux (#2976): the read
    is replaced, so nothing here needs a real ``/proc``."""

    def vanished(self, *args, **kwargs):
        raise error(3, "No such process")

    monkeypatch.setattr(process_watch, "READS_PROC", True)
    monkeypatch.setattr(Path, "read_text", vanished)

    assert alive(os.getpid()) is False
    assert ended(os.getpid(), within=0.1) is True


@pytest.mark.parametrize(
    "reads_proc",
    [
        pytest.param(
            True,
            marks=pytest.mark.skipif(
                not sys.platform.startswith("linux"),
                reason="/proc is Linux's; this platform reads a process's state from ps",
            ),
        ),
        False,
    ],
    ids=["from /proc", "from ps"],
)
def test_a_running_process_is_alive_until_it_is_killed(monkeypatch, reads_proc):
    """The control: the helper does not read every process as ended. It did on macOS until #2976,
    where there is no ``/proc`` to read. Each reading is run wherever it can be: both on Linux,
    ``ps`` on macOS."""
    monkeypatch.setattr(process_watch, "READS_PROC", reads_proc)
    proc = subprocess.Popen(["sleep", "60"])
    try:
        assert alive(proc.pid) is True
        proc.kill()
        # Killed and not yet reaped: a zombie, which has ended for every caller's purpose.
        assert ended(proc.pid)
    finally:
        proc.kill()
        proc.wait()
    assert ended(proc.pid)


def test_a_ps_that_fails_is_raised_and_never_read_as_an_ended_process(monkeypatch):
    """Bug caught: a ``ps`` that could not answer (no permission, a flag it refuses) read as "the
    process has ended", which is the answer every group-stop test is waiting for."""
    monkeypatch.setattr(process_watch, "READS_PROC", False)
    monkeypatch.setattr(
        process_watch.subprocess,
        "run",
        lambda cmd, **kw: subprocess.CompletedProcess(cmd, 1, "", "ps: operation not permitted\n"),
    )

    with pytest.raises(RuntimeError, match="operation not permitted"):
        alive(os.getpid())
