#!/usr/bin/env python3
"""The merge sweep (#2862): a merged contribution syncs its Project and re-validates it.

After the owner merges a contribution's pull request, the Project's ``integrated_upstream_commit``
stayed put until someone ran a sync by hand, so the next Campaign read a product without the merged
work. Run on a timer on the deploy's host (``infra/systemd/squadops-merge-sweep.*``), this:

1. lists every repository-backed Project's contributions through the runtime API;
2. reads each pending contribution's review request on the forge. **It only reads:** every forge
   call is a ``GET`` through ``_forge_get``, and the sweep never pushes, comments, merges or edits;
3. for a Project with a merged one, records a sync (``POST /api/v1/projects/{id}/syncs``), which
   marks the contribution integrated against the commit that took it and names the drift, then
   re-validates the Project (``POST /api/v1/projects/{id}/validate``). That advances the development
   baseline, so new cycles wait for configure and baseline capture, as after any sync (the owner's
   ruling of 2026-11-05).

**The credential** is the host's GitHub CLI login (``gh auth token``), passed with each of those two
requests for that request alone, as ``--token-from-gh`` does. The deploy stores no token, and the
sweep writes none anywhere (the owner, 2026-11-08: "accomplish the goal with your current access and
just not write anything you shouldn't").

**A failure is reported, never retried in silence.** A sync or validation the runtime refuses is
printed with its reason, a sync that can't reconcile reads ``unreconciled`` on the Project, and the
sweep exits 1. Detection is by polling, the timer's interval.

    python scripts/dev/ops/merge_sweep.py [--dry-run] [--env-file PATH]

``--dry-run`` reads and reports, and records nothing. The output is one JSON line per Project acted
on, then a summary line.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import uuid
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[3]
#: The sweep's own CLI config and token cache (the CLI honours ``XDG_CONFIG_HOME``), so its login
#: never overwrites another login on the box: one token cache per machine is the CLI's default.
SWEEP_CONFIG_HOME = Path.home() / ".config" / "squadops-merge-sweep"
#: Who the sweep signs in as: syncs and validations need ``admin:write``.
SWEEP_IDENTITY = "squadops-admin"
SWEEP_PASSWORD_KEY = "SQUADOPS_ADMIN_PASSWORD"
#: A review request's URL on the forge: owner, repository and pull request number.
_PULL_URL = re.compile(r"https://github\.com/([^/]+)/([^/]+)/pull/(\d+)/?$")
PENDING = "pending"


def _forge_get(path: str, run: Callable[..., Any] = subprocess.run) -> dict:
    """One forge read through the GitHub CLI's login. The only forge call the sweep makes, and
    always a ``GET``: the sweep never writes to the forge."""
    done = run(
        ["gh", "api", "--method", "GET", path],
        capture_output=True,
        text=True,
        timeout=60,
    )
    if done.returncode != 0:
        raise RuntimeError(f"forge read {path} failed: {(done.stderr or '').strip()[:200]}")
    return json.loads(done.stdout)


def gh_token(run: Callable[..., Any] = subprocess.run) -> str:
    """The host's GitHub CLI token, for one request's body. Never printed or written."""
    done = run(["gh", "auth", "token"], capture_output=True, text=True, timeout=30)
    token = (done.stdout or "").strip()
    if done.returncode != 0 or not token:
        raise RuntimeError("`gh auth token` gave no token: the host's GitHub CLI isn't logged in")
    return token


def merged_reviews(contributions: Sequence[Mapping[str, Any]], forge_get=_forge_get) -> list[dict]:
    """Each pending contribution whose review request is merged, with the merge's commit."""
    merged = []
    for c in contributions:
        if c.get("state") != PENDING or not c.get("review_url"):
            continue
        match = _PULL_URL.match(str(c["review_url"]))
        if match is None:
            continue
        owner, repo, number = match.groups()
        pull = forge_get(f"repos/{owner}/{repo}/pulls/{number}")
        if pull.get("merged"):
            merged.append(
                {
                    "review_url": c["review_url"],
                    "cycle_id": c.get("cycle_id"),
                    "merge_commit": pull.get("merge_commit_sha"),
                }
            )
    return merged


def unvalidated_sync(api: Any, project: Mapping[str, Any]) -> str | None:
    """The upstream commit of the Project's latest sync when that sync took a contribution and the
    development baseline still isn't there, else ``None``."""
    syncs = api.get(f"/api/v1/projects/{project['project_id']}/syncs")
    if not syncs:
        return None
    latest = syncs[-1].get("document", {})
    upstream = latest.get("upstream_commit")
    took = any(c.get("state") == "integrated" for c in latest.get("contributions", []))
    if took and upstream and upstream != project.get("development_baseline_commit"):
        return upstream
    return None


