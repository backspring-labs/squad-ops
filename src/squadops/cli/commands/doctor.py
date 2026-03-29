"""
Doctor command: validate bootstrap profile contract (SIP-0081).

Runs check functions against the declared profile and reports pass/fail
with fix guidance. Exit code 0 = all pass, 1 = any hard failure.
Heuristic-only warnings do not count as failures.
"""

from __future__ import annotations

import json

import typer

from squadops.bootstrap.setup.checks import CheckResult, run_checks
from squadops.bootstrap.setup.profile import BootstrapProfileError, load_bootstrap_profile


def doctor(
    profile_name: str = typer.Argument(
        ..., help="Bootstrap profile name (dev-mac, dev-pc, local-spark)"
    ),
    check: str | None = typer.Option(None, "--check", help="Run checks for a single category only"),
    json_output: bool = typer.Option(False, "--json", help="Machine-readable JSON output"),
):
    """Validate that the current machine satisfies a bootstrap profile."""
    try:
        profile = load_bootstrap_profile(profile_name)
    except BootstrapProfileError as exc:
        if json_output:
            typer.echo(json.dumps({"error": str(exc)}, indent=2))
        else:
            typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(code=1) from None

    results = run_checks(profile, category=check)

    if json_output:
        _render_json(profile_name, results)
    else:
        _render_table(profile_name, results)

    # Exit code: hard failures (non-heuristic) cause exit 1
    hard_failures = [r for r in results if not r.passed and not r.heuristic]
    if hard_failures:
        raise typer.Exit(code=1)


def _render_json(profile_name: str, results: list[CheckResult]) -> None:
    """Render results as JSON to stdout."""
    total = len(results)
    passed = sum(1 for r in results if r.passed)
    failed = sum(1 for r in results if not r.passed and not r.heuristic)
    heuristic_warnings = sum(1 for r in results if not r.passed and r.heuristic)
    output = {
        "profile": profile_name,
        "checks": [r.to_dict() for r in results],
        "summary": {
            "total": total,
            "passed": passed,
            "failed": failed,
            "heuristic_warnings": heuristic_warnings,
        },
    }
    typer.echo(json.dumps(output, indent=2))


def _render_table(profile_name: str, results: list[CheckResult]) -> None:
    """Render results as formatted text grouped by category."""
    typer.echo(f"Doctor: {profile_name}")
    typer.echo("=" * 50)

    # Group by category
    categories: dict[str, list[CheckResult]] = {}
    for r in results:
        categories.setdefault(r.category, []).append(r)

    for cat, checks in categories.items():
        typer.echo(f"\n[{cat}]")
        for r in checks:
            marker = _marker(r)
            typer.echo(f"  {marker} {r.message}")
            if not r.passed and r.detail:
                typer.echo(f"      {r.detail}")
            if not r.passed and r.fix_command:
                typer.echo(f"      Fix: {r.fix_command}")

    # Summary
    total = len(results)
    passed = sum(1 for r in results if r.passed)
    failed = sum(1 for r in results if not r.passed and not r.heuristic)
    heuristic_warnings = sum(1 for r in results if not r.passed and r.heuristic)
    typer.echo(f"\n{passed}/{total} checks passed", nl=False)
    if failed:
        typer.echo(f", {failed} failed", nl=False)
    if heuristic_warnings:
        typer.echo(f", {heuristic_warnings} warnings", nl=False)
    typer.echo()


def _marker(result: CheckResult) -> str:
    if result.passed:
        return "✓"
    if result.heuristic:
        return "~"
    return "✗"
