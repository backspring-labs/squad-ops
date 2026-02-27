"""
Squad profile commands (SIP-0065 §6.3).
"""

from __future__ import annotations

import typer

from squadops.cli.client import APIClient, CLIError
from squadops.cli.config import load_config
from squadops.cli.output import (
    print_detail,
    print_error,
    print_json,
    print_success,
    print_table,
)

app = typer.Typer(name="squad-profiles", help="Manage squad profiles")


def _get_client(ctx: typer.Context) -> APIClient:
    config = load_config()
    return APIClient(config)


@app.command("list")
def list_profiles(ctx: typer.Context):
    """List all squad profiles."""
    fmt = ctx.obj.get("format", "table") if ctx.obj else "table"
    quiet = ctx.obj.get("quiet", False) if ctx.obj else False

    try:
        client = _get_client(ctx)
        data = client.get("/api/v1/squad-profiles")
        client.close()
    except CLIError as e:
        print_error(str(e))
        raise typer.Exit(code=e.exit_code) from e

    if fmt == "json":
        print_json(data)
    else:
        rows = [
            [p["profile_id"], p["name"], str(p.get("version", "")), p.get("description", "")]
            for p in data
        ]
        print_table(["Profile ID", "Name", "Version", "Description"], rows, quiet=quiet)


@app.command("ls", hidden=True)
def list_profiles_alias(ctx: typer.Context):
    """Alias for list."""
    list_profiles(ctx)


@app.command("show")
def show_profile(ctx: typer.Context, profile_id: str = typer.Argument(...)):
    """Show squad profile details."""
    fmt = ctx.obj.get("format", "table") if ctx.obj else "table"
    quiet = ctx.obj.get("quiet", False) if ctx.obj else False

    try:
        client = _get_client(ctx)
        data = client.get(f"/api/v1/squad-profiles/{profile_id}")
        client.close()
    except CLIError as e:
        print_error(str(e))
        raise typer.Exit(code=e.exit_code) from e

    if fmt == "json":
        print_json(data)
    else:
        print_detail(data, quiet=quiet)


@app.command("cat", hidden=True)
def show_profile_alias(ctx: typer.Context, profile_id: str = typer.Argument(...)):
    """Alias for show."""
    show_profile(ctx, profile_id)


@app.command("active")
def active_profile(ctx: typer.Context):
    """Show the active squad profile."""
    fmt = ctx.obj.get("format", "table") if ctx.obj else "table"
    quiet = ctx.obj.get("quiet", False) if ctx.obj else False

    try:
        client = _get_client(ctx)
        data = client.get("/api/v1/squad-profiles/active")
        client.close()
    except CLIError as e:
        print_error(str(e))
        raise typer.Exit(code=e.exit_code) from e

    if fmt == "json":
        print_json(data)
    else:
        print_detail(data, quiet=quiet)


@app.command("set-active")
def set_active_profile(ctx: typer.Context, profile_id: str = typer.Argument(...)):
    """Set the active squad profile."""
    fmt = ctx.obj.get("format", "table") if ctx.obj else "table"

    try:
        client = _get_client(ctx)
        data = client.post("/api/v1/squad-profiles/active", json={"profile_id": profile_id})
        client.close()
    except CLIError as e:
        print_error(str(e))
        raise typer.Exit(code=e.exit_code) from e

    if fmt == "json":
        print_json(data)
    else:
        print_success(f"Active profile set to {profile_id}")
