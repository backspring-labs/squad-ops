#!/usr/bin/env python3
"""The unified-memory watchdog (SIP-0111 §5.6, #2199; a host service from #2288).

Exhausting the Spark's unified memory can freeze the host, and a frozen host stops everything until someone
reboots it. This runs apart from the switch and the harness, so it acts when they cannot: when MemAvailable
stays under the floor, or swap climbs, it kills TensorFold's container, then runs the restoration
(``engine_switch.py restore``), so Ollama serves and the clients move back rather than point at nothing.
It never starts TensorFold, and it does not touch Ollama while TensorFold is resident.

It runs always, as the host service ``squadops-memory-watchdog`` (``infra/systemd/``, installed once per
machine with ``scripts/dev/ops/install_host_unit.sh``), and acts only while TensorFold runs.

    memory_watchdog.py [--floor-gib 12] [--swap-climb-gib 2] [--interval 2]
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

from engine_switch import RECORDS, TF_CONTAINER

GIB = 2**30
#: One record per watch, named for the moment it began like every engine record, so the release's
#: records carry it (``attach_release_records.py`` takes engine records by the day they began).
LOG = RECORDS / f"{datetime.now(UTC):%Y%m%dT%H%M%SZ}-watchdog.jsonl"
SWITCH = Path(__file__).with_name("engine_switch.py")
#: The restoration waits for a switch in progress (its lock), then moves every client.
RESTORE_TIMEOUT_SECONDS = 3600


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


def act(reason: str) -> None:
    """Kill TensorFold, then restore Ollama (#2288). A restoration that fails is logged and the
    watch goes on: the restoration's own record says what it reached."""
    log("killing_tensorfold", reason=reason)
    subprocess.run(["docker", "kill", TF_CONTAINER], capture_output=True, timeout=60)
    log("killed_tensorfold")
    try:
        proc = subprocess.run(
            [sys.executable, str(SWITCH), "restore"],
            capture_output=True,
            text=True,
            timeout=RESTORE_TIMEOUT_SECONDS,
        )
    except (subprocess.TimeoutExpired, OSError) as exc:
        log("restoration_failed", error=str(exc)[:300])
        return
    # 0: restored and recorded, or nothing to restore; 4: restored, the deploy not recorded.
    event = "restored" if proc.returncode in (0, 4) else "restoration_failed"
    log(event, exit_code=proc.returncode, said=(proc.stdout or proc.stderr).strip()[-300:])


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
        low, swap_base = watch_once(low, swap_base, floor, args.swap_climb_gib * GIB)
        time.sleep(args.interval)


def watch_once(low: int, swap_base: int, floor: float, climb: float) -> tuple[int, int]:
    """One reading: TensorFold killed and Ollama restored when MemAvailable has stayed under the
    floor for two readings, or swap has climbed, while TensorFold runs. Returns the next readings'
    count of low ones and swap baseline."""
    available, swap = meminfo()
    low = low + 1 if available < floor else 0
    climbed = swap - swap_base > climb
    if (low >= 2 or climbed) and tensorfold_running():
        act("memory floor" if low >= 2 else "swap climb")
        time.sleep(10)
        return 0, meminfo()[1]
    if climbed:
        return low, swap  # a climb with nothing of ours to stop: re-baseline, keep watching
    return low, swap_base


if __name__ == "__main__":
    main()
