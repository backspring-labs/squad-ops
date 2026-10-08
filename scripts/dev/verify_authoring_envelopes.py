#!/usr/bin/env python3
"""Verify a run's authoring envelopes byte for byte (SIP-0110 §0.11; #2105).

For each envelope the run recorded, re-run its handler's own prompt construction inside the agent
container of the envelope's role (`authoring_reconstruct.py`), and compare what it would send with
what it sent. An envelope that does not reconstruct exactly is not a replayable case.

    python scripts/dev/verify_authoring_envelopes.py --run run_xxx [--task task-...]

It also reads each envelope's own exposure (SIP-0110 §0.2: one per authoring invocation, joined by
run, task and attempt, #2162). A re-dispatched task is its own invocation, so it needs its own
exposure, not its first attempt's.

Reads `authoring_envelopes` and `memory_exposures` from the deploy's Postgres container. Exits 1
if any envelope is not byte-exact or has no exposure of its own, or if the run recorded none. A run
from before exposures were recorded (2026-10-08 05:18Z) has none, and this says so.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path

_POSTGRES = "squadops-postgres"
#: #1304's attempt stamp, as the captured envelope's inputs carry it.
_PRIOR_ATTEMPTS = "prior_attempts"
_RECONSTRUCT = Path(__file__).resolve().parent / "authoring_reconstruct.py"


def _psql(sql: str) -> str:
    return subprocess.run(
        ["docker", "exec", _POSTGRES, "psql", "-U", "squadops", "-d", "squadops", "-Atc", sql],
        check=True,
        capture_output=True,
        text=True,
    ).stdout


def _envelopes(run_id: str, task_id: str | None) -> list[dict]:
    where = f"run_id = '{run_id}'" + (f" AND task_id = '{task_id}'" if task_id else "")
    if "'" in run_id or (task_id and "'" in task_id):
        raise SystemExit("ids carry no quotes")
    out = _psql(
        "SELECT coalesce(json_agg(envelope ORDER BY captured_at, envelope_id), '[]') "
        f"FROM authoring_envelopes WHERE {where}"
    )
    return json.loads(out or "[]")


def _exposure_ids(run_id: str) -> set[str]:
    out = _psql(
        "SELECT coalesce(json_agg(exposure_id), '[]') FROM memory_exposures "
        f"WHERE run_id = '{run_id}'"
    )
    return set(json.loads(out or "[]"))


def own_exposures(
    run_id: str, envelopes: list[dict], recorded: set[str]
) -> list[tuple[str, int, bool]]:
    """Each envelope's task, its attempt (the stamp of attempts already made, plus one) and
    whether the exposure of that invocation was recorded."""
    from squadops.memory.exposures import exposure_id_for

    rows = []
    for envelope in envelopes:
        task_id = envelope["task_id"]
        attempt = int((envelope.get("inputs") or {}).get(_PRIOR_ATTEMPTS) or 0) + 1
        rows.append((task_id, attempt, exposure_id_for(run_id, task_id, attempt) in recorded))
    return rows


def _container_for(role: str) -> str:
    """The running agent container whose process IS ``role`` (its SQUADOPS_AGENT_ROLE)."""
    names = subprocess.run(
        ["docker", "ps", "--format", "{{.Names}}"], check=True, capture_output=True, text=True
    ).stdout.split()
    for name in names:
        env = subprocess.run(
            ["docker", "exec", name, "printenv", "SQUADOPS_AGENT_ROLE"],
            capture_output=True,
            text=True,
        )
        if env.returncode == 0 and env.stdout.strip() == role:
            return name
    raise SystemExit(f"no running agent container has SQUADOPS_AGENT_ROLE={role}")


def _reconstruct_in(container: str, envelopes: list[dict]) -> list[dict]:
    subprocess.run(
        ["docker", "cp", str(_RECONSTRUCT), f"{container}:/tmp/authoring_reconstruct.py"],
        check=True,
    )
    with tempfile.TemporaryFile("w+") as stdin:
        json.dump(envelopes, stdin)
        stdin.seek(0)
        done = subprocess.run(
            ["docker", "exec", "-i", container, "python", "/tmp/authoring_reconstruct.py"],
            stdin=stdin,
            capture_output=True,
            text=True,
        )
    if not done.stdout.strip():
        raise SystemExit(f"{container}: the reconstruction wrote nothing:\n{done.stderr[-2000:]}")
    return json.loads(done.stdout)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--run", required=True)
    parser.add_argument("--task")
    args = parser.parse_args()

    envelopes = _envelopes(args.run, args.task)
    if not envelopes:
        print(f"{args.run}: no authoring envelopes recorded")
        return 1
    by_role: dict[str, list[dict]] = {}
    for envelope in envelopes:
        by_role.setdefault(envelope["role"], []).append(envelope)
    verdicts: list[dict] = []
    for role, group in sorted(by_role.items()):
        verdicts.extend(_reconstruct_in(_container_for(role), group))

    for v in verdicts:
        mark = "EXACT" if v["byte_exact"] else "DIFFERS"
        detail = v.get("first_difference") or v.get("reason") or ""
        print(
            f"{mark:8} {v['seam']:16} {v['task_type']:38} {v['envelope_bytes']:>9} bytes  "
            f"{v['task_id']}  {json.dumps(detail)[:300] if detail else ''}"
        )
    exact = sum(v["byte_exact"] for v in verdicts)
    print(f"{exact} of {len(verdicts)} envelopes reconstruct byte for byte")

    recorded = _exposure_ids(args.run)
    exposed = own_exposures(args.run, envelopes, recorded)
    for task_id, attempt, present in exposed:
        if not present:
            print(f"NO EXPOSURE  attempt {attempt}  {task_id}")
    own = sum(present for _, _, present in exposed)
    note = "" if recorded else " (the run recorded no exposures: before SIP-0110 slice 3?)"
    print(f"{own} of {len(exposed)} envelopes have their own exposure{note}")
    return 0 if exact == len(verdicts) and own == len(exposed) else 1


if __name__ == "__main__":
    sys.exit(main())
