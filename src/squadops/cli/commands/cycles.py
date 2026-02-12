"""
Cycle commands (SIP-0065 §6.3).
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
from squadops.contracts.cycle_request_profiles import (
    compute_overrides,
    load_profile,
    merge_config,
)
from squadops.cycles.lifecycle import compute_config_hash

app = typer.Typer(name="cycles", help="Manage experiment cycles")


def _get_client(ctx: typer.Context) -> APIClient:
    config = load_config()
    return APIClient(config)


def _parse_set_flags(set_flags: list[str]) -> dict:
    """Parse --set key=value flags into a dict."""
    result = {}
    for item in set_flags:
        if "=" not in item:
            raise typer.BadParameter(f"Invalid --set format: {item!r}. Expected key=value.")
        key, value = item.split("=", 1)
        result[key.strip()] = value.strip()
    return result


@app.command("create")
def create_cycle(
    ctx: typer.Context,
    project_id: str = typer.Argument(...),
    profile: str = typer.Option("default", "--profile", help="CRP profile name"),
    prd: Optional[str] = typer.Option(None, "--prd", help="PRD artifact ID"),
    squad_profile_id: str = typer.Option(..., "--squad-profile", help="Squad profile ID"),
    set_flags: Optional[list[str]] = typer.Option(None, "--set", help="Override: key=value"),
    notes: Optional[str] = typer.Option(None, "--notes", help="Experiment notes"),
):
    """Create a new experiment cycle.

    Creates an experiment record. Does not trigger task execution
    (deferred to a future release).
    """
    fmt = ctx.obj.get("format", "table") if ctx.obj else "table"

    # 1. Load CRP profile
    try:
        crp = load_profile(profile)
    except FileNotFoundError as e:
        print_error(str(e))
        raise typer.Exit(code=exit_codes.GENERAL_ERROR)

    # 2. Parse --set flags
    user_values = _parse_set_flags(set_flags or [])

    # 3. Merge CRP defaults with user values to get full config
    merged = merge_config(crp.defaults, user_values)

    # 4. Compute overrides (only fields that differ from CRP defaults)
    overrides = compute_overrides(crp.defaults, merged)

    # 5. Compute local hash for verification
    local_hash = compute_config_hash(crp.defaults, overrides)

    # 6. Build request body
    body = {
        "squad_profile_id": squad_profile_id,
        "applied_defaults": crp.defaults,
        "execution_overrides": overrides,
        "notes": notes,
    }
    if prd:
        body["prd_ref"] = prd

    # Merge known CRP defaults into body where they map to top-level DTO fields
    if "build_strategy" in merged:
        body["build_strategy"] = merged["build_strategy"]
    if "task_flow_policy" in merged:
        body["task_flow_policy"] = merged["task_flow_policy"]
    if "expected_artifact_types" in merged:
        body["expected_artifact_types"] = merged["expected_artifact_types"]
    if "experiment_context" in merged:
        body["experiment_context"] = merged["experiment_context"]

    # 7. POST to API
    try:
        client = _get_client(ctx)
        data = client.post(f"/api/v1/projects/{project_id}/cycles", json=body)
        client.close()
    except CLIError as e:
        print_error(str(e))
        raise typer.Exit(code=e.exit_code)

    # 8. Verify hash round-trip
    server_hash = data.get("resolved_config_hash", "")
    if server_hash and server_hash != local_hash:
        print_error(
            f"Warning: hash mismatch — local={local_hash[:12]}… server={server_hash[:12]}…"
        )

    if fmt == "json":
        print_json(data)
    else:
        print_success(f"Cycle {data['cycle_id']} created (run {data['run_id']})")
        print_detail({
            "cycle_id": data["cycle_id"],
            "run_id": data["run_id"],
            "status": data["status"],
            "hash": data.get("resolved_config_hash", ""),
        })


@app.command("list")
def list_cycles(
    ctx: typer.Context,
    project_id: str = typer.Argument(...),
    status: Optional[str] = typer.Option(None, "--status", help="Filter by status"),
):
    """List cycles for a project."""
    fmt = ctx.obj.get("format", "table") if ctx.obj else "table"
    quiet = ctx.obj.get("quiet", False) if ctx.obj else False

    params = {}
    if status:
        params["status"] = status

    try:
        client = _get_client(ctx)
        data = client.get(f"/api/v1/projects/{project_id}/cycles", params=params)
        client.close()
    except CLIError as e:
        print_error(str(e))
        raise typer.Exit(code=e.exit_code)

    if fmt == "json":
        print_json(data)
    else:
        rows = [
            [c["cycle_id"], c.get("status", ""), c.get("build_strategy", ""), c.get("created_at", "")]
            for c in data
        ]
        print_table(["Cycle ID", "Status", "Strategy", "Created"], rows, quiet=quiet)


@app.command("ls", hidden=True)
def list_cycles_alias(ctx: typer.Context, project_id: str = typer.Argument(...), status: Optional[str] = typer.Option(None, "--status")):
    """Alias for list."""
    list_cycles(ctx, project_id, status)


@app.command("show")
def show_cycle(
    ctx: typer.Context,
    project_id: str = typer.Argument(...),
    cycle_id: str = typer.Argument(...),
):
    """Show cycle details."""
    fmt = ctx.obj.get("format", "table") if ctx.obj else "table"
    quiet = ctx.obj.get("quiet", False) if ctx.obj else False

    try:
        client = _get_client(ctx)
        data = client.get(f"/api/v1/projects/{project_id}/cycles/{cycle_id}")
        client.close()
    except CLIError as e:
        print_error(str(e))
        raise typer.Exit(code=e.exit_code)

    if fmt == "json":
        print_json(data)
    else:
        print_detail(data, quiet=quiet)


@app.command("cat", hidden=True)
def show_cycle_alias(ctx: typer.Context, project_id: str = typer.Argument(...), cycle_id: str = typer.Argument(...)):
    """Alias for show."""
    show_cycle(ctx, project_id, cycle_id)


@app.command("cancel")
def cancel_cycle(
    ctx: typer.Context,
    project_id: str = typer.Argument(...),
    cycle_id: str = typer.Argument(...),
):
    """Cancel a cycle."""
    fmt = ctx.obj.get("format", "table") if ctx.obj else "table"

    try:
        client = _get_client(ctx)
        data = client.post(f"/api/v1/projects/{project_id}/cycles/{cycle_id}/cancel")
        client.close()
    except CLIError as e:
        print_error(str(e))
        raise typer.Exit(code=e.exit_code)

    if fmt == "json":
        print_json(data)
    else:
        print_success(f"Cycle {cycle_id} cancelled")
