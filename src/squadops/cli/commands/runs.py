"""
Run commands (SIP-0065 §6.3).
"""

from __future__ import annotations

from typing import Optional

import typer

from squadops.cli import exit_codes
from squadops.cli.client import APIClient, CLIError
from squadops.cli.config import load_config
from squadops.cli.output import (
    print_detail,
    print_error,
    print_json,
    print_success,
    print_table,
)

app = typer.Typer(name="runs", help="Manage execution runs within cycles")


def _get_client(ctx: typer.Context) -> APIClient:
    config = load_config()
    return APIClient(config)


@app.command("list")
def list_runs(
    ctx: typer.Context,
    project_id: str = typer.Argument(...),
    cycle_id: str = typer.Argument(...),
):
    """List runs for a cycle."""
    fmt = ctx.obj.get("format", "table") if ctx.obj else "table"
    quiet = ctx.obj.get("quiet", False) if ctx.obj else False

    try:
        client = _get_client(ctx)
        data = client.get(f"/api/v1/projects/{project_id}/cycles/{cycle_id}/runs")
        client.close()
    except CLIError as e:
        print_error(str(e))
        raise typer.Exit(code=e.exit_code)

    if fmt == "json":
        print_json(data)
    else:
        rows = [
            [r["run_id"], str(r["run_number"]), r["status"], r.get("started_at", "")]
            for r in data
        ]
        print_table(["Run ID", "#", "Status", "Started"], rows, quiet=quiet)


@app.command("ls", hidden=True)
def list_runs_alias(ctx: typer.Context, project_id: str = typer.Argument(...), cycle_id: str = typer.Argument(...)):
    """Alias for list."""
    list_runs(ctx, project_id, cycle_id)


@app.command("show")
def show_run(
    ctx: typer.Context,
    project_id: str = typer.Argument(...),
    cycle_id: str = typer.Argument(...),
    run_id: str = typer.Argument(...),
):
    """Show run details."""
    fmt = ctx.obj.get("format", "table") if ctx.obj else "table"
    quiet = ctx.obj.get("quiet", False) if ctx.obj else False

    try:
        client = _get_client(ctx)
        data = client.get(
            f"/api/v1/projects/{project_id}/cycles/{cycle_id}/runs/{run_id}"
        )
        client.close()
    except CLIError as e:
        print_error(str(e))
        raise typer.Exit(code=e.exit_code)

    if fmt == "json":
        print_json(data)
    else:
        print_detail(data, quiet=quiet)


@app.command("cat", hidden=True)
def show_run_alias(ctx: typer.Context, project_id: str = typer.Argument(...), cycle_id: str = typer.Argument(...), run_id: str = typer.Argument(...)):
    """Alias for show."""
    show_run(ctx, project_id, cycle_id, run_id)


@app.command("retry")
def retry_run(
    ctx: typer.Context,
    project_id: str = typer.Argument(...),
    cycle_id: str = typer.Argument(...),
):
    """Create a new run (retry) for a cycle.

    Creates an execution record. Does not trigger task execution
    (deferred to a future release).
    """
    fmt = ctx.obj.get("format", "table") if ctx.obj else "table"

    try:
        client = _get_client(ctx)
        data = client.post(f"/api/v1/projects/{project_id}/cycles/{cycle_id}/runs")
        client.close()
    except CLIError as e:
        print_error(str(e))
        raise typer.Exit(code=e.exit_code)

    if fmt == "json":
        print_json(data)
    else:
        print_success(f"Run {data.get('run_id', '')} created")


@app.command("cancel")
def cancel_run(
    ctx: typer.Context,
    project_id: str = typer.Argument(...),
    cycle_id: str = typer.Argument(...),
    run_id: str = typer.Argument(...),
):
    """Cancel a run."""
    fmt = ctx.obj.get("format", "table") if ctx.obj else "table"

    try:
        client = _get_client(ctx)
        data = client.post(
            f"/api/v1/projects/{project_id}/cycles/{cycle_id}/runs/{run_id}/cancel"
        )
        client.close()
    except CLIError as e:
        print_error(str(e))
        raise typer.Exit(code=e.exit_code)

    if fmt == "json":
        print_json(data)
    else:
        print_success(f"Run {run_id} cancelled")


@app.command("gate")
def gate_decision(
    ctx: typer.Context,
    project_id: str = typer.Argument(...),
    cycle_id: str = typer.Argument(...),
    run_id: str = typer.Argument(...),
    gate_name: str = typer.Argument(...),
    approve: bool = typer.Option(False, "--approve", help="Approve the gate"),
    reject: bool = typer.Option(False, "--reject", help="Reject the gate"),
    notes: Optional[str] = typer.Option(None, "--notes", help="Decision notes"),
):
    """Record a gate decision (approve or reject).

    Wire mapping (D8): --approve sends {"decision": "approved"},
    --reject sends {"decision": "rejected"}.
    """
    fmt = ctx.obj.get("format", "table") if ctx.obj else "table"

    if approve == reject:
        # Both true or both false
        print_error("Error: must specify exactly one of --approve or --reject")
        raise typer.Exit(code=2)

    # D8: CLI imperative → wire past tense
    decision = "approved" if approve else "rejected"

    body = {"decision": decision}
    if notes:
        body["notes"] = notes

    try:
        client = _get_client(ctx)
        data = client.post(
            f"/api/v1/projects/{project_id}/cycles/{cycle_id}/runs/{run_id}/gates/{gate_name}",
            json=body,
        )
        client.close()
    except CLIError as e:
        print_error(str(e))
        raise typer.Exit(code=e.exit_code)

    if fmt == "json":
        print_json(data)
    else:
        print_success(f"Gate {gate_name!r} {decision}")
