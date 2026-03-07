"""
Meta commands: version, status (SIP-0065 §6.3).
"""

from __future__ import annotations

import time

import typer

from squadops.cli import exit_codes
from squadops.cli.client import APIClient, CLIError
from squadops.cli.config import load_config
from squadops.cli.output import print_detail, print_error, print_json, print_table

app = typer.Typer(name="meta", help="Meta commands (version, status)")


def _get_bootstrap_info() -> dict | None:
    """Read bootstrap state for status display (R11 — never implies current health)."""
    try:
        from squadops.bootstrap.setup.state import read_state

        # Try each known profile — return the first (most recently written) match
        for profile in ("dev-mac", "dev-pc", "local-spark"):
            state = read_state(profile)
            if state is not None:
                return {
                    "profile": state.profile,
                    "last_run": state.last_run,
                    "doctor_summary": state.doctor_summary,
                }
    except Exception:
        pass
    return None


@app.command()
def version(ctx: typer.Context):
    """Show CLI version (local only; no server call)."""
    from squadops import __version__

    fmt = ctx.obj.get("format", "table") if ctx.obj else "table"
    if fmt == "json":
        print_json({"version": __version__})
    else:
        typer.echo(f"squadops {__version__}")


@app.command()
def status(ctx: typer.Context):
    """Check API and infrastructure status."""
    config = load_config()
    fmt = ctx.obj.get("format", "table") if ctx.obj else "table"
    quiet = ctx.obj.get("quiet", False) if ctx.obj else False

    # --- Runtime API connectivity ---
    runtime_result: dict | None = None
    client: APIClient | None = None
    try:
        client = APIClient(config)
        start = time.monotonic()
        data = client.get("/health")
        elapsed_ms = (time.monotonic() - start) * 1000
        runtime_result = {
            "status": "connected",
            "server_status": data.get("status", "unknown"),
            "server_version": data.get("version", "unknown"),
            "response_time_ms": round(elapsed_ms, 1),
            "base_url": config.base_url,
        }
    except CLIError as e:
        runtime_result = {
            "status": "unreachable",
            "base_url": config.base_url,
            "error": str(e),
        }

    # --- Infrastructure health (now served from runtime-api) ---
    infra_data: list[dict] | None = None
    if client and runtime_result.get("status") == "connected":
        try:
            infra_data = client.get("/health/infra")
        except CLIError:
            infra_data = None

    # --- Agent status (now served from runtime-api) ---
    agents_data: list[dict] | None = None
    if client and runtime_result.get("status") == "connected":
        try:
            agents_data = client.get("/health/agents")
        except CLIError:
            agents_data = None

    if client:
        client.close()

    # --- Bootstrap state (R11 — stale-state behavior) ---
    bootstrap_info = _get_bootstrap_info()

    # --- Render ---
    if fmt == "json":
        combined = {
            "runtime": runtime_result,
            "infrastructure": infra_data,
            "agents": agents_data,
            "bootstrap": bootstrap_info,
        }
        print_json(combined)
        if runtime_result.get("status") != "connected":
            raise typer.Exit(code=exit_codes.NETWORK_ERROR)
        return

    # Table output
    print_detail(runtime_result, quiet=quiet)

    if infra_data is not None:
        typer.echo()
        rows = [
            [
                c.get("component", ""),
                c.get("type", ""),
                c.get("status", ""),
                c.get("version", ""),
                c.get("notes", ""),
            ]
            for c in infra_data
        ]
        print_table(
            ["COMPONENT", "TYPE", "STATUS", "VERSION", "NOTES"],
            rows,
            quiet=quiet,
            title="Infrastructure",
        )
    else:
        typer.echo()
        print_error(f"Infrastructure status unavailable (runtime-api at {config.base_url})")

    if agents_data is not None:
        typer.echo()
        rows = [
            [
                a.get("agent_id", ""),
                a.get("agent_name", ""),
                a.get("role", ""),
                a.get("network_status", ""),
                a.get("lifecycle_state", ""),
                a.get("version", ""),
                a.get("last_seen", "") or "",
            ]
            for a in agents_data
        ]
        print_table(
            ["ID", "NAME", "ROLE", "STATUS", "STATE", "VERSION", "LAST SEEN"],
            rows,
            quiet=quiet,
            title="Agents",
        )
    else:
        typer.echo()
        print_error(f"Agent status unavailable (runtime-api at {config.base_url})")

    # Bootstrap state
    typer.echo()
    if bootstrap_info:
        typer.echo(f"Bootstrap: {bootstrap_info['profile']} (last run: {bootstrap_info['last_run']})")
        typer.echo("  (run `squadops doctor` for current status)")
    else:
        typer.echo("Bootstrap: No bootstrap state found — run `squadops bootstrap <profile>`")

    if runtime_result.get("status") != "connected":
        raise typer.Exit(code=exit_codes.NETWORK_ERROR)
