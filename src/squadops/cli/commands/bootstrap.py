"""
Bootstrap command: profile-driven environment setup (SIP-0081).

CLI wrapper over scripts/bootstrap/bootstrap.sh (R2). Validates the profile
schema before invoking shell, writes state file on completion (R3), and
auto-runs doctor at the end.
"""

from __future__ import annotations

import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

import typer

from squadops.bootstrap.setup.checks import run_checks
from squadops.bootstrap.setup.profile import BootstrapProfileError, load_bootstrap_profile
from squadops.bootstrap.setup.state import BootstrapState, write_state

_BOOTSTRAP_SCRIPT = Path(__file__).resolve().parents[4] / "scripts" / "bootstrap" / "bootstrap.sh"

app = typer.Typer(name="bootstrap", help="Profile-driven environment bootstrap")


@app.command()
def bootstrap(
    profile_name: str = typer.Argument(
        ..., help="Bootstrap profile (dev-mac, dev-pc, local-spark)"
    ),
    skip_docker: bool = typer.Option(False, "--skip-docker", help="Skip Docker service startup"),
    skip_models: bool = typer.Option(False, "--skip-models", help="Skip Ollama model pulls"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Show what would be done"),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation prompts"),
) -> None:
    """Bootstrap the local environment for a given profile."""
    # 1. Validate profile schema before any install (fail fast)
    try:
        profile = load_bootstrap_profile(profile_name)
    except BootstrapProfileError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(code=1) from None

    typer.echo(f"Bootstrapping profile: {profile_name}")

    # 2. Verify bootstrap script exists (installed package without repo check)
    if not _BOOTSTRAP_SCRIPT.is_file():
        typer.echo(
            f"Error: Bootstrap script not found at {_BOOTSTRAP_SCRIPT}\n"
            "Run ./scripts/bootstrap/bootstrap.sh directly from the repo checkout.",
            err=True,
        )
        raise typer.Exit(code=1) from None

    # 3. Build shell command
    cmd: list[str] = ["bash", str(_BOOTSTRAP_SCRIPT), profile_name]
    if skip_docker:
        cmd.append("--skip-docker")
    if skip_models:
        cmd.append("--skip-models")
    if dry_run:
        cmd.append("--dry-run")
    if yes:
        cmd.append("--yes")

    # 4. Shell out to bootstrap.sh (R2 — CLI wraps shell)
    result = subprocess.run(cmd, cwd=_BOOTSTRAP_SCRIPT.parents[1].parent)
    if result.returncode != 0:
        typer.echo("Bootstrap script failed.", err=True)
        raise typer.Exit(code=result.returncode) from None

    # 5. Write state file (R3 — Python CLI owns state)
    if not dry_run:
        doctor_results = run_checks(profile)
        summary = {
            "total": len(doctor_results),
            "passed": sum(1 for r in doctor_results if r.passed),
            "failed": sum(1 for r in doctor_results if not r.passed and not r.heuristic),
            "heuristic": sum(1 for r in doctor_results if not r.passed and r.heuristic),
        }
        state = BootstrapState(
            profile=profile_name,
            schema_version=profile.schema_version,
            last_run=datetime.now(UTC).isoformat(),
            steps_completed=_detect_completed_steps(profile_name, skip_docker, skip_models),
            detected_versions=_detect_versions(),
            doctor_summary=summary,
        )
        write_state(state)
        typer.echo(f"\nDoctor: {summary['passed']}/{summary['total']} checks passed", nl=False)
        if summary["failed"]:
            typer.echo(f", {summary['failed']} failed", nl=False)
        if summary["heuristic"]:
            typer.echo(f", {summary['heuristic']} warnings", nl=False)
        typer.echo()


def _detect_completed_steps(
    profile_name: str, skip_docker: bool, skip_models: bool
) -> list[str]:
    """Build list of steps that were run (best-effort)."""
    steps = ["system_deps", "python"]
    if not skip_docker:
        steps.append("docker")
    if not skip_models:
        steps.append("models")
    return steps


def _detect_versions() -> dict[str, str]:
    """Detect installed tool versions (best-effort)."""
    versions: dict[str, str] = {}
    try:
        out = subprocess.run(
            [sys.executable, "--version"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if out.returncode == 0:
            versions["python"] = out.stdout.strip().replace("Python ", "")
    except (OSError, subprocess.TimeoutExpired):
        pass
    return versions
