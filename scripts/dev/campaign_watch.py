#!/usr/bin/env python3
"""Watch a campaign until it needs its supervisor (#1956; the watcher that supervised every 2.0
shakeout and the counted set, until now a session-local script).

Each poll reads one line of live state through the ``squadops`` CLI (the campaign's state, its
newest cycle, that cycle's runs) and prints it when it changes. It exits, printing why, when the
supervisor is needed: the campaign escalated, paused, completed, blocked a launch or awaits a
ruling; a gate stays open across two polls; a run paused or failed.

    python scripts/dev/campaign_watch.py CAMPAIGN_ID [--polls 240] [--interval 60]

Run it in the background; its exit is the signal (CLAUDE.md, the supervisor's runbook).
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

#: The campaign states that need the supervisor (SIP-0109 §13).
_NEEDS_STATES = ("escalated", "paused", "completed", "launch_blocked", "awaiting_ruling")
#: The installed console script beside this interpreter (the venv's ``squadops``).
_SQUADOPS = [str(Path(sys.executable).with_name("squadops")), "--format", "json"]


@dataclass(frozen=True)
class Snapshot:
    """One poll: the campaign's state, its newest cycle, and that cycle's runs in order."""

    state: str
    outcome: str | None
    cycle: str
    runs: tuple[tuple[str, str], ...]  # (workload_type, status)
    gate_open: str | None  # the workload whose completed run awaits a decision

    def line(self) -> str:
        runs = " ".join(f"{w}:{s}" for w, s in self.runs)
        gate = f" GATE_OPEN:{self.gate_open}" if self.gate_open else ""
        return f"{self.state} {self.outcome} | {self.cycle} | {runs}{gate}"


def needs_supervisor(now: Snapshot, gate_seen_before: bool) -> str | None:
    """Why the supervisor is needed now, or ``None``. A gate counts once it has stayed open
    across two polls, so a run between its completion and its gate's recording is not one."""
    if now.state in _NEEDS_STATES:
        return f"campaign {now.state}"
    if now.gate_open and gate_seen_before:
        return f"a gate is open on the {now.gate_open} run"
    for workload, status in now.runs:
        if status in ("paused", "failed"):
            return f"a {workload} run {status}"
    return None


def _cli(*args: str) -> object:
    out = subprocess.run(
        [*_SQUADOPS, *args], capture_output=True, text=True, timeout=60, check=False
    ).stdout
    try:
        return json.loads(out)
    except ValueError:
        return None


def read(campaign_id: str) -> Snapshot | None:
    """A snapshot through the CLI, or ``None`` when it cannot be read (an expired session)."""
    campaign = _cli("campaigns", "show", campaign_id)
    if not isinstance(campaign, dict):
        return None
    project = campaign["project_id"]
    cycles = [
        c for c in (_cli("cycles", "list", project) or []) if c.get("campaign_id") == campaign_id
    ]
    cycles.sort(key=lambda c: c.get("created_at", ""))
    cycle = cycles[-1]["cycle_id"] if cycles else ""
    runs = (
        sorted(_cli("runs", "list", project, cycle) or [], key=lambda r: r.get("run_number", 0))
        if cycle
        else []
    )
    gate = None
    if runs:
        newest = runs[-1]
        if (
            newest.get("status") == "completed"
            and not newest.get("gate_decisions")
            and newest.get("workload_type") != "implementation"
        ):
            gate = newest.get("workload_type")
    return Snapshot(
        state=campaign["state"],
        outcome=campaign.get("outcome"),
        cycle=cycle,
        runs=tuple((r.get("workload_type"), r.get("status")) for r in runs),
        gate_open=gate,
    )


def main(argv: list[str]) -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("campaign_id")
    p.add_argument("--polls", type=int, default=240)
    p.add_argument("--interval", type=int, default=60)
    args = p.parse_args(argv)
    last, gate_seen, blind = "", False, 0
    for _ in range(args.polls):
        stamp = datetime.now(ZoneInfo("America/New_York")).strftime("%H:%M ET")
        now = read(args.campaign_id)
        if now is None:
            blind += 1
            if blind == 3:
                print(f"[{stamp}] UNREADABLE x3: the CLI cannot read the campaign (log in again?)")
            time.sleep(30)
            continue
        blind = 0
        if now.line() != last:
            print(f"[{stamp}] {now.line()}", flush=True)
            last = now.line()
        why = needs_supervisor(now, gate_seen)
        if why:
            print(f"NEEDS THE SUPERVISOR: {why}")
            return 0
        gate_seen = now.gate_open is not None
        time.sleep(args.interval)
    print(f"watch ended after {args.polls} polls")
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
