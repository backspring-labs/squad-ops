#!/usr/bin/env python3
"""Build, boot and photograph a cycle's DELIVERED app, for a release package's ``assets/``.

**Why this exists.** The cut checklist (CLAUDE.md step 7) has said "screenshots (Prefect run,
delivered app) go into that release's ``assets/`` before the script runs" since 2026-08-10, and
v1.7.0 through v1.7.4 all shipped with an EMPTY ``assets/``. That is the #789/#1061 shape: a
manual step that reads as done because nothing reports its absence. A step with that record
needs a command, not a restatement.

**Why it must run before the deploy moves.** The delivered tree lives in the artifact vault and
the package cites a cycle; once the deploy is rebuilt the cycle's evidence is gone (the same
reason ``loop_texture`` is perishable). Capture at the cut, from the deploy that produced it.

**It boots the real thing.** The tree is reconstructed latest-per-filename from the vault and run
in the same sandbox image the boot audit uses, backend and Vite dev server together. Seed
requests, if any, go through the app's OWN API — nothing is stubbed, so a screenshot cannot show
a state the app cannot reach.

    python scripts/dev/capture_delivered_app.py \\
        --cycle cyc_5a6e5ed0caeb --run run_d40b97760495 --version 1.7.5 \\
        --seed-file examples/03_group_run/screenshot_seed.json \\
        --id-from /runs \\
        --route /runs:delivered-app-run-list \\
        --route '/runs/{id}:delivered-app-run-detail' \\
        --route /runs/new:delivered-app-create-run-form

**The run's own interface is the authority (#1665).** Each cycle authors its interface manifest,
so field names, endpoints and client routes vary from roll to roll: v1.8.1's squad roll named
the field ``location`` (not ``meeting_location``), joined at ``/participants`` (not ``/join``)
and had no ``/`` route, so the list screenshot was a blank page written without complaint. The
seed file names candidates and aliases; the capture maps them onto what THIS run's
``interface_manifest.yaml`` declares, or refuses with the mismatch named. Every ``--route`` must
be a route the manifest declares, and every screenshot must render one of its route's declared
``data-testid`` values, or it is refused rather than written.

The label after each route's colon becomes the FILENAME, and `build_release_package.py` turns
that filename into the caption (stem, dashes to spaces) — so label them as captions, not as
slugs.

Two environment facts this encodes, both learned the hard way:

* **Only the frontend port is needed.** Vite proxies ``/api`` to the backend inside the
  container, so the UI is complete through one port and the API port is published only for
  poking at by hand.
* **Snap-confined chromium cannot write to ``/tmp/claude-*`` or to dot-directories.** It writes
  to a plain directory under ``$HOME`` and the files are moved into place afterwards.

The browser is ``--browser``, and a page it could not load is refused as the browser's failure,
never the app's (``capture_browser.py``, #1793). The vault is the main checkout's, so a capture
run from the release package's worktree reads the deploy's artifacts (#1793).
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

import yaml

from squadops.cycles.delivered_tree import StoredArtifact, delivered_files

sys.path.insert(0, str(Path(__file__).resolve().parent))
from capture_browser import add_browser_argument, loaded_dom, screenshot  # noqa: E402
from checkouts import main_checkout  # noqa: E402

#: The checkout the package is written into (a release branch's worktree), and the main one
#: whose ``data/`` the deploy writes: the vault is only ever there.
REPO = Path(__file__).resolve().parents[2]
MAIN = main_checkout(REPO)
VAULT = MAIN / "data/artifacts"
RELEASES = REPO / "site/content/releases"
SANDBOX_IMAGE = "squadops-sandbox-env:py3.12-node20-1.4"
CONTAINER = "squadops-delivered-app-capture"


def sh(*args: str, check: bool = True) -> str:
    r = subprocess.run(args, capture_output=True, text=True)
    if check and r.returncode != 0:
        raise SystemExit(f"failed: {' '.join(args)}\n{r.stderr.strip()}")
    return r.stdout.strip()


def reconstruct(project: str, cycle: str, run: str, out: Path) -> int:
    """The delivered tree, by the one rule the audit reads too (#1832): per filename, the latest
    workspace artifact the run accepted. A rejected repair candidate or a failed emission is
    never what the run delivered, however recent; this took the newest file by name before, and
    so could photograph a repair the framework had rejected.
    """
    src = VAULT / project / cycle / run
    if not src.is_dir():
        raise SystemExit(f"no vault directory for {project}/{cycle}/{run}")
    if out.exists():
        try:
            shutil.rmtree(out)
        except PermissionError:
            # `npm install` runs as root inside the container, so a previous capture leaves a
            # root-owned `node_modules` the host user cannot unlink. Remove it the same way it
            # was created rather than asking for sudo.
            sh(
                "docker",
                "run",
                "--rm",
                "-v",
                f"{out.parent}:/x",
                SANDBOX_IMAGE,
                "rm",
                "-rf",
                f"/x/{out.name}",
            )
            if out.exists():
                raise SystemExit(f"could not clear {out} — remove it by hand and re-run") from None
    records = {}
    for meta_path in src.glob("art_*/metadata.json"):
        meta = json.loads(meta_path.read_text())
        records[meta["artifact_id"]] = (meta, meta_path.parent)
    delivered = delivered_files(StoredArtifact.from_record(m) for m, _ in records.values())
    latest = {name: records[art_id][1] for name, art_id in delivered.items()}
    for name, art_dir in latest.items():
        source = art_dir / name
        if not source.exists():
            files = [p for p in art_dir.rglob("*") if p.is_file() and p.name != "metadata.json"]
            if not files:
                continue
            source = files[0]
        dest = out / name
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, dest)
    return len(latest)


def load_manifest(project: str, cycle: str) -> dict:
    """The cycle's authored ``interface_manifest.yaml`` from the vault: the latest one, from
    whichever run of the cycle stored it (framing authors it)."""
    found: list[tuple[str, Path]] = []
    for meta_path in (VAULT / project / cycle).glob("run_*/art_*/metadata.json"):
        meta = json.loads(meta_path.read_text())
        if meta.get("filename") == "interface_manifest.yaml":
            found.append((meta.get("created_at", ""), MAIN / meta["vault_uri"]))
    if not found:
        raise SystemExit(
            f"no interface_manifest.yaml stored for {project}/{cycle}: the capture maps the seed "
            "and the routes onto the run's own interface, and has none to read"
        )
    return yaml.safe_load(max(found)[1].read_text()) or {}


def _norm(path: str) -> str:
    """``/runs/{run_id}``, ``/runs/:run_id`` and ``/runs/{id}`` are one route."""
    return re.sub(r"\{[^}/]+\}|:[A-Za-z_][A-Za-z0-9_]*", "{id}", path)


def _endpoints(manifest: dict) -> dict[str, dict]:
    api = manifest.get("api") or {}
    base = api.get("base_path") or ""
    return {
        f"{e['method'].upper()} {_norm(base + e['path'])}": e for e in api.get("endpoints") or []
    }


def _pick(candidates: list[str], endpoints: dict[str, dict], what: str) -> tuple[str, dict]:
    for candidate in candidates:
        method, _, path = candidate.partition(" ")
        key = f"{method.upper()} {_norm(path)}"
        if key in endpoints:
            return key, endpoints[key]
    raise SystemExit(
        f"none of the seed's {what} endpoints {candidates} is declared by this run's manifest, "
        f"which declares {sorted(endpoints)}"
    )


def _body(
    record: dict, shape: dict, aliases: dict[str, list[str]], where: str
) -> tuple[dict, set[str]]:
    """The record's values under the SHAPE's field names, via the seed's aliases, and the
    record keys that carried over."""
    body: dict = {}
    used: set[str] = set()
    for name in [*(shape.get("required") or []), *(shape.get("optional") or [])]:
        key = next(
            (k for k in record if k == name or name in (aliases.get(k) or [])),
            None,
        )
        if key is not None:
            body[name] = record[key]
            used.add(key)
        elif name in (shape.get("required") or []):
            raise SystemExit(
                f"{where}: the manifest requires {name!r} and the seed has no value for it "
                f"(record keys {sorted(record)}, aliases {aliases})"
            )
    return body, used


def _under_base(candidates: list[str], base: str) -> list[str]:
    """The seed names endpoints without a base path (``POST /runs``); an interface declares its
    endpoints under one (``base_path: /api``, so ``POST /api/runs``). Each candidate is also tried
    under the base, the form the app's own client uses — the 1.8.2 cut found the committed seed
    matching nothing on an app behind ``/api``."""
    if not base:
        return candidates
    under = []
    for c in candidates:
        method, _, path = c.partition(" ")
        under.append(c if path == base or path.startswith(base + "/") else f"{method} {base}{path}")
    return list(dict.fromkeys(candidates + under))


def plan_seed(manifest: dict, seed: dict) -> tuple[list[dict], list[str]]:
    """The seed as requests against THIS run's declared interface, and notes on what did not
    carry over. Refuses a seed the interface cannot take rather than sending a request that
    would 422 or 404 halfway through."""
    if not isinstance(seed, dict):
        raise SystemExit(
            "the seed file is the pre-#1665 request list; write it as {create, records, "
            "field_aliases, member_action} so it can be mapped onto each run's interface"
        )
    endpoints = _endpoints(manifest)
    shapes = (manifest.get("api") or {}).get("request_shapes") or {}
    aliases = seed.get("field_aliases") or {}
    base = (manifest.get("api") or {}).get("base_path") or ""
    create_key, create = _pick(_under_base(seed["create"], base), endpoints, "create")
    create_shape = shapes.get(create.get("request") or "", {})
    requests: list[dict] = []
    notes: list[str] = []
    for i, record in enumerate(seed["records"], start=1):
        body, used = _body(record, create_shape, aliases, f"record {i}")
        notes += [
            f"record {i}: {k} dropped, not in {create.get('request')}"
            for k in sorted(set(record) - used)
        ]
        requests.append({"method": "POST", "path": create_key.partition(" ")[2], "body": body})
    member = seed.get("member_action")
    if member:
        key, endpoint = _pick(_under_base(member["endpoints"], base), endpoints, "member action")
        shape = shapes.get(endpoint.get("request") or "", {})
        for j, record in enumerate(member["bodies"], start=1):
            body, _ = _body(record, shape, aliases, f"member action {j}")
            requests.append({"method": "POST", "path": key.partition(" ")[2], "body": body})
    return requests, notes


def declared_routes(manifest: dict, routes: list[tuple[str, str]]) -> dict[str, list[str]]:
    """``{requested path: its declared testids}``; refuses a route the app does not declare,
    which is a blank page (#1665: the list shot at ``/`` on an app routed at ``/runs``)."""
    declared = {
        _norm(r["path"]): list(r.get("testids") or [])
        for r in (manifest.get("frontend") or {}).get("routes") or []
    }
    if not declared:
        raise SystemExit("this run's manifest declares no frontend routes; nothing to photograph")
    unknown = [path for path, _ in routes if _norm(path) not in declared]
    if unknown:
        raise SystemExit(
            f"route(s) {unknown} are not declared by this run's app, which routes "
            f"{sorted(declared)}; a route it does not define photographs as a blank page"
        )
    return {path: declared[_norm(path)] for path, _ in routes}


def rendered_testids(browser: str, ui_port: int, route: str) -> set[str]:
    """The ``data-testid`` values the page at ``route`` actually rendered."""
    dom = loaded_dom(browser, f"http://localhost:{ui_port}{route}", 8000)
    return set(re.findall(r'data-testid="([^"]+)"', dom))


def boot(app: Path, ui_port: int, api_port: int, wait_s: int) -> None:
    sh("docker", "rm", "-f", CONTAINER, check=False)
    sh(
        "docker",
        "run",
        "-d",
        "--name",
        CONTAINER,
        "-v",
        f"{app}:/workspace",
        "-w",
        "/workspace",
        "-p",
        f"{ui_port}:5173",
        "-p",
        f"{api_port}:8000",
        SANDBOX_IMAGE,
        "sh",
        "-c",
        "set -e\n"
        "pip install --quiet -r backend/requirements.txt\n"
        "python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 &\n"
        "cd frontend\n"
        "npm install --no-audit --no-fund --loglevel=error\n"
        "npx vite --host 0.0.0.0 --port 5173",
    )
    deadline = time.time() + wait_s
    while time.time() < deadline:
        try:
            urllib.request.urlopen(f"http://localhost:{ui_port}/", timeout=3).read()
            urllib.request.urlopen(f"http://localhost:{api_port}/docs", timeout=3).read()
            return
        except (urllib.error.URLError, OSError, TimeoutError):
            time.sleep(3)
    print(sh("docker", "logs", CONTAINER, check=False), file=sys.stderr)
    raise SystemExit(f"app did not come up within {wait_s}s")


def seed(port: int, requests: list[dict], id_from: str) -> None:
    """Drive the app through its own API. A non-2xx is fatal: a screenshot of a state the
    app refused to enter would be a picture of something that never happened.

    A seed path may contain ``{id}``, resolved from ``--id-from`` at the moment it is first
    needed — the requests that act ON a record (join, leave, comment) cannot know its id until
    the requests that CREATE one have run. Without this the run-detail shot read
    ``Participants (0)`` under a filename promising participants, and the filename is the
    caption on the release page.
    """
    ident = ""
    for spec in requests:
        path = spec["path"]
        if "{id}" in path:
            if not ident:
                if not id_from:
                    raise SystemExit(f"seed {path} needs --id-from to resolve {{id}}")
                ident = first_id(port, id_from)
            path = path.replace("{id}", ident)
        body = json.dumps(spec.get("body") or {}).encode()
        req = urllib.request.Request(
            f"http://localhost:{port}{path}",
            data=body if spec.get("method", "POST") != "GET" else None,
            method=spec.get("method", "POST"),
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=20) as resp:
            if resp.status >= 300:
                raise SystemExit(f"seed {path} returned {resp.status}")


def first_id(port: int, path: str) -> str:
    with urllib.request.urlopen(f"http://localhost:{port}{path}", timeout=20) as resp:
        rows = json.load(resp)
    if not rows:
        raise SystemExit(f"--id-from {path} returned nothing to photograph")
    return str(rows[0]["id"])


def shoot(
    browser: str,
    ui_port: int,
    routes: list[tuple[str, str]],
    assets: Path,
    width: int,
    testids: dict[str, list[str]],
) -> list[Path]:
    # Snap-confined chromium refuses /tmp/claude-* and dot-directories; it writes here and
    # the files are moved into the repo afterwards.
    staging = Path.home() / "squadops-capture-staging"
    staging.mkdir(exist_ok=True)
    written = []
    try:
        for route, label in routes:
            target = staging / f"{label}.png"
            screenshot(browser, f"http://localhost:{ui_port}{route}", target, width, 940, 8000)
            if not target.exists() or target.stat().st_size == 0:
                raise SystemExit(f"{browser} wrote no file for {route} — is it snap-confined?")
            # A screenshot of a page that rendered none of its view is a picture of nothing,
            # and its filename is a caption promising something (#1665).
            expected = testids.get(route) or []
            seen = rendered_testids(browser, ui_port, route)
            if not (seen & set(expected) if expected else seen):
                raise SystemExit(
                    f"the page at {route} rendered none of its view's test ids {expected} "
                    f"(saw {sorted(seen)}): a blank or error page, refused rather than written"
                )
            assets.mkdir(parents=True, exist_ok=True)
            dest = assets / target.name
            shutil.move(str(target), dest)
            written.append(dest)
            print(f"  {route:24} -> {dest.relative_to(REPO)} ({dest.stat().st_size} bytes)")
    finally:
        shutil.rmtree(staging, ignore_errors=True)
    return written


def main() -> int:
    p = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    p.add_argument("--cycle", required=True)
    p.add_argument("--run", required=True, help="the IMPLEMENTATION run id, not the framing one")
    p.add_argument("--project", default="group_run")
    p.add_argument("--version", required=True, help="e.g. 1.7.5 — selects site/content/releases/vX")
    p.add_argument(
        "--route",
        action="append",
        default=[],
        metavar="PATH:LABEL",
        help="repeatable; `{id}` is filled from --id-from. LABEL becomes the caption",
    )
    p.add_argument(
        "--id-from",
        default="",
        metavar="PATH",
        help="GET this list endpoint and use the first row's id for `{id}`",
    )
    p.add_argument(
        "--seed-file",
        type=Path,
        help="{create, records, field_aliases, member_action}, mapped onto the run's manifest",
    )
    p.add_argument("--ui-port", type=int, default=5199)
    p.add_argument("--api-port", type=int, default=8099)
    p.add_argument("--width", type=int, default=1180)
    p.add_argument("--wait", type=int, default=180)
    p.add_argument("--keep-up", action="store_true", help="leave the container running afterwards")
    add_browser_argument(p)
    args = p.parse_args()

    routes = []
    for spec in args.route:
        if ":" not in spec:
            raise SystemExit(f"--route needs PATH:LABEL, got {spec!r}")
        path, _, label = spec.rpartition(":")
        routes.append((path, label))
    if not routes:
        raise SystemExit("nothing to photograph — pass at least one --route PATH:LABEL")

    manifest = load_manifest(args.project, args.cycle)
    # Resolved against the run's interface BEFORE anything boots: a mismatch is named here, not
    # discovered as a 422 halfway through seeding or a blank page on the release.
    route_testids = declared_routes(manifest, routes)
    if args.id_from and f"GET {_norm(args.id_from)}" not in _endpoints(manifest):
        raise SystemExit(f"--id-from {args.id_from} is not a GET endpoint this run declares")
    requests: list[dict] = []
    if args.seed_file:
        requests, notes = plan_seed(manifest, json.loads(args.seed_file.read_text()))
        for note in notes:
            print(f"  seed: {note}")

    app = Path.home() / ".cache" / "squadops-capture" / args.cycle
    app.parent.mkdir(parents=True, exist_ok=True)
    count = reconstruct(args.project, args.cycle, args.run, app)
    print(f"reconstructed {count} files of {args.cycle}/{args.run} into {app}")

    boot(app, args.ui_port, args.api_port, args.wait)
    print(f"app up — ui :{args.ui_port}, api :{args.api_port}")
    try:
        # Through the UI port, with the interface's client-facing paths: the app's own client
        # calls its API that way, and the dev proxy strips the base path the backend does not
        # serve (the 1.8.2 cut's React app: base_path /api, the router at the root — a request
        # sent straight to the backend's /api/runs was a 404).
        if requests:
            seed(args.ui_port, requests, args.id_from)
            print(f"seeded {len(requests)} request(s) through the app's own API")
        if args.id_from:
            ident = first_id(args.ui_port, args.id_from)
            route_testids = {r.replace("{id}", ident): t for r, t in route_testids.items()}
            routes = [(r.replace("{id}", ident), label) for r, label in routes]
        assets = RELEASES / f"v{args.version}" / "assets"
        written = shoot(args.browser, args.ui_port, routes, assets, args.width, route_testids)
    finally:
        if not args.keep_up:
            sh("docker", "rm", "-f", CONTAINER, check=False)

    print(f"\n{len(written)} screenshot(s) in {assets.relative_to(REPO)}")
    print("Now run build_release_package.py WITHOUT --write, read the verdict, run counts and")
    print("check names, and only then re-run with --write (CLAUDE.md step 7).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