def sweep(api: Any, *, forge_get=_forge_get, token: Callable[[], str] = gh_token,
          dry_run: bool = False) -> tuple[list[dict], bool]:  # fmt: skip
    """Every repository-backed Project with a merged pending contribution, synced and re-validated.
    Returns each Project's line and whether every one succeeded."""
    lines: list[dict] = []
    ok = True
    for project in api.get("/api/v1/projects"):
        project_id = project.get("project_id")
        if not project.get("source"):
            continue  # a sample application has no upstream to merge into
        contributions = [
            item.get("contribution", item)
            for item in api.get(f"/api/v1/projects/{project_id}/contributions")
        ]
        try:
            merged = merged_reviews(contributions, forge_get)
        except RuntimeError as e:
            ok = False
            lines.append({"project_id": project_id, "error": str(e)})
            continue
        unvalidated = None if merged else unvalidated_sync(api, project)
        if not merged and unvalidated is None:
            continue
        line: dict[str, Any] = {"project_id": project_id, "merged": merged}
        if unvalidated is not None:
            # A sync took a contribution, and its validation never landed (it failed, or the
            # sweep stopped between them). Nothing reads pending now, so retry the validation.
            line["revalidating_after"] = unvalidated
        if dry_run:
            lines.append({**line, "dry_run": True})
            continue
        key = "merge-sweep-" + (
            "-".join(sorted((m["merge_commit"] or "?")[:12] for m in merged))
            or f"revalidate-{str(unvalidated)[:12]}"
        )
        try:
            if merged:
                synced = api.post(
                    f"/api/v1/projects/{project_id}/syncs",
                    json={"idempotency_key": key, "token": token()},
                )
                document = synced.get("document", {})
                line["sync"] = {
                    "upstream_commit": document.get("upstream_commit"),
                    "contributions": [
                        {"cycle_id": c.get("cycle_id"), "state": c.get("state")}
                        for c in document.get("contributions", [])
                    ],
                }
            validated = api.post(
                f"/api/v1/projects/{project_id}/validate",
                json={"idempotency_key": f"{key}-validate", "token": token()},
            )
            record = validated.get("project", validated)
            line["validated"] = {
                "lifecycle_status": record.get("lifecycle_status"),
                "development_baseline_commit": record.get("development_baseline_commit"),
                "next": "configure, then baseline capture, before a new cycle",
            }
        except Exception as e:  # noqa: BLE001 — every refusal is reported and fails the run
            ok = False
            line["error"] = f"{type(e).__name__}: {e}"
        lines.append(line)
    return lines, ok


def env_value(env_file: Path, key: str) -> str | None:
    """``key``'s value in the deploy's ``.env``, unquoted, or ``None``."""
    if not env_file.is_file():
        return None
    for line in env_file.read_text().splitlines():
        name, sep, value = line.partition("=")
        if sep and name.strip() == key:
            return value.strip().strip('"').strip("'") or None
    return None


def sign_in(env_file: Path, run: Callable[..., Any] = subprocess.run) -> None:
    """Sign the sweep in under its own config home, non-interactively. The password reaches the
    CLI as ``SQUADOPS_PASSWORD`` in its environment, never as an argument, and is never printed."""
    SWEEP_CONFIG_HOME.mkdir(mode=0o700, parents=True, exist_ok=True)
    os.environ["XDG_CONFIG_HOME"] = str(SWEEP_CONFIG_HOME)
    own = SWEEP_CONFIG_HOME / "squadops" / "config.toml"
    default = Path.home() / ".config" / "squadops" / "config.toml"
    if not own.exists() and default.exists():
        own.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        shutil.copyfile(default, own)
        own.chmod(0o600)
    password = env_value(env_file, SWEEP_PASSWORD_KEY)
    if password is None:
        raise RuntimeError(
            f"{SWEEP_PASSWORD_KEY} isn't in the deploy's .env: the sweep can't sign in"
        )
    # The realm and host the runtime's public issuer is built from (docker-compose.yml:
    # ISSUER_PUBLIC_URL = http://${SQUADOPS_HOST}:8180/realms/${SQUADOPS_REALM}), so the token the
    # sweep is issued is one the runtime accepts.
    realm = env_value(env_file, "SQUADOPS_REALM") or "squadops-dev"
    host = env_value(env_file, "SQUADOPS_HOST") or "localhost"
    cli = shutil.which("squadops") or str(Path(sys.executable).parent / "squadops")
    done = run(
        [
            cli,
            "login",
            "-u",
            SWEEP_IDENTITY,
            "--keycloak-url",
            f"http://{host}:8180",
            "--realm",
            realm,
        ],  # fmt: skip
        env={**os.environ, "SQUADOPS_PASSWORD": password},
        capture_output=True,
        text=True,
        timeout=120,
    )
    if done.returncode != 0:
        raise RuntimeError(
            f"the sweep's sign-in as {SWEEP_IDENTITY} failed (exit {done.returncode})"
        )


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--env-file", type=Path, default=REPO_ROOT / ".env",
                    help="the deploy's .env, for the sweep's sign-in (the checkout's own by default)")  # fmt: skip
    args = ap.parse_args(argv)
    sign_in(args.env_file)
    from squadops.cli.client import APIClient
    from squadops.cli.config import load_config

    api = APIClient(load_config())
    try:
        lines, ok = sweep(api, dry_run=args.dry_run)
    finally:
        api.close()
    for line in lines:
        print(json.dumps(line, sort_keys=True))
    print(json.dumps({"merge_sweep": "ok" if ok else "failed", "projects_acted_on": len(lines),
                      "run": uuid.uuid4().hex[:8]}))  # fmt: skip
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
