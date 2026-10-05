#!/usr/bin/env python3
"""Each deploy's own credentials (#2006).

A deploy made by bootstrap used to keep the values the repository commits, so every deploy shared
them, and anyone reading the repository could sign in to any deploy reachable beyond its host.
The registry (``infra/deploy_credentials.json``) names every credential a deploy holds. ``.env`` is
each one's single home.

``ensure`` gives ``.env`` every credential and derives the ``secrets/`` files from it:
- a variable ``.env`` lacks, or holds empty, is **generated** on a new deploy;
- on a deploy that already exists, the value it already runs with is **adopted** instead (the
  secret file it already has, else the registry's ``legacy`` value), so a deploy that predates
  #2006 keeps working until it is rotated (the doctor names what to rotate);
- a value ``.env`` holds is never changed here. Rotating one is a deliberate act
  (``docs/ops/credential_rotation.md``).

``check`` names every credential that is missing or holds a value the repository has committed.

Stdlib only: bootstrap runs this before the venv exists.

    python3 scripts/dev/ops/deploy_credentials.py ensure [--existing auto|yes|no] [--dry-run]
    python3 scripts/dev/ops/deploy_credentials.py check
"""

from __future__ import annotations

import argparse
import importlib.util
import subprocess
import sys
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
#: The container every deploy has (compose fixes the name); its existence says a deploy exists.
DEPLOY_MARKER_CONTAINER = "squadops-postgres"

# The decisions live in the package, which the doctor imports; loaded by path here so this runs
# before the venv exists (the module is stdlib only).
_spec = importlib.util.spec_from_file_location(
    "squadops_deploy_credentials",
    REPO / "src" / "squadops" / "bootstrap" / "setup" / "credentials.py",
)
_core = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = _core
_spec.loader.exec_module(_core)
Plan, load_registry, plan, problems, read_env, rotation_targets, generate = (
    _core.Plan,
    _core.load_registry,
    _core.plan,
    _core.problems,
    _core.read_env,
    _core.rotation_targets,
    _core.generate,
)


def deploy_exists(repo: Path = REPO) -> bool:
    """A deploy already runs here, so its services hold some values that must be adopted, never
    replaced. Either sign says so: a secret file bootstrap wrote, or the Postgres container. The
    container alone is not enough: ``docker compose down`` removes it and leaves the volume, and
    the roles in it, behind."""
    registry = load_registry(repo / "infra" / "deploy_credentials.json")
    if any((repo / c["secret_file"]).exists() for c in registry if c.get("secret_file")):
        return True
    probe = subprocess.run(
        ["docker", "inspect", DEPLOY_MARKER_CONTAINER], capture_output=True, check=False
    )
    return probe.returncode == 0


def _write_env(path: Path, updates: Mapping[str, tuple[str, str]]) -> None:
    """Fill an empty ``KEY=`` line in place, else append under one header."""
    lines = path.read_text().splitlines() if path.exists() else []
    pending = dict(updates)
    for i, line in enumerate(lines):
        key = line.partition("=")[0].strip()
        if key in pending and line.strip() == f"{key}=":
            lines[i] = f"{key}={pending.pop(key)[0]}"
    if pending:
        lines += [
            "",
            "# Per-deploy credentials (#2006), written by scripts/dev/ops/deploy_credentials.py",
        ]
        lines += [f"{key}={value}" for key, (value, _how) in pending.items()]
    path.write_text("\n".join(lines) + "\n")


def ensure(repo: Path, *, existing: bool, dry_run: bool) -> Plan:
    registry = load_registry(repo / "infra" / "deploy_credentials.json")
    env_path = repo / ".env"
    held = {
        c["secret_file"]: (repo / c["secret_file"]).read_text()
        for c in registry
        if c.get("secret_file") and (repo / c["secret_file"]).exists()
    }
    decided = plan(registry, read_env(env_path), held, existing=existing)
    for name, (_value, how) in decided.env_updates.items():
        print(f"{'[dry-run] ' if dry_run else ''}{name}: {how} into .env")
    for target in decided.secret_writes:
        print(f"{'[dry-run] ' if dry_run else ''}{target}: written from .env")
    if dry_run:
        return decided
    if decided.env_updates:
        _write_env(env_path, decided.env_updates)
    for target, content in decided.secret_writes.items():
        path = repo / target
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
        path.chmod(0o600)
    return decided


def rotate(repo: Path, *, only: Sequence[str], keep: Sequence[str], dry_run: bool) -> list[str]:
    """Replace the chosen credentials' values in .env with generated ones, after copying .env
    beside itself. Changes .env only: applying the new values to the running services is
    docs/ops/credential_rotation.md, step by step. Prints names, never values."""
    env_path = repo / ".env"
    registry = load_registry(repo / "infra" / "deploy_credentials.json")
    targets = rotation_targets(registry, read_env(env_path), only=only, keep=keep)
    for name in targets:
        print(f"{'[dry-run] ' if dry_run else ''}{name}: a new value into .env")
    if dry_run or not targets:
        return targets
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    backup = env_path.with_name(f".env.pre-rotation-{stamp}")
    backup.write_text(env_path.read_text())
    backup.chmod(0o600)
    print(f"the previous .env: {backup.name}")
    fresh = {name: generate() for name in targets}
    lines = env_path.read_text().splitlines()
    for i, line in enumerate(lines):
        key = line.partition("=")[0].strip()
        if key in fresh and not line.lstrip().startswith("#"):
            lines[i] = f"{key}={fresh[key]}"
    env_path.write_text("\n".join(lines) + "\n")
    return targets


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = parser.add_subparsers(dest="command", required=True)
    e = sub.add_parser("ensure", help="give .env every credential; derive secrets/ from it")
    e.add_argument("--existing", choices=("auto", "yes", "no"), default="auto")
    e.add_argument("--dry-run", action="store_true")
    sub.add_parser("check", help="name each credential missing or holding a committed value")
    r = sub.add_parser("rotate", help="new values into .env for the committed (or named) ones")
    r.add_argument("--only", nargs="*", default=[], help="rotate these, committed or not")
    r.add_argument("--keep", nargs="*", default=[], help="never rotate these")
    r.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    if args.command == "ensure":
        existing = {"yes": True, "no": False}.get(args.existing)
        ensure(
            REPO, existing=deploy_exists() if existing is None else existing, dry_run=args.dry_run
        )
        return 0
    if args.command == "rotate":
        rotate(REPO, only=args.only, keep=args.keep, dry_run=args.dry_run)
        return 0
    found = problems(load_registry(), read_env(REPO / ".env"))
    for line in found:
        print(f"{line}: rotate it (docs/ops/credential_rotation.md)")
    return 1 if found else 0


if __name__ == "__main__":
    sys.exit(main())
