"""A process's end reads as its end, however the kernel reports it.

Bug caught: main's run 37395958188. A process that exits between ``/proc/<pid>/stat``'s open and
its read raises ``ProcessLookupError``. The probe runner's copy of ``alive`` did not catch it, so
a test of a stop that had worked failed.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

from tests.unit.core.process_watch import alive, ended


@pytest.mark.parametrize("error", [FileNotFoundError, ProcessLookupError])
def test_a_process_whose_stat_vanishes_mid_read_has_ended(monkeypatch, error):
    def vanished(self, *args, **kwargs):
        raise error(3, "No such process")

    monkeypatch.setattr(Path, "read_text", vanished)

    assert alive(os.getpid()) is False
    assert ended(os.getpid(), within=0.1) is True


def test_a_running_process_is_alive_until_it_is_killed():
    """The control: the helper does not read every process as ended."""
    proc = subprocess.Popen(["sleep", "60"])
    try:
        assert alive(proc.pid) is True
    finally:
        proc.kill()
        proc.wait()
    assert ended(proc.pid)
