#!/usr/bin/env python3
"""Who called the engine: TensorFold's request counter by key label, and its two gauges (the 2.5
cut's pre-registration, "The engine's other callers"; the owner chose "2 metrics", 2026-10-29).

The counted set runs beside the crews' load, so a roll is read inconclusive for another caller only
on this evidence, never on assertion. Each reading is one JSON line:

    {"at": "<UTC>", "requests_total": {"<key label>": {"<status>": n}}, "running": n, "waiting": n}

**No key leaves the deploy.** The reader runs inside the runtime image, with the client the runtime
builds from its own config (``create_llm_provider``, the key resolved by its secret provider), and
prints only counts and key *labels*. A label that isn't a short name (``SAFE_LABEL``) is replaced by
a hash of it, so a key written where a label belongs is never printed.

    python scripts/dev/engine_callers.py read                         # one reading
    python scripts/dev/engine_callers.py watch --seconds 3600 --out F # one reading every 5 s

``read`` and ``watch`` run on the host and send this file to the runtime container's Python
(``docker exec -i squadops-runtime-api python - --inside``), as ``read_scenarios.py`` runs there.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import re
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

CONTAINER = "squadops-runtime-api"
#: A key label as #2742's registry writes one: a short name. Anything else is hashed, never printed.
SAFE_LABEL = re.compile(r"^[A-Za-z0-9_.-]{1,32}$")
#: A counter line: its labels (a quoted value may hold ``}``), its value and an optional timestamp.
_COUNTER = re.compile(
    r'^tensorfold:requests_total\{((?:[^}"]|"(?:[^"\\]|\\.)*")*)\}\s+'
    r"([0-9.eE+-]+)(?:\s+-?\d+)?\s*$",
    re.M,
)
_LABEL = re.compile(r'(\w+)="((?:[^"\\]|\\.)*)"')
_GAUGE = re.compile(r"^tensorfold:(requests_running|requests_waiting)\s+([0-9.eE+]+)\s*$", re.M)


def safe_label(value: str) -> str:
    """``value`` if it is a short name, else ``sha256:<12 hex>`` of it."""
    if SAFE_LABEL.fullmatch(value):
        return value
    return "sha256:" + hashlib.sha256(value.encode()).hexdigest()[:12]


def parse_metrics(text: str) -> dict[str, Any]:
    """The counter by key label and status, and the two gauges, from ``/metrics``'s text. A counter
    line with no ``key`` label counts under ``(none)``. Raises when either gauge is missing, since
    an unread gauge is unknown, never zero."""
    counter_lines = [
        line for line in text.splitlines() if line.startswith("tensorfold:requests_total")
    ]
    matched = _COUNTER.findall(text)
    if len(matched) != len(counter_lines):
        # A line the reader can't parse would vanish, and a caller's load read as none.
        raise ValueError(
            f"{len(counter_lines) - len(matched)} of {len(counter_lines)} "
            "tensorfold:requests_total lines couldn't be read"
        )
    totals: dict[str, dict[str, int]] = {}
    for labels, value in matched:
        parsed = dict(_LABEL.findall(labels))
        key = safe_label(parsed["key"]) if "key" in parsed else "(none)"
        status = safe_label(parsed.get("status", "(none)"))
        # Series that differ in another label (a model, a route) are summed, never overwritten.
        by_status = totals.setdefault(key, {})
        by_status[status] = by_status.get(status, 0) + int(float(value))
    gauges = {name: int(float(value)) for name, value in _GAUGE.findall(text)}
    if set(gauges) != {"requests_running", "requests_waiting"}:
        raise ValueError("TensorFold's /metrics reports no request gauges")
    return {
        "requests_total": totals,
        "running": gauges["requests_running"],
        "waiting": gauges["requests_waiting"],
    }


async def _inside() -> dict[str, Any]:
    """In the runtime image: ``/metrics`` through the runtime's own TensorFold client."""
    from adapters.llm.factory import create_llm_provider
    from squadops.bootstrap.secrets import secret_provider_for
    from squadops.config import load_config

    config = load_config(strict=False, secret_provider_factory=secret_provider_for)
    if config.llm.provider != "tensorfold":
        raise SystemExit(f"the runtime's engine is {config.llm.provider!r}, not tensorfold")
    adapter = create_llm_provider(
        provider=config.llm.provider,
        base_url=config.llm.url,
        default_model=config.llm.model or "unused",
        timeout_seconds=float(config.llm.timeout),
        api_key=config.llm.api_key,
    )
    client = await adapter._get_client()
    response = await client.get("/metrics", timeout=10.0)
    if response.status_code != 200:
        raise SystemExit(f"/metrics answered {response.status_code}")
    return parse_metrics(response.text)


def read_once() -> dict[str, Any]:
    """One reading, taken inside the runtime container."""
    done = subprocess.run(
        ["docker", "exec", "-i", "-w", "/app", CONTAINER, "python", "-", "--inside"],
        input=Path(__file__).read_text(),
        capture_output=True,
        text=True,
        timeout=60,
    )
    if done.returncode != 0:
        # Never the container's own words: an error there could echo a configured value.
        raise SystemExit(f"the reading failed inside {CONTAINER} (exit {done.returncode})")
    lines = done.stdout.strip().splitlines()
    if not lines:
        raise SystemExit(f"the reading inside {CONTAINER} printed nothing")
    reading = json.loads(lines[-1])
    return {"at": datetime.now(UTC).isoformat(timespec="seconds"), **reading}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--inside", action="store_true", help=argparse.SUPPRESS)
    sub = ap.add_subparsers(dest="command")
    sub.add_parser("read", help="one reading, printed as a JSON line")
    watch = sub.add_parser("watch", help="a reading every --interval seconds, appended to --out")
    watch.add_argument("--seconds", type=int, required=True)
    watch.add_argument("--interval", type=float, default=5.0)
    watch.add_argument("--out", type=Path, required=True)
    args = ap.parse_args(argv)

    if args.inside:
        print(json.dumps(asyncio.run(_inside()), sort_keys=True))
        return 0
    if args.command == "read":
        print(json.dumps(read_once(), sort_keys=True))
        return 0
    if args.command == "watch":
        # A failed reading is a gap the record shows, never a silent end: a watch that died would
        # read as "no other caller" for the rest of its window. Exit 1 if any reading failed.
        end = time.monotonic() + args.seconds
        gaps = 0
        with args.out.open("a") as out:
            while time.monotonic() < end:
                try:
                    line = read_once()
                except (SystemExit, subprocess.TimeoutExpired, ValueError) as e:
                    gaps += 1
                    line = {
                        "at": datetime.now(UTC).isoformat(timespec="seconds"),
                        "error": type(e).__name__,
                    }
                out.write(json.dumps(line, sort_keys=True) + "\n")
                out.flush()
                time.sleep(args.interval)
        return 1 if gaps else 0
    ap.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main())
