"""
Squad profile commands (SIP-0065 §6.3, SIP-0075 CRUD).
"""

from __future__ import annotations

import sys
from pathlib import Path

import typer
import yaml

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
            [
                p["profile_id"],
                p["name"],
                str(p.get("version", "")),
                "*" if p.get("is_active") else "",
                p.get("description", ""),
            ]
            for p in data
        ]
        print_table(["Profile ID", "Name", "Version", "Active", "Description"], rows, quiet=quiet)


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


def _print_warnings(data: dict) -> None:
    """Print warnings from API response to stderr."""
    for w in data.get("warnings", []):
        print(f"Warning: {w}", file=sys.stderr)


@app.command("create")
def create_profile(
    ctx: typer.Context,
    file: Path = typer.Option(..., "--file", "-f", help="YAML file with profile definition"),
):
    """Create a new squad profile from a YAML file."""
    fmt = ctx.obj.get("format", "table") if ctx.obj else "table"

    if not file.exists():
        print_error(f"File not found: {file}")
        raise typer.Exit(code=1)

    with open(file) as f:
        spec = yaml.safe_load(f)

    if not spec or "name" not in spec or "agents" not in spec:
        print_error("YAML must contain 'name' and 'agents' keys")
        raise typer.Exit(code=1)

    payload = {
        "name": spec["name"],
        "description": spec.get("description", ""),
        "agents": spec["agents"],
    }

    try:
        client = _get_client(ctx)
        data = client.post("/api/v1/squad-profiles", json=payload)
        client.close()
    except CLIError as e:
        print_error(str(e))
        raise typer.Exit(code=e.exit_code) from e

    _print_warnings(data)
    if fmt == "json":
        print_json(data)
    else:
        print_success(f"Created profile: {data['profile_id']}")


@app.command("clone")
def clone_profile(
    ctx: typer.Context,
    profile_id: str = typer.Argument(..., help="Source profile ID"),
    name: str = typer.Option(..., "--name", "-n", help="Name for the cloned profile"),
):
    """Clone an existing squad profile with a new name."""
    fmt = ctx.obj.get("format", "table") if ctx.obj else "table"

    try:
        client = _get_client(ctx)
        data = client.post(f"/api/v1/squad-profiles/{profile_id}/clone", json={"name": name})
        client.close()
    except CLIError as e:
        print_error(str(e))
        raise typer.Exit(code=e.exit_code) from e

    _print_warnings(data)
    if fmt == "json":
        print_json(data)
    else:
        print_success(f"Cloned profile: {data['profile_id']}")


@app.command("activate")
def activate_profile(ctx: typer.Context, profile_id: str = typer.Argument(...)):
    """Activate a squad profile (atomic deactivate + activate)."""
    fmt = ctx.obj.get("format", "table") if ctx.obj else "table"

    try:
        client = _get_client(ctx)
        data = client.post(f"/api/v1/squad-profiles/{profile_id}/activate")
        client.close()
    except CLIError as e:
        print_error(str(e))
        raise typer.Exit(code=e.exit_code) from e

    if fmt == "json":
        print_json(data)
    else:
        print_success(f"Activated profile: {profile_id}")


@app.command("delete")
def delete_profile(ctx: typer.Context, profile_id: str = typer.Argument(...)):
    """Delete a squad profile (cannot delete active profile)."""
    fmt = ctx.obj.get("format", "table") if ctx.obj else "table"

    try:
        client = _get_client(ctx)
        data = client.delete(f"/api/v1/squad-profiles/{profile_id}")
        client.close()
    except CLIError as e:
        print_error(str(e))
        raise typer.Exit(code=e.exit_code) from e

    if fmt == "json":
        print_json(data)
    else:
        print_success(f"Deleted profile: {profile_id}")
