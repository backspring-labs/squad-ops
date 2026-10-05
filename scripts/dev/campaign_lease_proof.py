#!/usr/bin/env python3
"""The live-lease proof (#1802; #1908 precondition 4), tracked (#1956).

Five steps around a supervisor's approval on a live deploy, proving the box lease holds a launch
for the crew and releases it only when the box is quiet:

1. a short lease is acquired, and a ``cycles create`` is refused ``supervisor_holds_the_box``;
2. the lease expires with a stand-in crew model resident, and a create is refused ``box_not_quiet``;
3. the lease is re-acquired and the increment's ruling approved while it is held: the framing run
   waits (``run_start_waiting_for_box``);
4. the lease is released with the model still resident: the run still waits, and a create is still
   refused ``box_not_quiet``;
5. the model unloads: the framing run starts (``run_start_box_free``).

The refused creates are also read from the audit sink (#560). Each observation goes to the log,
and ``verdict`` names every step that did not hold. Needs a logged-in ``squadops`` CLI, a campaign
paused at an increment's ruling, and the box otherwise idle.

    python scripts/dev/campaign_lease_proof.py --campaign CMP --cycle CYC --proposal-run RUN \\
        --change-request change_request.yaml --idempotency-key KEY --notes "…"
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
_SQUADOPS = str(Path(sys.executable).with_name("squadops"))


def verdict(obs: dict) -> list[str]:
    """Each step that did not hold, by name; ``[]`` when the proof holds."""
    failures = []
    if "supervisor_holds_the_box" not in obs.get("step1_create", ""):
        failures.append(
            "step 1: a create while the lease is held was not refused supervisor_holds_the_box"
        )
    if "box_not_quiet" not in obs.get("step2_create", ""):
        failures.append(
            "step 2: a create after expiry with a model resident was not refused box_not_quiet"
        )
    if "running" in obs.get("step3_framing", "") or not obs.get("step3_waiting"):
        failures.append("step 3: the approved framing run did not wait for the box")
    if "running" in obs.get("step4_framing", ""):
        failures.append("step 4: the framing run started with the model still resident")
    if "box_not_quiet" not in obs.get("step4_create", ""):
        failures.append("step 4: a create with the model resident was not refused box_not_quiet")
    if "running" not in obs.get("step5_framing", "") or not obs.get("step5_free"):
        failures.append("step 5: the framing run did not start once the box was quiet")
    refused = obs.get("audit_refusals", [])
    if len(refused) < 3:
        failures.append(
            f"audit: {len(refused)} refused creates recorded, 3 expected (steps 1, 2, 4)"
        )
    return failures


def _run(*args: str, timeout: int = 120) -> str:
    r = subprocess.run(args, capture_output=True, text=True, timeout=timeout, check=False)
    return (r.stdout + r.stderr).strip()


def _sq(*args: str) -> str:
    return _run(_SQUADOPS, *args)


def _psql(sql: str) -> str:
    return _run(
        "docker",
        "exec",
        "squadops-postgres",
        "psql",
        "-U",
        "squadops",
        "-d",
        "squadops",
        "-At",
        "-F",
        " ",
        "-c",
        sql,
    )


def _ollama(url: str, body: dict) -> None:
    req = urllib.request.Request(
        f"{url}/api/generate", data=json.dumps(body).encode(), method="POST"
    )
    urllib.request.urlopen(req, timeout=300).read()


def _resident(url: str) -> list[str]:
    with urllib.request.urlopen(f"{url}/api/ps", timeout=30) as r:
        return [m["name"] for m in json.load(r)["models"]]


def main(argv: list[str]) -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("--campaign", required=True)
    p.add_argument("--cycle", required=True)
    p.add_argument("--proposal-run", required=True)
    p.add_argument("--change-request", required=True)
    p.add_argument("--idempotency-key", required=True)
    p.add_argument("--notes", required=True)
    p.add_argument("--project", default="group_run")
    p.add_argument("--squad-profile", default="full-38")
    p.add_argument("--request-profile", default="validated-fullstack")
    p.add_argument("--stand-in-model", default="llama3.1:8b")
    p.add_argument("--ollama", default="http://localhost:11434")
    a = p.parse_args(argv)
    out = REPO_ROOT / "var" / "campaigns" / a.campaign / "proofs" / "1802-live-lease-proof.log"
    out.parent.mkdir(parents=True, exist_ok=True)
    log: list[str] = []

    def note(text: str) -> None:
        line = f"{datetime.now(UTC).strftime('%H:%M:%S')}Z {text}"
        log.append(line)
        print(line, flush=True)

    def create() -> str:
        return _sq(
            "cycles",
            "create",
            a.project,
            "--squad-profile",
            a.squad_profile,
            "--request-profile",
            a.request_profile,
            "--notes",
            "#1802 live-lease proof: expected refused",
        )

    def framing() -> str:
        return _psql(
            f"select run_id, status from cycle_runs where cycle_id='{a.cycle}' and workload_type='framing'"
        )

    def runtime_log(since: str, needle: str) -> bool:
        return needle in _run("docker", "logs", "--since", since, "squadops-runtime-api")

    started = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%S")
    obs: dict = {}
    note("step 1: a short lease")
    note(
        _sq(
            "campaigns",
            "lease",
            "acquire",
            a.campaign,
            "--expires-in",
            "120",
            "--reason",
            "#1802 live-lease proof, step 1",
        )
    )
    expires = time.time() + 125
    obs["step1_create"] = create()
    note(f"create: {obs['step1_create'][-200:]}")
    note("step 2: expired, a stand-in model resident")
    _ollama(a.ollama, {"model": a.stand_in_model, "prompt": "", "keep_alive": "2h"})
    note(f"resident: {_resident(a.ollama)}")
    time.sleep(max(0.0, expires - time.time()))
    note(_sq("campaigns", "lease", "show", a.campaign))
    obs["step2_create"] = create()
    note(f"create: {obs['step2_create'][-200:]}")
    note("step 3: re-acquired, the ruling approved while held")
    note(
        _sq(
            "campaigns",
            "lease",
            "acquire",
            a.campaign,
            "--expires-in",
            "1800",
            "--reason",
            "#1802 live-lease proof, step 3",
        )
    )
    note(
        _sq(
            "runs",
            "gate",
            a.project,
            a.cycle,
            a.proposal_run,
            "progress_increment_ruling",
            "--approve",
            "--notes",
            a.notes,
            "--change-request",
            a.change_request,
            "--idempotency-key",
            a.idempotency_key,
        )
    )
    time.sleep(45)
    obs["step3_framing"] = framing()
    obs["step3_waiting"] = runtime_log("2m", "run_start_waiting_for_box")
    note(f"framing: {obs['step3_framing']}; waiting logged: {obs['step3_waiting']}")
    note("step 4: released, the model still resident")
    note(
        _sq(
            "campaigns",
            "lease",
            "release",
            a.campaign,
            "--reason",
            "#1802 live-lease proof, step 4",
        )
    )
    time.sleep(45)
    obs["step4_framing"] = framing()
    obs["step4_create"] = create()
    note(f"framing: {obs['step4_framing']}; create: {obs['step4_create'][-200:]}")
    note("step 5: the model unloaded")
    _ollama(a.ollama, {"model": a.stand_in_model, "keep_alive": 0})
    for _ in range(12):
        obs["step5_framing"] = framing()
        if "running" in obs["step5_framing"]:
            break
        time.sleep(5)
    obs["step5_free"] = runtime_log("2m", "run_start_box_free")
    note(f"framing: {obs['step5_framing']}; box-free logged: {obs['step5_free']}")
    audit = _run(
        "docker",
        "exec",
        "squadops-runtime-api",
        "sh",
        "-c",
        'grep "cycle.launch_refused" "$SQUADOPS_AUDIT_LOG_PATH"',
    )
    obs["audit_refusals"] = [
        f"{d['timestamp']} {d['denial_reason']}"
        for d in (json.loads(line) for line in audit.splitlines() if line.startswith("{"))
        if d["timestamp"] >= started
    ]
    note(f"audit (the #560 sink): {obs['audit_refusals']}")
    failures = verdict(obs)
    note("VERDICT: holds" if not failures else "VERDICT: fails\n  " + "\n  ".join(failures))
    out.write_text("\n".join(log) + "\n")
    print(f"log: {out.relative_to(REPO_ROOT)}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
