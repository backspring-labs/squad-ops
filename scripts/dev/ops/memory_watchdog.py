#!/usr/bin/env python3
"""The unified-memory watchdog for unattended engine runs (SIP-0111 §5.6, #2199).

Exhausting the Spark's unified memory can freeze the host, and a frozen host stops everything until someone
reboots it. This runs apart from the switch and the harness, so it acts when they cannot: when MemAvailable
stays under the floor, or swap climbs, it kills TensorFold's container and lets restoration start Ollama.
It never starts TensorFold, and it does not touch Ollama while TensorFold is resident.

    memory_watchdog.py [--floor-gib 12] [--swap-climb-gib 2] [--interval 2]
"""

from __future__ import annotations

import argparse
import json
import subprocess
import time
from datetime import UTC, datetime
from pathlib import Path

from engine_switch import RECORDS, TF_CONTAINER

GIB = 2**30
#: One record per watch, named for the moment it began like every engine record, so the release's
#: records carry it (``attach_release_records.py`` takes engine records by the day they began).
LOG = RECORDS / f"{datetime.now(UTC):%Y%m%dT%H%M%SZ}-watchdog.jsonl"


def meminfo() -> tuple[int, int]:
    info = {}
    for line in Path("/proc/meminfo").read_text().splitlines():
        key, value = line.split(":", 1)
        info[key] = int(value.split()[0]) * 1024
    return info["MemAvailable"], info["SwapTotal"] - info["SwapFree"]


def log(event: str, **fields) -> None:
    LOG.parent.mkdir(parents=True, exist_ok=True)
    available, swap = meminfo()
    line = {
        "at": datetime.now(UTC).isoformat(timespec="seconds"),
        "event": event,
        "mem_available_gib": round(available / GIB, 1),
        "swap_used_gib": round(swap / GIB, 2),
        **fields,
    }
    with LOG.open("a") as f:
        f.write(json.dumps(line) + "\n")


def tensorfold_running() -> bool:
    proc = subprocess.run(
        ["docker", "inspect", "-f", "{{.State.Running}}", TF_CONTAINER],
        capture_output=True,
        text=True,
    )
    return proc.returncode == 0 and proc.stdout.strip() == "true"


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--floor-gib", type=float, default=12.0)
    parser.add_argument("--swap-climb-gib", type=float, default=2.0)
    parser.add_argument("--interval", type=float, default=2.0)
    args = parser.parse_args()
    floor = args.floor_gib * GIB
    _, swap_base = meminfo()
    low = 0
    log("watching", floor_gib=args.floor_gib, swap_base_gib=round(swap_base / GIB, 2))
    while True:
        available, swap = meminfo()
        low = low + 1 if available < floor else 0
        climbed = swap - swap_base > args.swap_climb_gib * GIB
        if (low >= 2 or climbed) and tensorfold_running():
            log("killing_tensorfold", reason="memory floor" if low >= 2 else "swap climb")
            subprocess.run(["docker", "kill", TF_CONTAINER], capture_output=True, timeout=60)
            log("killed_tensorfold")
            low = 0
            time.sleep(10)
            _, swap_base = meminfo()
        elif climbed:
            swap_base = swap  # a climb with nothing of ours to stop: re-baseline, keep watching
        time.sleep(args.interval)


if __name__ == "__main__":
    main()
