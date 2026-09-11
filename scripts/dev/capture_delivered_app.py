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
        --route /:delivered-app-run-list \\
        --route '/runs/{id}:delivered-app-run-detail' \\
        --route /create:delivered-app-create-run-form

The label after each route's colon becomes the FILENAME, and `build_release_package.py` turns
that filename into the caption (stem, dashes to spaces) — so label them as captions, not as
slugs.

Two environment facts this encodes, both learned the hard way:

* **Only the frontend port is needed.** Vite proxies ``/api`` to the backend inside the
  container, so the UI is complete through one port and the API port is published only for
  poking at by hand.
* **Snap-confined chromium cannot write to ``/tmp/claude-*`` or to dot-directories.** It writes
  to a plain directory under ``$HOME`` and the files are moved into place afterwards.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
VAULT = REPO / "data/artifacts"
RELEASES = REPO / "site/content/releases"
SANDBOX_IMAGE = "squadops-sandbox-env:py3.12-node20-1.4"
CONTAINER = "squadops-delivered-app-capture"
#: Not the vault's own bookkeeping, and not the run's reports — the app.
NOT_APP = {"run_report.md", "test_report.md", "definition_of_done.json"}


def sh(*args: str, check: bool = True) -> str:
    r = subprocess.run(args, capture_output=True, text=True)
    if check and r.returncode != 0:
        raise SystemExit(f"failed: {' '.join(args)}\n{r.stderr.strip()}")
    return r.stdout.strip()


def reconstruct(project: str, cycle: str, run: str, out: Path) -> int:
    """The delivered tree: latest artifact per filename, which is what the audit builds.

    Earlier versions of a file are real history, not the delivery — taking the newest per
    name is what makes this the tree the run ended with rather than a union of attempts.
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
    latest: dict[str, tuple[str, Path]] = {}
    for meta_path in src.glob("art_*/metadata.json"):
        meta = json.loads(meta_path.read_text())
        name = meta.get("filename")
        if not name or name in NOT_APP or name.startswith("typed_check_evaluation"):
            continue
        stamp = meta.get("created_at", "")
        if name not in latest or stamp > latest[name][0]:
            latest[name] = (stamp, meta_path.parent)
    for name, (_, art_dir) in latest.items():
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


def seed(api_port: int, requests: list[dict], id_from: str) -> None:
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
                ident = first_id(api_port, id_from)
            path = path.replace("{id}", ident)
        body = json.dumps(spec.get("body") or {}).encode()
        req = urllib.request.Request(
            f"http://localhost:{api_port}{path}",
            data=body if spec.get("method", "POST") != "GET" else None,
            method=spec.get("method", "POST"),
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=20) as resp:
            if resp.status >= 300:
                raise SystemExit(f"seed {path} returned {resp.status}")


def first_id(api_port: int, path: str) -> str:
    with urllib.request.urlopen(f"http://localhost:{api_port}{path}", timeout=20) as resp:
        rows = json.load(resp)
    if not rows:
        raise SystemExit(f"--id-from {path} returned nothing to photograph")
    return str(rows[0]["id"])


def shoot(ui_port: int, routes: list[tuple[str, str]], assets: Path, width: int) -> list[Path]:
    # Snap-confined chromium refuses /tmp/claude-* and dot-directories; it writes here and
    # the files are moved into the repo afterwards.
    staging = Path.home() / "squadops-capture-staging"
    staging.mkdir(exist_ok=True)
    written = []
    try:
        for route, label in routes:
            target = staging / f"{label}.png"
            subprocess.run(
                [
                    "chromium",
                    "--headless",
                    "--disable-gpu",
                    "--no-sandbox",
                    "--hide-scrollbars",
                    f"--window-size={width},940",
                    "--virtual-time-budget=8000",
                    f"--screenshot={target}",
                    f"http://localhost:{ui_port}{route}",
                ],
                capture_output=True,
                text=True,
            )
            if not target.exists() or target.stat().st_size == 0:
                raise SystemExit(f"chromium wrote no file for {route} — is it snap-confined?")
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
    p.add_argument("--seed-file", type=Path, help="JSON list of {method, path, body} requests")
    p.add_argument("--ui-port", type=int, default=5199)
    p.add_argument("--api-port", type=int, default=8099)
    p.add_argument("--width", type=int, default=1180)
    p.add_argument("--wait", type=int, default=180)
    p.add_argument("--keep-up", action="store_true", help="leave the container running afterwards")
    args = p.parse_args()

    routes = []
    for spec in args.route:
        if ":" not in spec:
            raise SystemExit(f"--route needs PATH:LABEL, got {spec!r}")
        path, _, label = spec.rpartition(":")
        routes.append((path, label))
    if not routes:
        raise SystemExit("nothing to photograph — pass at least one --route PATH:LABEL")

    app = Path.home() / ".cache" / "squadops-capture" / args.cycle
    app.parent.mkdir(parents=True, exist_ok=True)
    count = reconstruct(args.project, args.cycle, args.run, app)
    print(f"reconstructed {count} files of {args.cycle}/{args.run} into {app}")

    boot(app, args.ui_port, args.api_port, args.wait)
    print(f"app up — ui :{args.ui_port}, api :{args.api_port}")
    try:
        if args.seed_file:
            requests = json.loads(args.seed_file.read_text())
            seed(args.api_port, requests, args.id_from)
            print(f"seeded {len(requests)} request(s) through the app's own API")
        if args.id_from:
            ident = first_id(args.api_port, args.id_from)
            routes = [(r.replace("{id}", ident), label) for r, label in routes]
        assets = RELEASES / f"v{args.version}" / "assets"
        written = shoot(args.ui_port, routes, assets, args.width)
    finally:
        if not args.keep_up:
            sh("docker", "rm", "-f", CONTAINER, check=False)

    print(f"\n{len(written)} screenshot(s) in {assets.relative_to(REPO)}")
    print("Now run build_release_package.py WITHOUT --write, read the verdict, run counts and")
    print("check names, and only then re-run with --write (CLAUDE.md step 7).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
