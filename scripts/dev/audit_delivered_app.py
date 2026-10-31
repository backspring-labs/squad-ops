"""Sandbox audit of a run's DELIVERED application (FAY measurement §2/§7).

Answers "does the app this run delivered actually work?" independently of the
run's own verdict: assemble the deliverable from stored artifacts, stand it up
in the SIP-0102 canonical environment, and make it answer its contract's
probes over real HTTP.

The deliverable is selected the way the release capture selects it
(``capture_delivered_app.delivered_dirs``, #2310), from the deploy's vault:
- **a promoted campaign increment** is its accepted tree, the whole app its
  promotion recorded. Its own run holds only the files its change touched, plus
  the scaffold's stubs for the rest, so a run-only selection audited the stubs;
- **a cycle built on an accepted one without a promotion** (the reference
  increment, #2008) is composed on the tree it built on;
- **any other run** is its own files by the executor's acceptance-aware rule
  (pf-31 Fix E): per filename, the LATEST stored artifact whose
  ``producing_task_type`` is NOT a repair-candidate type. Accepted repairs are
  re-stored under the task's own type (#389 swap), so rejected candidates never
  enter the tree. pf-54 is the canonical trap this rule survives: last-wins-by-time
  would pick a *rejected* repair that boots.

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
from pathlib import Path

import httpx

from adapters.sandbox.container_backend import ContainerBackend
from adapters.tools.docker import DockerAdapter
from squadops.capabilities.handlers.probe_runner import evaluate_expectations, seed_failure
from squadops.capabilities.ui_data_path import (
    LIVE_SERVER,
    SERVED,
    classify_ui_response,
    describe_failure,
    expects_json,
    extract_ui_calls,
)
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

#: Where each declared route is rendered (#1796): the qa role's container, the one image that
#: declares a browser and Node (``agents/instances/qa/system-packages.txt``). The audit's sandbox
#: image has neither, and on the React stack the sandbox serves only the backend.
_RENDER_CONTAINER = "squadops-eve"
#: Install, build and stand-up, then each page: the evaluation allows its preparation 600 s.
_RENDER_TIMEOUT_S = 1800

#: Run inside the render container with its deployed code: the increment evaluation's own render
#: (SIP-0109 §24p, ``evaluate_increment._rendered``), so the audit and the evaluation cannot
#: disagree about how a stack's pages are stood up and read. Reads its input from stdin and
#: prints one JSON line.
_RENDER_DRIVER = """
import asyncio, json, sys
from squadops.capabilities.handlers.cycle.evaluate_increment import _rendered
p = json.load(sys.stdin)
declared = {route: tuple(ids) for route, ids in p["declared"].items()}
seen = asyncio.run(_rendered(p["stack"], p["files"], declared, {"increment_route_seeds": p["seeds"]}))
print(json.dumps({route: (sorted(ids) if ids is not None else None) for route, ids in seen.items()}))
"""
_AUDIT_ROOT = Path("/tmp/squadops-sandbox-audit")


def _select_deliverable(
    project: str, cycle_id: str, run_id: str, built_on: str | None = None
) -> tuple[dict[str, str], str]:
    """filename -> content: the delivered app, by the release capture's selection, and the line
    saying which tree it is (``delivered_dirs``, #2310). This kept a run-only copy before, so a
    campaign increment that left ``backend/routes.py`` alone was audited with the scaffold's stub,
    every route answering 501, while its accepted tree named the working file."""
    from capture_delivered_app import delivered_dirs

    dirs, how = delivered_dirs(project, cycle_id, run_id, built_on)
    return {name: (d / name).read_text() for name, d in dirs.items()}, how


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

    A path fails when the answer shows no route is mounted there: a 404 the framework
    produced (HTML rather than the app's own JSON envelope), or HTML through the JSON seam,
    which means the call landed on a page. It also fails on an error status the seam receives
    without JSON, such as a route that raised (#2154). An app correctly reporting an unknown id
    still passes, and so does one that rejects the probe's method.
    """
    calls = extract_ui_calls(files, stack)
    if not calls:
        return []
    failures: list[str] = []
    # Each answer is kept beside its verdict, so a failure line states what the probe saw (#2154).
    seen: dict[tuple[str, bool], tuple[str, int | None, str]] = {}
    async with httpx.AsyncClient(base_url=base_url, timeout=15.0) as client:
        for call in calls:
            cache_key = (call.request_path, expects_json(call.fn))
            answer = seen.get(cache_key)
            if answer is None:
                if call.request_path.startswith(("http://", "https://")):
                    answer = (LIVE_SERVER, None, "")
                else:
                    try:
                        resp = await client.get(call.request_path)
                    except httpx.HTTPError as exc:
                        failures.append(f"{call.location()}: transport error {exc!r}")
                        continue
                    content_type = resp.headers.get("content-type", "")
                    answer = (
                        classify_ui_response(
                            call.request_path,
                            resp.status_code,
                            content_type,
                            via_seam=expects_json(call.fn),
                        ),
                        resp.status_code,
                        content_type,
                    )
                seen[cache_key] = answer
            verdict, status, content_type = answer
            if verdict != SERVED:
                failures.append(
                    describe_failure(call, verdict, status=status, content_type=content_type)
                )
    return failures


#: The most of a judged response a failure line carries — enough to see the shape that
#: was returned (an error envelope, a partial object, HTML), bounded so a record stays a
#: record. Every character past it is replaced by a count.
RESPONSE_EXCERPT_CHARS = 600


def response_excerpt(text: str, payload: object) -> str:
    """The judged response, compact and bounded (#1324): the JSON re-serialised with
    sorted keys when it parsed, otherwise the raw text repr'd and marked non-JSON."""
    if payload is not None:
        body = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    else:
        body = f"(non-JSON) {text!r}"
    if len(body) > RESPONSE_EXCERPT_CHARS:
        return f"{body[:RESPONSE_EXCERPT_CHARS]}… (+{len(body) - RESPONSE_EXCERPT_CHARS} chars)"
    return body


async def _issue_seeds(client: httpx.AsyncClient, probe) -> str | None:
    """#2202: the state an expectation is judged on, issued first, as the in-cycle runner issues
    it. Why the first seed that failed did, with the response it gave; ``None`` when all
    succeeded."""
    for index, seed in enumerate(probe.seed):
        try:
            seeded = await client.request(
                str(seed.get("method", "POST")).upper(),
                str(seed.get("path", "/")),
                json=seed.get("json"),
            )
        except httpx.HTTPError as exc:
            return f"seed[{index}] transport error {exc!r}"
        failure = seed_failure(index, seed, seeded.status_code)
        if failure is not None:
            try:
                payload = seeded.json()
            except ValueError:
                payload = None
            return f"{failure} — response: {response_excerpt(seeded.text, payload)}"
    return None


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
            seed_failed = await _issue_seeds(client, probe)
            if seed_failed is not None:
                failures.append(f"probe {probe.id}: {seed_failed}")
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
                # #1324: keep the response the judgment was made on. The delivered app is
                # gone by the time anyone reads the record, so a failure line that names
                # only the missing keys cannot be root-caused (1.7.2 counted roll 1).
                failures.append(
                    f"probe {probe.id}: {failure} — response {resp.status_code}: "
                    f"{response_excerpt(resp.text, payload)}"
                )
                continue
            if probe.capture:
                captured, missing_key = capture_probe_values(probe, payload)
                if missing_key is not None:
                    failures.append(
                        f"probe {probe.id}: capture key {missing_key!r} missing from response "
                        f"— response {resp.status_code}: {response_excerpt(resp.text, payload)}"
                    )
                    continue
                context.update(captured)
    return failures


def render_declared_routes(
    files: dict[str, str],
    stack: str,
    declared: dict[str, tuple[str, ...]],
    seeds: dict[str, dict],
    *,
    container: str = _RENDER_CONTAINER,
    run=subprocess.run,
) -> dict[str, frozenset[str] | None]:
    """Each declared route's rendered test ids, read in the qa container by the evaluation's own
    render (#1796). Every route is answered: one the container could not read is ``None``."""
    payload = json.dumps({"stack": stack, "files": files, "declared": declared, "seeds": seeds})
    try:
        done = run(  # noqa: S603 - fixed argv, dev tooling
            ["docker", "exec", "-i", container, "python3", "-c", _RENDER_DRIVER],
            input=payload,
            capture_output=True,
            text=True,
            timeout=_RENDER_TIMEOUT_S,
        )
    except (OSError, subprocess.TimeoutExpired) as e:
        print(f"route rendering could not run in {container}: {e}")
        return {route: None for route in declared}
    lines = [line for line in (done.stdout or "").splitlines() if line.startswith("{")]
    if done.returncode != 0 or not lines:
        print(f"route rendering failed in {container}: {(done.stderr or '').strip()[-500:]}")
        return {route: None for route in declared}
    read = json.loads(lines[-1])
    return {
        route: (frozenset(read[route]) if read.get(route) is not None else None)
        for route in declared
    }


def route_failures(
    declared: dict[str, tuple[str, ...]],
    rendered: dict[str, frozenset[str] | None],
    seeds: dict[str, dict],
) -> list[str]:
    """A failure line per declared route that did not render its view's root anchor, judged by
    the evaluation's own judge (``route_rendering``, §24p). A page that was never read is a
    failure here too: an audit that could not look has not seen the page render."""
    from squadops.campaigns.acceptance import Held, route_rendering
    from squadops.campaigns.increment_tree import unseeded_routes

    failures = []
    unseeded = unseeded_routes(declared, seeds)
    for result in route_rendering(declared, rendered, unseeded=unseeded):
        if result.held is Held.BROKEN:
            failures.append(f"{result.path}: rendered without its view's root {result.missing}")
        elif result.unseeded:
            failures.append(f"{result.path}: not read, no seed brings its page into being")
        elif result.held is not Held.HELD:
            failures.append(f"{result.path}: not read ({result.held}), so not seen to render")
    return failures


async def _audit(args: argparse.Namespace) -> int:
    contract = VerificationContract.from_yaml(Path(args.contract).read_text(encoding="utf-8"))

    from capture_delivered_app import built_on_cycle, cycle_overrides

    built_on = built_on_cycle(cycle_overrides(args.project, args.cycle_id))
    files, how = _select_deliverable(args.project, args.cycle_id, args.run_id, built_on)
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
    print(f"assembled {len(files)} files for stack {stack}: {how}")

    audit_cycle = f"audit_{args.run_id[:16]}"
    shutil.rmtree(_AUDIT_ROOT / "cycles" / audit_cycle, ignore_errors=True)
    store = WorkspaceStore(_AUDIT_ROOT / "cycles")
    env = get_environment_contract(stack)
    backend = ContainerBackend(
        app_network=None,  # a host run: apps publish to loopback (#2451 part 4)
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
    # #1796: the API calls the UI makes are not its pages. Each route the run's manifest
    # declares must render its view in a browser; #1794's rolls passed everything above with a
    # detail page no browser could reach.
    declared, seeds = _declared_routes(args.project, args.cycle_id)
    render_failures = (
        route_failures(
            declared,
            render_declared_routes(files, stack, declared, seeds, container=args.render_container),
            seeds,
        )
        if declared
        else []
    )
    for line in failures:
        print(f"FAIL {line}")
    for line in ui_failures:
        print(f"FAIL ui-data-path {line}")
    for line in render_failures:
        print(f"FAIL route-render {line}")
    if failures or ui_failures or render_failures:
        return 1
    print(
        f"PASS — delivered app installs, builds, boots, answers "
        f"{len(contract.behavioral.probes)} contract probe(s), its UI reaches "
        f"every path it requests, and each of its {len(declared)} declared route(s) renders "
        f"its view [image {env.image}, contract {env.contract_id()[:12]}]"
    )
    return 0


def _declared_routes(project: str, cycle_id: str) -> tuple[dict, dict]:
    """The run's declared client routes and their seeds, from the cycle's own manifest, read the
    way the release capture reads it (``capture_delivered_app.load_manifest``)."""
    import yaml
    from capture_delivered_app import load_manifest

    from squadops.campaigns.increment_tree import declared_routes, route_seeds
    from squadops.stacks.scaffold import InterfaceManifest

    manifest = InterfaceManifest.from_yaml(yaml.safe_dump(load_manifest(project, cycle_id)))
    return declared_routes(manifest), route_seeds(manifest)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("cycle_id")
    parser.add_argument("run_id")
    parser.add_argument("--contract", required=True, help="the contract the run was seeded with")
    parser.add_argument("--project", default="group_run")
    parser.add_argument(
        "--render-container",
        default=_RENDER_CONTAINER,
        help="the container each declared route is rendered in (#1796): one with a browser and "
        "Node, the qa role's by default",
    )
    return asyncio.run(_audit(parser.parse_args()))


if __name__ == "__main__":
    sys.exit(main())
