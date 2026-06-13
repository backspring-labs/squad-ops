"""Agent commands (SIP-0089 §1.5).

`squadops agent state <agent-id>` reads the SIP-0089 AgentRuntimeState
for an agent and renders it as a table or `--json`.
"""

from __future__ import annotations

import typer

from squadops.cli.client import APIClient, CLIError
from squadops.cli.config import load_config
from squadops.cli.output import print_detail, print_error, print_json

app = typer.Typer(name="agent", help="Inspect agent runtime state (SIP-0089)")


def _get_client(ctx: typer.Context) -> APIClient:
    config = load_config()
    return APIClient(config)


def _derived_availability(state: dict) -> str:
    """Compute idle/busy/paused for display only (per D6 — never stored)."""
    if state.get("current_runtime_activity_id"):
        return "busy"
    if state.get("interruptibility") == "none":
        return "paused"
    return "idle"


@app.command("state")
def state(
    ctx: typer.Context,
    agent_id: str = typer.Argument(..., help="Agent identifier (e.g. max, neo)"),
):
    """Show runtime state for an agent: mode, focus, heartbeat, assignments."""
    fmt = ctx.obj.get("format", "table") if ctx.obj else "table"
    quiet = ctx.obj.get("quiet", False) if ctx.obj else False

    try:
        client = _get_client(ctx)
        try:
            data = client.get(f"/health/agents/{agent_id}/runtime-state")
        finally:
            client.close()
    except CLIError as e:
        print_error(str(e))
        raise typer.Exit(code=e.exit_code) from e

    if fmt == "json":
        print_json(data)
        return

    display = dict(data)
    display["availability"] = _derived_availability(data)
    print_detail(display, quiet=quiet)
