"""Sandbox audit of a run's DELIVERED application (FAY measurement §2/§7).

Answers "does the app this run delivered actually work?" independently of the
run's own verdict: assemble the deliverable from stored artifacts, stand it up
in the SIP-0102 canonical environment, and make it answer its contract's
probes over real HTTP.

Selection mirrors the executor's acceptance-aware rule (pf-31 Fix E,
dispatched_flow_executor ~L1026): per filename, the LATEST stored artifact
whose ``producing_task_type`` is NOT a repair-candidate type — accepted
repairs are re-stored under the task's own type (#389 swap), so rejected
candidates never enter the tree. pf-54 is the canonical trap this rule
survives: last-wins-by-time would pick a *rejected* repair that boots.

#971 adds the second exclusion: an emission marked ``emission_status="failed"``
is banked for triage and is never deliverable. The trap there is narrower and
worse — a failed emission is often the ONLY copy of its file (nothing re-emitted
it before the run died), so latest-per-filename would audit bytes already proven
not to work and report on an application the run never produced.

The assembly uses the run's OWN stored skeleton files (the seeding rail stores
them), so an audit of an old run reflects that run's era, not today's expander.

Probes come from the contract the run was seeded with (--contract): status
plus, when pinned, the error envelope's code. Issued directly over HTTP
against the sandbox-started app — the backend's probe op has no body/envelope
support yet; 102.4's relocation subsumes this.

Usage:
    .venv/bin/python scripts/dev/audit_delivered_app.py CYCLE_ID RUN_ID \
        --contract path/to/contract.yaml [--project group_run]

Exit 0 = PASS (install, build, boot, every probe). Exit 1 = FAIL, with the
step and detail on stdout. Exit 2 = auditor error (could not assemble).
"""

from __future__ import annotations

import argparse
import asyncio
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import httpx

from adapters.sandbox.container_backend import ContainerBackend
from adapters.tools.docker import DockerAdapter
from squadops.capabilities.handlers.probe_runner import evaluate_expectations
from squadops.capabilities.ui_data_path import (
    LIVE_SERVER,
    SERVED,
    classify_ui_response,
    describe_failure,
    expects_json,
    extract_ui_calls,
)
from squadops.cycles.task_plan import REPAIR_TASK_TYPES
from squadops.cycles.verification_contract import (
    VerificationContract,
    capture_probe_values,
    resolve_probe_path,
)
from squadops.sandbox.environment import get_environment_contract
from squadops.sandbox.models import RevisionOrigin
from squadops.sandbox.workspace import WorkspaceStore

#: One file per stack whose absence means assembly itself failed — the deliverable's
#: irreducible entry surface. Keyed by stack so a third stack declares its own rather
#: than inheriting a check that silently cannot hold.
_ASSEMBLY_SENTINELS: dict[str, str] = {
    "fullstack_fastapi_react": "backend/routes.py",
    "nextjs_ts": "package.json",
}

_VAULT_CONTAINER = "squadops-runtime-api"
_WORKSPACE_ARTIFACT_TYPES = frozenset({"source", "test", "config"})
_AUDIT_ROOT = Path("/tmp/squadops-sandbox-audit")


def _pull_run_artifacts(project: str, cycle_id: str, run_id: str, dest: Path) -> None:
    """Copy the run's vault subtree (contents + metadata.json) out of the
    runtime-api container in one shot."""
    vault_path = f"data/artifacts/{project}/{cycle_id}/{run_id}"
    tar = subprocess.run(  # noqa: S603 - fixed argv, dev tooling
        ["docker", "exec", _VAULT_CONTAINER, "sh", "-c", f"cd {vault_path} && tar cf - ."],
        capture_output=True,
    )
    if tar.returncode != 0:
        raise SystemExit(f"AUDITOR ERROR: cannot read vault for {run_id}: {tar.stderr.decode()!r}")
    subprocess.run(  # noqa: S603
        ["tar", "xf", "-", "-C", str(dest)], input=tar.stdout, check=True
    )


