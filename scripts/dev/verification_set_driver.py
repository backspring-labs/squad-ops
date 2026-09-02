#!/usr/bin/env python3
"""Verification-set driver — ONE roll per invocation, facts only.

Promoted from the session scratchpad that drove the 1.6.3 and 1.6.4 sets (sixteen
counted rolls and three shakeouts), with the two defects those sets recorded against it
fixed and its assumptions moved out of the code:

* **No fixed parameters in the code.** Project, squad, request profile, overrides, the
  frozen deploy's identity, the gate constant and the launch notes all come from a
  set-config YAML (``--set``) — the pre-registration's §1 table as data, committed
  beside the pre-registration it belongs to. The scratchpad copies carried them as
  constants and were hand-edited per set.
* **The stack is a fact of the cycle, not of the driver.** It is derived from the
  request profile's defaults and the overrides, and the P0 static checks dispatch on
  it. A stack with no registered P0 check is refused loudly, never silently passed
  (the #818 rule). The scratchpad opened ``lib/models.ts`` unconditionally.
* **The log window is UTC-explicit.** ``docker logs --since`` read the wrong window
  because the timestamp carried no zone (1.6.4 record §4, "instrument defect").

Deliberately not a loop over a set: §5.1's *reset* rule requires someone to NOTICE a new
harness-attributable failure, so everything mechanical is automated and the scoring
decision — counted / void / reset — is left at the roll boundary, where a reader is. It
does not judge: it collects what happened and renders it; the pre-registration says
what those facts mean.

Usage:
    .venv/bin/python scripts/dev/verification_set_driver.py preflight --set <yaml>
    .venv/bin/python scripts/dev/verification_set_driver.py shakeout  --set <yaml> [--dry-run]
    .venv/bin/python scripts/dev/verification_set_driver.py roll      --set <yaml> --roll N [--dry-run]

``shakeout`` is NON-COUNTING by declaration: it records the deploy's identity instead of
asserting it (first cycle on new images — nothing to hold to yet). ``roll`` asserts the
frozen image ids, pins HEAD on roll 1 and holds it, and asserts the config hash.

The procedure around this script — the shakeout loop and its exit rule, what a diagnostic
must be, how a launch survives the session, how a dead driver is re-attached — is
``docs/plans/verification-sets/README.md``.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shlex
import subprocess
import sys
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml

REPO = Path(__file__).resolve().parents[2]
SQUADOPS = str(REPO / ".venv" / "bin" / "squadops")
PYTHON = str(REPO / ".venv" / "bin" / "python")

#: docker-compose service names (fixed by docker-compose.yml; CLAUDE.md forbids renaming).
AGENT_SERVICES = ("max", "neo", "nat", "bob", "eve", "data")
DEPLOY_SERVICES = ("runtime-api", *AGENT_SERVICES)
POSTGRES_CONTAINER = "squadops-postgres"
RUNTIME_API_CONTAINER = "squadops-runtime-api"

POLL_S = 30
MAX_WAIT_S = 4 * 60 * 60


# ---------------------------------------------------------------------------
# Set config — the pre-registration's §1 as data
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SetConfig:
    name: str
    project: str
    squad_profile: str
    request_profile: str
    gate_name: str
    #: Copied verbatim onto every gate approval — NO substitution of any kind (§6).
    gate_notes: str
    #: The only formatting the driver does: ``{roll}`` and ``{n}``.
    launch_notes: str
    shakeout_notes: str
    n_rolls: int
    overrides: dict[str, str] = field(default_factory=dict)
    #: Empty = record, do not assert (a shakeout on a fresh deploy).
    expected_config_hash_prefix: str = ""
    #: The squad-profile snapshot the set is frozen on. A per-agent override (1.6.5 E:
    #: eve's completion budget) moves THIS identity and leaves resolved_config_hash — the
    #: request-profile side — untouched; a set that asserted only the latter would accept
    #: a roll on a different squad configuration.
    expected_squad_snapshot_prefix: str = ""
    frozen_deploy_commit: str = ""
    frozen_image_ids: dict[str, str] = field(default_factory=dict)
    #: ``{service: python_source}`` — "loaded, not built": run inside the container and
    #: recorded with the deploy identity (the pre-registration's own list, as data).
    loaded_checks: dict[str, str] = field(default_factory=dict)
    records_dir: str = ""
    pre_registration: str = ""

    @property
    def records_path(self) -> Path:
        # var/ is gitignored and user-writable; data/ is the docker volume, owned by root —
        # the first launch died on mkdir there before it created anything.
        return (
            Path(self.records_dir)
            if self.records_dir
            else REPO / "var" / "verification_sets" / self.name
        )

    @property
    def head_pin(self) -> Path:
        return self.records_path / ".head_pin"


_REQUIRED = (
    "name",
    "project",
    "squad_profile",
    "request_profile",
    "gate_name",
    "gate_notes",
    "launch_notes",
    "shakeout_notes",
    "n_rolls",
)


def load_set_config(path: Path) -> SetConfig:
    raw = yaml.safe_load(path.read_text()) or {}
    missing = [k for k in _REQUIRED if k not in raw]
    if missing:
        raise SystemExit(f"{path}: set config is missing {', '.join(missing)}")
    overrides = {str(k): str(v) for k, v in (raw.get("overrides") or {}).items()}
    image_ids = {str(k): str(v) for k, v in (raw.get("frozen_image_ids") or {}).items()}
    unknown = sorted(set(image_ids) - set(DEPLOY_SERVICES))
    if unknown:
        raise SystemExit(f"{path}: frozen_image_ids names unknown services {unknown}")
    return SetConfig(
        name=str(raw["name"]),
        project=str(raw["project"]),
        squad_profile=str(raw["squad_profile"]),
        request_profile=str(raw["request_profile"]),
        gate_name=str(raw["gate_name"]),
        gate_notes=str(raw["gate_notes"]).strip(),
        launch_notes=str(raw["launch_notes"]).strip(),
        shakeout_notes=str(raw["shakeout_notes"]).strip(),
        n_rolls=int(raw["n_rolls"]),
        overrides=overrides,
        expected_config_hash_prefix=str(raw.get("expected_config_hash_prefix") or ""),
        expected_squad_snapshot_prefix=str(raw.get("expected_squad_snapshot_prefix") or ""),
        frozen_deploy_commit=str(raw.get("frozen_deploy_commit") or ""),
        frozen_image_ids=image_ids,
        loaded_checks={str(k): str(v) for k, v in (raw.get("loaded_checks") or {}).items()},
        records_dir=str(raw.get("records_dir") or ""),
        pre_registration=str(raw.get("pre_registration") or ""),
    )


def render_launch_notes(template: str, roll: int, n: int) -> str:
    """``{roll}`` and ``{n}`` only — never ``str.format`` on text that may carry braces."""
    return template.replace("{roll}", str(roll)).replace("{n}", str(n))


# ---------------------------------------------------------------------------
# The stack is the cycle's fact
# ---------------------------------------------------------------------------


def derive_stack(profile_defaults: Mapping[str, Any], overrides: Mapping[str, str]) -> str:
    """``build_profile`` from the overrides, else the request profile's defaults.

    Refuses rather than guesses: a driver that assumed a stack opened ``lib/models.ts``
    on every cycle, which is exactly wrong for stack #1.
    """
    stack = overrides.get("build_profile") or profile_defaults.get("build_profile")
    if not stack:
        raise SystemExit(
            "cannot derive the stack: no build_profile in overrides or profile defaults"
        )
    return str(stack)


def stack_for(cfg: SetConfig) -> str:
    from squadops.contracts.cycle_request_profiles import load_profile

    return derive_stack(load_profile(cfg.request_profile).defaults, cfg.overrides)


# ---------------------------------------------------------------------------
# Shell / evidence helpers
# ---------------------------------------------------------------------------


def sh(cmd: str, check: bool = True) -> str:
    proc = subprocess.run(shlex.split(cmd), capture_output=True, text=True)
    if check and proc.returncode != 0:
        raise SystemExit(f"FAILED: {cmd}\n{proc.stdout}\n{proc.stderr}")
    return proc.stdout.strip()


def psql(query: str) -> str:
    return sh(
        f"docker exec {POSTGRES_CONTAINER} psql -U squadops -d squadops -tAc " + shlex.quote(query)
    )


def log(msg: str) -> None:
    print(f"[{datetime.now(UTC).strftime('%H:%M:%S')}Z] {msg}", flush=True)


def log_since(moment: datetime) -> str:
    """RFC 3339 with an explicit zone — what ``docker logs --since`` needs.

    The scratchpad driver passed ``%Y-%m-%dT%H:%M:%S`` with no zone; docker read it in
    the daemon's local time and the P4/P5 windows came back empty (1.6.4 record §4).
    """
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=UTC)
    return moment.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def login() -> None:
    """Refresh the token immediately before any state-changing call — it expires in minutes,
    and gate approvals land hours after launch. Do NOT pass --keycloak-url (the override
    logs in at Keycloak and then 401s on every API call; silent at login)."""
    user = os.environ.get("SQUADOPS_DRIVER_USER", "squadops-admin")
    password = os.environ.get("SQUADOPS_DRIVER_PASSWORD", "admin123")
    sh(f"{SQUADOPS} login -u {shlex.quote(user)} -p {shlex.quote(password)}")


def image_id(service: str) -> str:
    return sh(f"docker inspect --format={{{{.Image}}}} squadops-{service}", check=False)[7:19]


def deploy_identity(cfg: SetConfig) -> dict[str, str]:
    ids = {s: image_id(s) for s in DEPLOY_SERVICES}
    ids["head"] = sh(f"git -C {REPO} rev-parse --short HEAD")
    for service, source in cfg.loaded_checks.items():
        # A failed check must say WHY: an ImportError here is the "rebuild exited 0 with
        # stale images" signal, and an empty string reads as "nothing to report".
        proc = subprocess.run(
            ["docker", "exec", f"squadops-{service}", "python", "-c", source],
            capture_output=True,
            text=True,
        )
        err = (proc.stderr or "").strip().splitlines()
        ids[f"{service}:loaded"] = (
            proc.stdout.strip()
            if proc.returncode == 0
            else (f"ERROR: {err[-1] if err else f'exit {proc.returncode}'}")
        )
    return ids


# ---------------------------------------------------------------------------
# Preflight — §2.6 and the freeze, at EVERY launch
# ---------------------------------------------------------------------------


def preflight(cfg: SetConfig, *, counting: bool) -> list[str]:
    problems: list[str] = []
    leases = psql("select count(*) from focus_leases where released_at is null;")
    if leases != "0":
        problems.append(f"§2.6: {leases} unreleased focus leases (must be 0) — #529 deadlock risk")
    running = psql("select count(*) from cycle_runs where status='running';")
    if running != "0":
        problems.append(f"§2.6: {running} runs already in flight (the GPU is not shareable)")
    dirty = sh(f"git -C {REPO} status --porcelain")
    if dirty:
        problems.append(f"§7: working tree is dirty ({len(dirty.splitlines())} files)")
    if not counting:
        return problems
    if not cfg.frozen_image_ids:
        problems.append(
            "counting roll with no frozen_image_ids in the set config — pre-register the deploy first"
        )
    for service, expected in cfg.frozen_image_ids.items():
        actual = image_id(service)
        if actual != expected:
            problems.append(
                f"§7 DEPLOY CHANGED: squadops-{service} is image {actual or '?'}, the set is "
                f"frozen on {expected}. A rebuild mid-set voids comparability."
            )
    head = sh(f"git -C {REPO} rev-parse --short HEAD")
    if cfg.head_pin.exists():
        pinned = cfg.head_pin.read_text().strip()
        if head != pinned:
            problems.append(
                f"§7 MERGE DURING THE SET: HEAD is {head}, pinned at {pinned} when roll 1 launched. "
                "Abort and re-register rather than continuing."
            )
    else:
        log(f"pinning HEAD at {head} — §7 binds from here")
    return problems


# ---------------------------------------------------------------------------
# Launch and drive
# ---------------------------------------------------------------------------


def launch(cfg: SetConfig, notes: str) -> tuple[str, str, str]:
    login()
    sets = " ".join(f"--set {k}={v}" for k, v in cfg.overrides.items())
    out = sh(
        f"{SQUADOPS} cycles create {cfg.project} --squad-profile {cfg.squad_profile} "
        f"--request-profile {cfg.request_profile} {sets} --notes {shlex.quote(notes)}"
    )
    cyc = re.search(r"(cyc_[0-9a-f]+)", out)
    run = re.search(r"(run_[0-9a-f]+)", out)
    chash = re.search(r"hash:\s*([0-9a-f]+)", out)
    if not (cyc and run):
        raise SystemExit(f"could not parse create output:\n{out}")
    return cyc.group(1), run.group(1), (chash.group(1) if chash else "")


def gate_pending(cycle_id: str) -> str | None:
    """The framing run awaiting a decision, if any. Keys on the WAITING state."""
    got = psql(
        f"select r.run_id from cycle_runs r where r.cycle_id='{cycle_id}' and r.workload_type='framing' "
        "and r.status='completed' and not exists "
        "(select 1 from cycle_gate_decisions g where g.run_id=r.run_id);"
    )
    return got or None


def terminal_impl(cycle_id: str) -> str | None:
    status = psql(
        f"select status from cycle_runs where cycle_id='{cycle_id}' and workload_type='implementation' "
        "order by run_number desc limit 1;"
    )
    active = psql(
        f"select count(*) from cycle_runs where cycle_id='{cycle_id}' and status='running';"
    )
    return status if status and status != "running" and active == "0" else None


def ended_without_implementation(cycle_id: str) -> str | None:
    """``"<status>: <reason>"`` once the cycle has stopped without ever creating an
    implementation run, else None.

    **Why this exists (#1168).** ``terminal_impl`` only ever reports on an implementation
    run. A cycle whose framing fails never creates one, so it returned None on every poll
    and ``drive`` span for the full four-hour ``MAX_WAIT_S`` — no record written, the
    watcher never woken, and the next set's preflight blocked behind a process that would
    not exit. Measured on the 1.7.0 Atlas shakeout ``cyc_6e068cdd7de0`` (2026-08-28,
    framing failed at ``governance.prepare_plan_authoring_brief``); killed by hand.

    Named for the condition rather than for ``framing_failed`` as #1168 sketched it,
    because a framing that is *cancelled* reaches this state too and did so 32 times in
    the run table — calling that a failure would put a wrong word in a banked record.

    The three clauses are ordered cheapest-first and each is load-bearing: an
    implementation run existing at all means ``terminal_impl`` owns the answer; anything
    running or queued means the cycle may still create one; and only then is a run that
    ended ``failed``/``cancelled`` the reason it never will. A framing sitting
    ``completed`` at an open gate matches none of them, so the gate loop keeps its turn.
    """
    if (
        psql(
            f"select count(*) from cycle_runs where cycle_id='{cycle_id}' "
            "and workload_type='implementation';"
        )
        != "0"
    ):
        return None
    if (
        psql(
            f"select count(*) from cycle_runs where cycle_id='{cycle_id}' "
            "and status in ('running','queued');"
        )
        != "0"
    ):
        return None
    return (
        psql(
            "select status||': '||coalesce(nullif(failure_reason,''),'no failure_reason recorded') "
            f"from cycle_runs where cycle_id='{cycle_id}' and status in ('failed','cancelled') "
            "order by run_number desc limit 1;"
        )
        or None
    )


def drive(cfg: SetConfig, cycle_id: str) -> str | None:
    """Approve the gate (§6 constant, verbatim) when it opens; return once the cycle can
    produce nothing further. Returns the reason when it ended with no implementation run
    (#1168), None on the ordinary path."""
    started = time.time()
    approved: set[str] = set()
    while time.time() - started < MAX_WAIT_S:
        pending = gate_pending(cycle_id)
        if pending and pending not in approved:
            log(f"gate open on {pending} — applying the §6 constant")
            login()
            sh(
                f"{SQUADOPS} runs gate {cfg.project} {cycle_id} {pending} {cfg.gate_name} "
                f"--approve --as-agent --notes {shlex.quote(cfg.gate_notes)}"
            )
            approved.add(pending)
            continue
        done = terminal_impl(cycle_id)
        if done:
            log(f"implementation run terminal: {done}")
            return None
        red = ended_without_implementation(cycle_id)
        if red:
            log(f"cycle ended with no implementation run — {red}")
            return red
        time.sleep(POLL_S)
    raise SystemExit(f"driver timed out after {MAX_WAIT_S}s on {cycle_id}")


# ---------------------------------------------------------------------------
# Collect — the per-roll record
# ---------------------------------------------------------------------------


def artifact_dirs(cfg: SetConfig, cycle_id: str, run_id: str) -> list[Path]:
    root = REPO / "data" / "artifacts" / cfg.project / cycle_id / run_id
    return sorted(root.glob("art_*")) if root.exists() else []


def _metadata(art: Path) -> dict | None:
    meta = art / "metadata.json"
    if not meta.exists():
        return None
    try:
        return json.loads(meta.read_text())
    except (OSError, ValueError):
        return None


def artifact_text(
    cfg: SetConfig,
    cycle_id: str,
    run_id: str,
    filename: str,
    producing_task_type: str | None = None,
) -> str | None:
    for art in artifact_dirs(cfg, cycle_id, run_id):
        m = _metadata(art)
        if not m or m.get("filename") != filename:
            continue
        if (
            producing_task_type
            and (m.get("metadata") or {}).get("producing_task_type") != producing_task_type
        ):
            continue
        try:
            return (REPO / m["vault_uri"]).read_text()
        except (OSError, KeyError):
            return None
    return None


def parse_run_rows(text: str) -> list[dict]:
    runs = []
    for r in text.splitlines():
        num, wtype, status, reason, run_id, secs = (r.split("|") + [""] * 6)[:6]
        if not num:
            continue
        runs.append(
            {
                "run_number": int(num),
                "workload": wtype,
                "status": status,
                "failure_reason": reason,
                "run_id": run_id,
                "seconds": int(secs or 0),
            }
        )
    return runs


def completed_framing_run(cycle_id: str) -> str | None:
    """The framing run that was APPROVED — never `head -1` (a rejected framing's contract
    once produced a spurious audit FAIL against endpoints the deliverable never had)."""
    return (
        psql(
            "select g.run_id from cycle_gate_decisions g join cycle_runs r on r.run_id=g.run_id "
            f"where r.cycle_id='{cycle_id}' and g.decision='approved' order by g.decided_at desc limit 1;"
        )
        or None
    )


def collect(cfg: SetConfig, cycle_id: str) -> dict:
    runs = parse_run_rows(
        psql(
            "select run_number||'|'||workload_type||'|'||status||'|'||coalesce(failure_reason,'')||'|'"
            "||run_id||'|'||extract(epoch from (finished_at-started_at))::int "
            f"from cycle_runs where cycle_id='{cycle_id}' order by run_number;"
        )
    )
    impl = next((r for r in reversed(runs) if r["workload"] == "implementation"), None)
    framings = [r for r in runs if r["workload"] == "framing"]
    gates = psql(
        "select g.gate_name||'|'||g.decision||'|'||g.decided_by from cycle_gate_decisions g "
        f"join cycle_runs r on r.run_id=g.run_id where r.cycle_id='{cycle_id}' order by g.decided_at;"
    ).splitlines()
    summary: dict = {}
    corrections = failed_emissions = 0
    if impl:
        raw = psql(
            "select summary from run_verification_summaries where run_id='{}';".format(
                impl["run_id"]
            )
        )
        try:
            summary = json.loads(raw) if raw else {}
        except ValueError:
            summary = {}
        for art in artifact_dirs(cfg, cycle_id, impl["run_id"]):
            m = _metadata(art)
            if not m:
                continue
            if m.get("filename") == "correction_decision.md":
                corrections += 1
            if (m.get("metadata") or {}).get("emission_status") == "failed":
                failed_emissions += 1
    snapshot = psql(
        f"select coalesce(squad_profile_snapshot_ref,'') from cycle_registry where cycle_id='{cycle_id}';"
    )
    return {
        "cycle_id": cycle_id,
        "squad_profile_snapshot_ref": snapshot,
        "runs": runs,
        "gate_decisions": [
            dict(zip(("gate", "decision", "decided_by"), g.split("|"), strict=False)) for g in gates
        ],
        "framing_runs": len(framings),
        "framing_rerolls": max(0, len(framings) - 1),
        "correction_rounds": corrections,
        "failed_emissions_banked": failed_emissions,
        "verdict": summary.get("verdict"),
        "failed_checks": summary.get("failed", []),
        "criteria_total": len(summary.get("criteria_total", []) or []),
        "criteria_verified": len(summary.get("criteria_verified", []) or []),
        "criteria_unevidenced": summary.get("criteria_unevidenced", []) or [],
        "wall_clock_seconds": sum(r["seconds"] for r in runs),
        "impl_run_id": impl["run_id"] if impl else None,
    }


def boot_audit(cfg: SetConfig, cycle_id: str, impl_run: str) -> dict:
    framing = completed_framing_run(cycle_id)
    if not framing:
        return {"ran": False, "reason": "no approved framing run — no contract to audit against"}
    contract = None
    for art in artifact_dirs(cfg, cycle_id, framing):
        m = _metadata(art)
        if m and m.get("filename") == "verification_contract.yaml":
            contract = art / "verification_contract.yaml"
            break
    if contract is None:
        return {"ran": False, "reason": f"no verification_contract.yaml under framing {framing}"}
    log(f"boot audit against the APPROVED framing's contract ({framing})")
    proc = subprocess.run(
        [
            PYTHON,
            "scripts/dev/audit_delivered_app.py",
            cycle_id,
            impl_run,
            "--contract",
            str(contract),
            "--project",
            cfg.project,
        ],
        capture_output=True,
        text=True,
        cwd=REPO,
    )
    tail = (proc.stdout or proc.stderr).strip().splitlines()
    return {
        "ran": True,
        "passed": proc.returncode == 0,
        "exit_code": proc.returncode,
        "contract_from": framing,
        "detail": tail[-1] if tail else "",
    }


# ---------------------------------------------------------------------------
# P0 — the seeded frozen tree against the manifest, per stack, no model in the loop
# ---------------------------------------------------------------------------

Reader = Callable[[str], str | None]


def _p0_nextjs_ts(manifest: Any, seeded: Reader) -> dict:
    from squadops.capabilities.scaffold import root_persisted_entities
    from squadops.capabilities.stack_nextjs_ts import _ts_type

    models = seeded("lib/models.ts") or ""
    store = seeded("lib/store.ts") or ""
    harness = seeded("__tests__/harness.test.ts") or ""
    declared = frozenset(
        [e.name for e in manifest.entities] + [s.name for s in manifest.api.request_shapes]
    )
    expected, mismatches = [], []
    for entity in manifest.entities:
        for f in entity.fields:
            if f.type.strip().lower().startswith("list["):
                want = f"{f.name}{'' if f.required else '?'}: {_ts_type(f.type, declared)}"
                expected.append(want)
                if want not in models:
                    mismatches.append(want)
    roots = list(root_persisted_entities(manifest))
    tables = re.findall(r"^\s+(\w+): '", store, re.M)
    harness_table = (re.findall(r"TABLES\.(\w+)", harness) or [None])[0]
    return {
        "stack": "nextjs_ts",
        "asserted": True,
        "models_expected_collection_lines": expected,
        "models_mismatches": mismatches,
        "p0_models_entity_typed": not mismatches,
        "store_tables": tables,
        "root_persisted_entities": roots,
        "p0_store_root_only": tables == roots,
        "harness_table": harness_table,
        "p0_harness_root": harness_table in roots,
        "passed": not mismatches and tables == roots and harness_table in roots,
    }


def _p0_fullstack_fastapi_react(manifest: Any, seeded: Reader) -> dict:
    """Stack #1's seeded tree against its manifest.

    Asserted: every collection field in ``backend/models.py`` carries the manifest's
    element type (``_py_type`` passes entity names through — the #1096 class cannot
    recur here, and this is where that stays true). Recorded, NOT asserted: the store
    exports one dict per declared entity by design (#1087's stack #1 half is open), so
    ``stores_beyond_roots`` is texture for the roll that finally measures it.
    """
    from squadops.capabilities.scaffold import root_persisted_entities
    from squadops.capabilities.stack_fastapi_react import _py_type

    models = seeded("backend/models.py") or ""
    store = seeded("backend/store.py") or ""
    expected, mismatches = [], []
    nullable_expected, nullable_mismatches = [], []
    for entity in manifest.entities:
        for f in entity.fields:
            if f.type.strip().lower().startswith("list["):
                want = f"{f.name}: {_py_type(f.type)}"
                expected.append(want)
                if want not in models:
                    mismatches.append(want)
            elif (not f.required) or (f.has_default and f.default is None):
                # #1125 (1.6.6 A, prediction R1): an optional field — declared
                # ``required: false`` or ``default: null`` — freezes nullable. The
                # ``str = None`` form pydantic rejects sat under five of six 1.6.5 rolls.
                want = f"{f.name}: {_py_type(f.type)} | None = None"
                nullable_expected.append(want)
                if want not in models:
                    nullable_mismatches.append(want)
    roots = list(root_persisted_entities(manifest))
    stores = re.findall(r"^(\w+)_store:", store, re.M)
    return {
        "stack": "fullstack_fastapi_react",
        "asserted": True,
        "models_expected_collection_lines": expected,
        "models_mismatches": mismatches,
        "p0_models_entity_typed": not mismatches,
        "models_nullable_expected_lines": nullable_expected,
        "models_nullable_mismatches": nullable_mismatches,
        "p0_optional_fields_nullable": not nullable_mismatches,
        "store_names": stores,
        "root_persisted_entities": roots,
        "stores_beyond_roots": sorted(set(stores) - {_snake(r) for r in roots}),
        "passed": not mismatches and not nullable_mismatches,
    }


def _snake(name: str) -> str:
    return re.sub(r"(?<!^)(?=[A-Z])", "_", name).lower()


_P0_CHECKS: dict[str, Callable[[Any, Reader], dict]] = {
    "nextjs_ts": _p0_nextjs_ts,
    "fullstack_fastapi_react": _p0_fullstack_fastapi_react,
}


def p0_checks(stack: str, manifest: Any, seeded: Reader) -> dict:
    """Dispatch the seeded-tree check on the cycle's stack; refuse an unregistered one."""
    check = _P0_CHECKS.get(stack)
    if check is None:
        return {
            "stack": stack,
            "asserted": False,
            "passed": False,
            "refused": f"no P0 check registered for stack {stack!r} — register one, do not skip",
        }
    if manifest is None:
        return {
            "stack": stack,
            "asserted": False,
            "passed": False,
            "refused": "no interface_manifest.yaml found under the framing or implementation run",
        }
    return check(manifest, seeded)


def static_checks(
    cfg: SetConfig, stack: str, cycle_id: str, impl_run: str | None, framing_run: str | None
) -> dict:
    from squadops.capabilities.scaffold import InterfaceManifest

    out: dict = {}
    manifest = None
    for run in (impl_run, framing_run):
        text = artifact_text(cfg, cycle_id, run, "interface_manifest.yaml") if run else None
        if text:
            manifest = InterfaceManifest.from_yaml(text)
            break
    if impl_run:
        out["p0"] = p0_checks(
            stack,
            manifest,
            lambda name: artifact_text(
                cfg, cycle_id, impl_run, name, producing_task_type="scaffold.expand"
            ),
        )
    if framing_run:
        contract = artifact_text(cfg, cycle_id, framing_run, "verification_contract.yaml")
        out["contract_json_has_probes"] = contract.count("json_has:") if contract else None
        # 1.6.6 R5 (#1128): no POST probe on an endpoint that declares a request body ships {}.
        out["empty_body_probes"] = (
            empty_body_probes(manifest, contract) if contract and manifest is not None else None
        )
    if impl_run:
        # 1.6.6 R2 (#1127): no stored report fails "Found multiple elements".
        out["multiple_elements_reports"] = _report_scan(
            cfg, cycle_id, impl_run, "Found multiple elements"
        )
    return out


def empty_body_probes(manifest: Any, contract_text: str) -> list[str]:
    """Ids of POST probes that carry ``json: {}`` on an endpoint whose manifest declares a
    ``request:`` — the shape that made 1.6.5 FastAPI+React roll 3 unsatisfiable (#1128)."""
    paths_with_request = {ep.path for ep in manifest.api.endpoints if ep.request}
    try:
        contract = yaml.safe_load(contract_text) or {}
    except yaml.YAMLError:
        return ["<contract unparseable>"]
    probes = ((contract.get("behavioral") or {}).get("probes")) or []
    return [
        str(p.get("id"))
        for p in probes
        if isinstance(p, dict)
        and (p.get("request") or {}).get("method") == "POST"
        and (p.get("request") or {}).get("path") in paths_with_request
        and (p.get("request") or {}).get("json") == {}
    ]


def _report_scan(cfg: SetConfig, cycle_id: str, impl_run: str, needle: str) -> list[str]:
    """Task ids whose stored ``test_report.md`` contains ``needle`` (per-round evidence, #1127)."""
    hits: list[str] = []
    for art in artifact_dirs(cfg, cycle_id, impl_run):
        m = _metadata(art)
        if not m or str(m.get("filename", "")) != "test_report.md":
            continue
        try:
            text = (REPO / m["vault_uri"]).read_text()
        except (OSError, KeyError):
            continue
        if needle in text:
            hits.append(str((m.get("metadata") or {}).get("task_id") or art.name))
    return sorted(hits)


def ledger_checks(rec: dict) -> dict:
    """#1021 at N=1: a green roll credits every criterion."""
    unevidenced = rec.get("criteria_unevidenced") or []
    return {
        "criteria": f"{rec.get('criteria_verified')}/{rec.get('criteria_total')}",
        "compile_criteria_unevidenced": [
            c for c in unevidenced if str(c).startswith("vc-compiles")
        ],
        "p_coverage_full": rec.get("verdict") != "accepted"
        or (rec.get("criteria_verified") == rec.get("criteria_total")),
    }


def runtime_log_window(since: str) -> list[str]:
    out = sh(f"docker logs --since {since} {RUNTIME_API_CONTAINER}", check=False)
    keys = (
        "correction_repair_target",
        "correction_repair_locus",
        "repair emitted no content",
        "correction_terminated",
        "self_eval fills",
        "fill merge",
        "patch_verification task=",
        "patch_retest task=",
        "Dispatched task task-",
        "plan_defect terminal",
        "evidence superseded",
    )
    return [line for line in out.splitlines() if any(k in line for k in keys)]


def loop_texture(cfg: SetConfig, cycle_id: str, impl_run: str | None, since: str) -> dict:
    logs = runtime_log_window(since)
    out = texture_from_logs(logs)
    out["fill_rejections"] = _fill_rejections(cfg, cycle_id, impl_run) if impl_run else []
    return out


def texture_from_logs(logs: list[str]) -> dict:
    """The loop's readouts from the runtime-api log window — pure, so the parse is testable.

    1.6.6 (plan §2.3): ``refused_patches`` (patch verification refused the repair — never
    applied), ``applied_patches`` (a retest ran, or verification passed), and
    ``plan_defect_after_zero_applied`` — prediction R4's falsifier, readable from the
    record instead of the executor log. ``refused_rounds_not_counted`` is D's own line;
    ``evidence_superseded`` is F's (#1111).
    """
    # A patch is APPLIED when verification passed or a retest ran on it; it is REFUSED when
    # verification failed, or came back unverifiable and the executor re-dispatched the task
    # instead of retesting (a dev task with no executable typed checks — the Next.js 1.6.6
    # shakeout's shape, which the first reading of this readout missed). Read sequentially
    # per task so an unverifiable-then-retest pair counts once, as applied.
    refused: list[str] = []
    applied = 0
    pending: dict[str, str] = {}  # task -> the unverifiable line awaiting its fate
    for line in logs:
        if "patch_verification task=" in line:
            task = line.split("patch_verification task=", 1)[1].split()[0]
            if "status=passed" in line:
                applied += 1
            elif "status=failed" in line:
                refused.append(line[-200:])
            elif "status=unverifiable" in line:
                pending[task] = line[-200:]
        elif "patch_retest task=" in line:
            task = line.split("patch_retest task=", 1)[1].split()[0]
            pending.pop(task, None)
            applied += 1
        elif "Dispatched task " in line:
            task = line.split("Dispatched task ", 1)[1].split()[0]
            if task in pending:
                refused.append(pending.pop(task))
    refused.extend(pending.values())
    terminations = [line[-200:] for line in logs if "correction_terminated_plan_defect" in line]
    return {
        "narrowed_targets": [
            line.split("correction_repair_target:")[-1][:160]
            for line in logs
            if "narrowed to the slot" in line
        ],
        "language_fallbacks": sum("falling back to same-language" in line for line in logs),
        "fill_targets": [
            line.split("correction_repair_locus:")[-1][:160]
            for line in logs
            if "re-fills slot" in line
        ],
        "empty_repair_emissions": [
            line[-160:] for line in logs if "repair emitted no content" in line
        ],
        "self_eval_fill_merges": [line[-160:] for line in logs if "self_eval fills" in line],
        "refused_patches": refused,
        "applied_patches": applied,
        "plan_defect_terminations": terminations,
        "plan_defect_after_zero_applied": bool(terminations) and applied == 0,
        "refused_rounds_not_counted": [
            line[-200:] for line in logs if "not counted as a repeat (#1129)" in line
        ],
        "evidence_superseded": [line[-200:] for line in logs if "evidence superseded" in line],
    }


def _fill_rejections(cfg: SetConfig, cycle_id: str, impl_run: str) -> list[str]:
    found = set()
    for art in artifact_dirs(cfg, cycle_id, impl_run):
        m = _metadata(art)
        if not m or not str(m.get("filename", "")).startswith("__tests__/scaffold/"):
            continue
        if (m.get("metadata") or {}).get("role") != "qa":
            continue
        try:
            text = (REPO / m["vault_uri"]).read_text()
        except (OSError, KeyError):
            continue
        found.update(
            line.strip()[:160]
            for line in text.splitlines()
            if "fill layer:" in line and "rejected" in line
        )
    return sorted(found)


# ---------------------------------------------------------------------------
# Render
# ---------------------------------------------------------------------------


def render(cfg: SetConfig, title: str, rec: dict) -> str:
    audit = rec.get("boot_audit", {})
    functional = rec.get("verdict") == "accepted" and audit.get("passed") is True
    lines = [
        f"# {cfg.name} — {title}",
        "",
        f"**Cycle** `{rec['cycle_id']}` · stack `{rec.get('stack')}` · deploy "
        f"`{cfg.frozen_deploy_commit or rec.get('deploy', {}).get('head', '?')}` · "
        f"config `{(rec.get('config_hash') or cfg.expected_config_hash_prefix or '?')[:12]}` · "
        f"squad snapshot `{(rec.get('squad_profile_snapshot_ref') or '?')[:12]}`",
        "",
        "## Headline",
        "",
        f"- verdict: **{rec.get('verdict')}**",
        *(
            [f"- ended with NO implementation run — {rec['ended_without_implementation']}"]
            if rec.get("ended_without_implementation")
            else []
        ),
        f"- boot audit: **{'PASS' if audit.get('passed') else 'FAIL' if audit.get('ran') else 'NOT RUN'}**"
        + (
            f" — {audit.get('detail', '')}" if audit.get("ran") else f" ({audit.get('reason', '')})"
        ),
        f"- functional (verdict AND audit AND zero intervention): **{'yes' if functional else 'no'}**",
        f"- P0 (seeded tree vs manifest): **{_p0_word(rec.get('static_checks', {}).get('p0'))}**",
        f"- wall clock: {rec['wall_clock_seconds'] // 60} min",
        "",
        "## Texture",
        "",
        "| field | value |",
        "|---|---|",
        f"| framing runs / re-rolls | {rec['framing_runs']} / {rec['framing_rerolls']} |",
        f"| correction rounds | {rec['correction_rounds']} |",
        f"| failed checks | {', '.join(rec['failed_checks']) or '—'} |",
        f"| criteria verified / total | {rec['criteria_verified']} / {rec['criteria_total']} |",
        f"| criteria unevidenced | {', '.join(rec['criteria_unevidenced']) or '—'} |",
        f"| failed emissions banked (#971) | {rec['failed_emissions_banked']} |",
        "",
        "## Gate decisions (decider recorded verbatim, never inferred)",
        "",
    ]
    lines += [
        f"- `{g['gate']}` → **{g['decision']}** by `{g['decided_by']}`"
        for g in rec["gate_decisions"]
    ]
    lines += [
        "",
        "## Runs",
        "",
        "| # | workload | status | min | failure |",
        "|---|---|---|---|---|",
    ]
    lines += [
        f"| {r['run_number']} | {r['workload']} | {r['status']} | {r['seconds'] // 60} | {r['failure_reason'] or '—'} |"
        for r in rec["runs"]
    ]
    lines += [
        "",
        "## Scoring — NOT decided here",
        "",
        "Validity (void / reset / counted) is a reading made at the roll boundary.",
        "The driver reports; the pre-registration decides.",
        "",
    ]
    return "\n".join(lines)


def _p0_word(p0: dict | None) -> str:
    if not p0:
        return "not run"
    if p0.get("refused"):
        return f"REFUSED — {p0['refused']}"
    return "held" if p0.get("passed") else "FALSIFIED"


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------


def identity_mismatch(expected_prefix: str, actual: str) -> bool:
    """True when a pinned identity is set and the roll's value does not carry it."""
    return bool(expected_prefix) and not (actual or "").startswith(expected_prefix)


def _write_record(cfg: SetConfig, stem: str, rec: dict, md: str) -> None:
    cfg.records_path.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    (cfg.records_path / f"{stem}-{stamp}.json").write_text(json.dumps(rec, indent=2))
    (cfg.records_path / f"{stem}-{stamp}.md").write_text(md)


def _run_cycle(
    cfg: SetConfig, stack: str, notes: str, *, title: str, stem: str, assert_hash: bool
) -> int:
    launched_at = log_since(datetime.now(UTC))
    cyc, run, chash = launch(cfg, notes)
    log(f"{title} launched: {cyc} / {run} config-hash {chash[:12]} stack {stack}")
    if cfg.expected_config_hash_prefix and not chash.startswith(cfg.expected_config_hash_prefix):
        log(f"!! config hash {chash[:12]} != the set's {cfg.expected_config_hash_prefix}")
        if assert_hash:
            log("   the roll is NOT comparable; recording and stopping")
            return 3
    ended_early = drive(cfg, cyc)
    rec = collect(cfg, cyc)
    rec["ended_without_implementation"] = ended_early
    rec["stack"] = stack
    rec["config_hash"] = chash
    rec["launched_at"] = launched_at
    if identity_mismatch(cfg.expected_squad_snapshot_prefix, rec["squad_profile_snapshot_ref"]):
        log(
            f"!! squad-profile snapshot {rec['squad_profile_snapshot_ref'][:16]} != the set's "
            f"{cfg.expected_squad_snapshot_prefix} — a different squad configuration"
        )
        if assert_hash:
            log("   the roll is NOT comparable; recording and stopping")
            _write_record(cfg, stem, rec, render(cfg, title, rec))
            return 3
    framing = completed_framing_run(cyc)
    rec["static_checks"] = static_checks(cfg, stack, cyc, rec["impl_run_id"], framing)
    rec["ledger_checks"] = ledger_checks(rec)
    rec["loop_texture"] = loop_texture(cfg, cyc, rec["impl_run_id"], launched_at)
    rec["boot_audit"] = (
        boot_audit(cfg, cyc, rec["impl_run_id"])
        if rec["impl_run_id"]
        else {"ran": False, "reason": "no implementation run"}
    )
    md = render(cfg, title, rec)
    _write_record(cfg, stem, rec, md)
    print()
    print(md)
    print("STATIC CHECKS:", json.dumps(rec["static_checks"], indent=2))
    print("LEDGER CHECKS:", json.dumps(rec["ledger_checks"], indent=2))
    print("LOOP TEXTURE:", json.dumps(rec["loop_texture"], indent=2))
    p0 = rec["static_checks"].get("p0") or {}
    if p0.get("refused"):
        return 4
    # A red framing is a recorded outcome, not a silent zero: a chained set or a watcher
    # reading only the exit code would otherwise treat "never built anything" as a pass.
    return 5 if ended_early else 0


def cmd_preflight(cfg: SetConfig, counting: bool) -> int:
    problems = preflight(cfg, counting=counting)
    if problems:
        print("PREFLIGHT FAILED — nothing launched:")
        for p in problems:
            print(f"  ✗ {p}")
        return 2
    log("preflight clean")
    return 0


def cmd_shakeout(cfg: SetConfig, dry_run: bool) -> int:
    rc = cmd_preflight(cfg, counting=False)
    if rc:
        return rc
    stack = stack_for(cfg)
    ident = deploy_identity(cfg)
    log(f"stack {stack}; deploy identity: {json.dumps(ident)}")
    if dry_run:
        return 0
    cfg.records_path.mkdir(parents=True, exist_ok=True)
    (cfg.records_path / "shakeout-deploy.json").write_text(json.dumps(ident, indent=2))
    return _run_cycle(
        cfg,
        stack,
        cfg.shakeout_notes,
        title="shakeout (non-counting)",
        stem="shakeout",
        assert_hash=False,
    )


def cmd_roll(cfg: SetConfig, roll: int, dry_run: bool) -> int:
    rc = cmd_preflight(cfg, counting=True)
    if rc:
        return rc
    stack = stack_for(cfg)
    if dry_run:
        return 0
    cfg.records_path.mkdir(parents=True, exist_ok=True)
    if not cfg.head_pin.exists():
        cfg.head_pin.write_text(sh(f"git -C {REPO} rev-parse --short HEAD"))
    notes = render_launch_notes(cfg.launch_notes, roll, cfg.n_rolls)
    return _run_cycle(
        cfg,
        stack,
        notes,
        title=f"roll {roll} of {cfg.n_rolls}",
        stem=f"roll-{roll:02d}",
        assert_hash=True,
    )


def main(argv: Sequence[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    sub = ap.add_subparsers(dest="command", required=True)
    for name in ("preflight", "shakeout", "roll"):
        p = sub.add_parser(name)
        p.add_argument(
            "--set",
            required=True,
            type=Path,
            help="set-config YAML (the pre-registration §1 as data)",
        )
        if name != "preflight":
            p.add_argument(
                "--dry-run", action="store_true", help="preflight + identity only, launch nothing"
            )
        if name == "roll":
            p.add_argument("--roll", type=int, required=True)
        if name == "preflight":
            p.add_argument(
                "--counting", action="store_true", help="also assert the frozen deploy and HEAD pin"
            )
    args = ap.parse_args(argv)
    cfg = load_set_config(args.set)
    if args.command == "preflight":
        return cmd_preflight(cfg, counting=args.counting)
    if args.command == "shakeout":
        return cmd_shakeout(cfg, args.dry_run)
    return cmd_roll(cfg, args.roll, args.dry_run)


if __name__ == "__main__":
    sys.exit(main())
