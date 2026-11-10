"""A known memory reading for the tests of the Spark's engine scripts (#2976).

``engine_switch.py`` and ``memory_watchdog.py`` are written for the Spark and read
``/proc/meminfo``. Their tests run on every profile, and macOS has no ``/proc``, so 32 of them
failed there at the first record line. On Linux they passed while reading the memory of whatever
box ran them, so no test could say what a reading should come to.

``install`` points a script module's ``Path("/proc/meminfo")`` at a file holding the reading
below. The script's own parsing still runs, on every platform, against values a test can assert.
"""

from __future__ import annotations

from pathlib import Path

#: 100 GiB available, and 1.5 GiB of a 16 GiB swap used. The kernel reports kibibytes, and a line
#: with no unit (the huge-page counts) is part of every real reading.
MEMINFO = """\
MemTotal:       127535064 kB
MemFree:          3145728 kB
MemAvailable:   104857600 kB
SwapTotal:       16777216 kB
SwapFree:        15204352 kB
HugePages_Total:        0
"""
MEM_AVAILABLE_GIB = 100.0
SWAP_USED_GIB = 1.5


class _ProcMeminfoRedirect:
    """Stands in for a module's ``Path``: ``Path("/proc/meminfo")`` is the reading's file, and
    every other use is ``pathlib.Path``'s own."""

    def __init__(self, reading: Path) -> None:
        self._reading = reading

    def __call__(self, *parts):
        return self._reading if parts == ("/proc/meminfo",) else Path(*parts)

    def __getattr__(self, name: str):
        return getattr(Path, name)


def install(monkeypatch, module, directory: Path, text: str = MEMINFO) -> None:
    """Give ``module`` the reading ``text`` wherever it reads ``/proc/meminfo``."""
    reading = directory / "proc-meminfo"
    reading.write_text(text)
    monkeypatch.setattr(module, "Path", _ProcMeminfoRedirect(reading))