def _select_deliverable(pulled: Path) -> dict[str, str]:
    """filename -> content, acceptance-aware last-wins (the executor's rule)."""
    latest: dict[str, tuple[str, Path]] = {}
    for meta_path in pulled.glob("*/metadata.json"):
        meta = json.loads(meta_path.read_text())
        if meta.get("artifact_type") not in _WORKSPACE_ARTIFACT_TYPES:
            continue
        if (meta.get("metadata") or {}).get("emission_status") == "failed":
            continue  # #971: a banked failed emission is triage evidence, never the deliverable
        producing = (meta.get("metadata") or {}).get("producing_task_type", "")
        if producing in REPAIR_TASK_TYPES:
            continue  # rejected candidate — accepted repairs re-store under the task type
        filename = meta["filename"]
        content_file = meta_path.parent / filename
        if not content_file.is_file():
            continue
        created = str(meta.get("created_at", ""))
        if filename not in latest or created > latest[filename][0]:
            latest[filename] = (created, content_file)
    return {name: path.read_text() for name, (_, path) in latest.items()}


async def _run_ui_data_path(files: dict[str, str], stack: str, base_url: str) -> list[str]:
    """Put the paths the UI's own source requests to the running app (roll 1's defect).

    The contract probes above prove the API answers where the CONTRACT says; this proves
    it answers where the UI ASKS. Roll 1 passed the former and failed the latter on every
    page action, and nothing noticed. Each distinct path is requested once.

    **Every probe is a GET, whatever verb the UI uses**, and deliberately so: issuing the
    real verb would mutate the application under audit — a POST probe creates a record —
    and the audit has to be re-runnable against the same workspace. The cost is that a
    POST-only route answers 405, which ``classify_ui_response`` reads as SERVED (#953);
    the alternative, sending real verbs, buys a stronger signal by destroying the
    property that makes the audit repeatable.

    A path fails only when the answer shows no route is mounted there: a 404 the framework
    produced (HTML rather than the app's own JSON envelope), or HTML through the JSON seam,
    which means the call landed on a page. An app correctly reporting an unknown id still
    passes, and so does one that rejects the probe's method.
    """
    calls = extract_ui_calls(files, stack)
    if not calls:
        return []
    failures: list[str] = []
    seen: dict[tuple[str, bool], str] = {}
    async with httpx.AsyncClient(base_url=base_url, timeout=15.0) as client:
        for call in calls:
            cache_key = (call.request_path, expects_json(call.fn))
            verdict = seen.get(cache_key)
            if verdict is None:
                if call.request_path.startswith(("http://", "https://")):
                    verdict = LIVE_SERVER
                else:
                    try:
                        resp = await client.get(call.request_path)
                    except httpx.HTTPError as exc:
                        failures.append(f"{call.location()}: transport error {exc!r}")
                        continue
                    verdict = classify_ui_response(
                        call.request_path,
                        resp.status_code,
                        resp.headers.get("content-type", ""),
                        via_seam=expects_json(call.fn),
                    )
                seen[cache_key] = verdict
            if verdict != SERVED:
                failures.append(describe_failure(call, verdict))
    return failures


async def _run_probes(contract: VerificationContract, base_url: str) -> list[str]:
    """Issue every contract probe over HTTP, in order, sharing the capture
    context (#651 — join/leave resolve the id the create captured); return
    failure detail lines. Substitution/capture semantics come from the shared
    contract helpers so this stays in lockstep with the qa probe runner."""
    failures: list[str] = []
    context: dict[str, str] = {}
    async with httpx.AsyncClient(base_url=base_url, timeout=15.0) as client:
        for probe in contract.behavioral.probes:
            method = str(probe.request.get("method", "GET")).upper()
            path, missing = resolve_probe_path(str(probe.request.get("path", "/")), context)
            if missing is not None:
                failures.append(
                    f"probe {probe.id}: unresolved path placeholder {{{missing}}} "
                    f"(its upstream probe failed or captured nothing)"
                )
                continue
            body = probe.request.get("json")
            try:
                resp = await client.request(method, path, json=body)
            except httpx.HTTPError as exc:
                failures.append(f"probe {probe.id}: transport error {exc!r}")
                continue
            try:
                payload = resp.json()
            except ValueError:
                payload = None
            # #1079: the SAME judgment the in-cycle runner applies. This block used
            # to be a second implementation carrying two of the three expectation
            # kinds — it had no `json_has` branch — so the oracle was quietly the
            # more permissive of the two judges of one contract.
            failure = evaluate_expectations(probe.expect, resp.status_code, payload)
            if failure is not None:
                failures.append(f"probe {probe.id}: {failure}")
                continue
            if probe.capture:
                captured, missing_key = capture_probe_values(probe, payload)
                if missing_key is not None:
                    failures.append(
                        f"probe {probe.id}: capture key {missing_key!r} missing from response"
                    )
                    continue
                context.update(captured)
    return failures


