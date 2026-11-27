#!/usr/bin/env python3
"""How busy the worker's Mac is, as one JSON document (the 2.9 plan's item 13, #3250).

# Platform: dev-mac (the Studio worker's Mac: `vm_stat`, `memory_pressure`, `sysctl`, `ps`)

The certification window's measured sets are matched only when the host's readings at each set's
start and end are comparable. This takes them:

- the load average (`sysctl -n vm.loadavg`);
- memory: free, active, inactive, wired and compressed, in bytes (`vm_stat`), and the system's
  free percentage (`memory_pressure`);
- the models Ollama has loaded (`ollama ps`), by name;
- whether Docker answers, and how many containers run;
- CPU and resident memory of Studio, of the worker, of Docker and of Ollama, by name, and of
  everything else together, by count only.

**Nothing else is named.** The document goes into a record on a public Release, so the owner's
other apps are never named: they are "other", a count and a total. A reading that can't be taken
says so (`{"unread": why}`) and is never left out or guessed.

    python scripts/dev/host_quiet_reading.py > reading.json
"""

from __future__ import annotations

import json
import platform
import re
import subprocess
import sys
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

Run = Callable[[list[str]], str]

#: The processes read by name. Everything else is "other".
NAMED = ("studio", "worker", "docker", "ollama")
_VM_STAT_PAGE = re.compile(r"page size of (\d+) bytes")
_VM_STAT_LINE = re.compile(r'^"?([A-Za-z][A-Za-z ()-]*?)"?:\s+(\d+)\.?$')
_VM_STAT_KEYS = {
    "Pages free": "free",
    "Pages active": "active",
    "Pages inactive": "inactive",
    "Pages wired down": "wired",
    "Pages occupied by compressor": "compressed",
}


def run(command: list[str]) -> str:
    """A command's standard output. Raises when it can't be run or fails."""
    done = subprocess.run(command, capture_output=True, text=True, timeout=30, check=False)
    if done.returncode != 0:
        raise OSError(f"{command[0]} exited {done.returncode}: {done.stderr.strip()[:200]}")
    return done.stdout


def load_average(text: str) -> list[float]:
    """`sysctl -n vm.loadavg`'s ``{ 2.46 4.68 4.83 }``: the 1, 5 and 15 minute averages."""
    values = [float(v) for v in text.strip().strip("{}").split()]
    if len(values) != 3:
        raise ValueError(f"vm.loadavg read {text.strip()!r}, not three averages")
    return values


def memory(vm_stat: str) -> dict[str, int]:
    """`vm_stat`'s pages, in bytes, for the five kinds this reads. Each must be present."""
    page = _VM_STAT_PAGE.search(vm_stat)
    if page is None:
        raise ValueError("vm_stat names no page size")
    size, found = int(page.group(1)), {}
    for line in vm_stat.splitlines():
        matched = _VM_STAT_LINE.match(line.strip())
        if matched and matched.group(1) in _VM_STAT_KEYS:
            found[_VM_STAT_KEYS[matched.group(1)]] = int(matched.group(2)) * size
    missing = sorted(set(_VM_STAT_KEYS.values()) - set(found))
    if missing:
        raise ValueError(f"vm_stat read no {', '.join(missing)}")
    return found


def free_percent(text: str) -> int:
    matched = re.search(r"free percentage:\s*(\d+)%", text)
    if matched is None:
        raise ValueError("memory_pressure named no free percentage")
    return int(matched.group(1))


def models_loaded(text: str) -> list[str]:
    """`ollama ps`'s loaded models, by name: the first column of each row under its header."""
    lines = [line for line in text.splitlines() if line.strip()]
    if not lines or not lines[0].split() or lines[0].split()[0] != "NAME":
        raise ValueError("ollama ps answered no table")
    return [line.split()[0] for line in lines[1:]]


#: The worker as its command runs it: a Python with these arguments (#3292).
WORKER_ARGUMENTS = "-m squadops.remote_execution.worker_main"


def kind(executable: str, args: str) -> str:
    """Which named process this is, or ``other``, read from its executable (#3292): a shell whose
    own command line merely names Studio or the worker's module is neither. The worker is a
    Python whose arguments run its module. Neither text is kept."""
    name = executable.rsplit("/", 1)[-1]
    if "RobloxStudio.app/Contents/MacOS/" in executable:
        return "studio"
    # Without case: a framework Python on macOS runs as ``Python.app/Contents/MacOS/Python``.
    if name.lower().startswith("python") and WORKER_ARGUMENTS in args:
        return "worker"
    if "Docker.app/" in executable or name.startswith("com.docker."):
        return "docker"
    if name == "ollama":
        return "ollama"
    return "other"


def processes(ps: str, ps_args: str) -> dict[str, dict[str, float | int]]:
    """`ps -Ao pid=,pcpu=,rss=,comm=` (each process's executable) with `ps -Ao pid=,args=` (its
    arguments), joined by pid and summed by kind: how many, total CPU %, total resident MB."""
    arguments = {}
    for line in ps_args.splitlines():
        pid, _, args = line.strip().partition(" ")
        arguments[pid] = args.strip()
    totals = {name: {"count": 0, "cpu_percent": 0.0, "rss_mb": 0.0} for name in (*NAMED, "other")}
    for line in ps.splitlines():
        parts = line.split(None, 3)
        if len(parts) < 4:
            continue
        pid, cpu, rss, executable = parts
        bucket = totals[kind(executable, arguments.get(pid, ""))]
        bucket["count"] += 1
        bucket["cpu_percent"] = round(bucket["cpu_percent"] + float(cpu), 1)
        bucket["rss_mb"] = round(bucket["rss_mb"] + int(rss) / 1024, 1)
    return totals


def docker(run: Run) -> dict[str, Any]:
    try:
        running = run(["docker", "ps", "-q"])
    except (OSError, FileNotFoundError, subprocess.TimeoutExpired) as e:
        # A daemon that hangs answers nothing too: the document is still printed, and says so.
        return {"answers": False, "why": f"{type(e).__name__}: {e}"[:200]}
    return {"answers": True, "containers_running": len(running.split())}


def reading(run: Run = run, now: Callable[[], datetime] = lambda: datetime.now(UTC)) -> dict:
    """Every reading, each its value or ``{"unread": why}``."""

    def taken(read: Callable[[], Any]) -> Any:
        try:
            return read()
        except (OSError, ValueError, FileNotFoundError, subprocess.TimeoutExpired) as e:
            return {"unread": f"{type(e).__name__}: {e}"[:300]}

    return {
        "schema": "squadops.host-quiet-reading/1",
        "recorded_at": now().isoformat(timespec="seconds"),
        "load_average": taken(lambda: load_average(run(["sysctl", "-n", "vm.loadavg"]))),
        "memory_bytes": taken(lambda: memory(run(["vm_stat"]))),
        "memory_free_percent": taken(lambda: free_percent(run(["memory_pressure"]))),
        "models_loaded": taken(lambda: models_loaded(run(["ollama", "ps"]))),
        "docker": docker(run),
        "processes": taken(
            lambda: processes(
                run(["ps", "-Ao", "pid=,pcpu=,rss=,comm="]), run(["ps", "-Ao", "pid=,args="])
            )
        ),
    }


def main() -> int:
    if platform.system() != "Darwin":
        print("host_quiet_reading.py reads the worker's Mac (dev-mac) and runs only there",
              file=sys.stderr)  # fmt: skip
        return 2
    print(json.dumps(reading(), indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