async def _audit(args: argparse.Namespace) -> int:
    contract = VerificationContract.from_yaml(Path(args.contract).read_text(encoding="utf-8"))

    pulled = Path(tempfile.mkdtemp(prefix="fay_audit_pull_"))
    try:
        _pull_run_artifacts(args.project, args.cycle_id, args.run_id, pulled)
        files = _select_deliverable(pulled)
    finally:
        shutil.rmtree(pulled, ignore_errors=True)
    # The stack is the contract's own fact (``skeleton.expander``), never assumed: this
    # auditor was FastAPI-only until SIP-0104's window needed it for stack #2, and a
    # hardcoded environment would have stood a Next.js tree up with uvicorn and reported
    # the AUDITOR's defect as the app's.
    stack = contract.skeleton.expander
    sentinel = _ASSEMBLY_SENTINELS.get(stack)
    if sentinel is None:
        print(f"AUDITOR ERROR: no assembly sentinel for stack {stack!r}")
        return 2
    if sentinel not in files:
        print(f"AUDITOR ERROR: no {sentinel} among {len(files)} selected files")
        return 2
    print(f"assembled {len(files)} files for stack {stack} (acceptance-aware last-wins)")

    audit_cycle = f"audit_{args.run_id[:16]}"
    shutil.rmtree(_AUDIT_ROOT / "cycles" / audit_cycle, ignore_errors=True)
    store = WorkspaceStore(_AUDIT_ROOT / "cycles")
    env = get_environment_contract(stack)
    backend = ContainerBackend(
        container=DockerAdapter(),
        store=store,
        image=env.image,
        operation_commands=env.commands(),
        app_port=env.app_port,
        install_network=env.install_network,
        environment_contract_id=env.contract_id(),
        build_mutates_source=env.build_mutates_source,
        cache_root=_AUDIT_ROOT / "caches",
        timeout_seconds=420.0,
        readiness_timeout_seconds=30.0,
    )
    revision = store.seed(audit_cycle, files, origin=RevisionOrigin.SCAFFOLD_SEED)

    install = await backend.install_dependencies(revision=revision)
    if install.status != "succeeded":
        print(f"FAIL install: {install.exit_classification}")
        return 1
    build = await backend.build_frontend(revision=revision)
    if build.status != "succeeded":
        print(f"FAIL build: {'; '.join(build.diagnostics[-3:])}")
        return 1
    start = await backend.start_application(revision=revision)
    if not start.ready:
        print(f"FAIL boot: {'; '.join(start.startup_diagnostics[-3:])}")
        return 1
    try:
        if not start.endpoints:
            print("FAIL boot: app ready but no endpoint reported")
            return 1
        base_url = start.endpoints[0]
        failures = await _run_probes(contract, base_url)
        ui_failures = await _run_ui_data_path(files, stack, base_url)
    finally:
        await backend.stop_application(revision=revision, cleanup_handle=start.cleanup_handle)
    for line in failures:
        print(f"FAIL {line}")
    for line in ui_failures:
        print(f"FAIL ui-data-path {line}")
    if failures or ui_failures:
        return 1
    print(
        f"PASS — delivered app installs, builds, boots, answers "
        f"{len(contract.behavioral.probes)} contract probe(s), and its UI reaches "
        f"every path it requests "
        f"[image {env.image}, contract {env.contract_id()[:12]}]"
    )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("cycle_id")
    parser.add_argument("run_id")
    parser.add_argument("--contract", required=True, help="the contract the run was seeded with")
    parser.add_argument("--project", default="group_run")
    return asyncio.run(_audit(parser.parse_args()))


if __name__ == "__main__":
    sys.exit(main())
