"""
Cycle request profile commands (SIP-0074 §5.10).
"""

from __future__ import annotations

import typer

from squadops.cli.client import APIClient, CLIError
from squadops.cli.config import load_config
from squadops.cli.output import print_detail, print_error, print_json, print_table

app = typer.Typer(name="request-profiles", help="Manage cycle request profiles")


def _get_client(ctx: typer.Context) -> APIClient:
    config = load_config()
    return APIClient(config)


@app.command("list")
def list_request_profiles(ctx: typer.Context):
    """List all cycle request profiles."""
    fmt = ctx.obj.get("format", "table") if ctx.obj else "table"
    quiet = ctx.obj.get("quiet", False) if ctx.obj else False

    try:
        client = _get_client(ctx)
        data = client.get("/api/v1/cycle-request-profiles")
        client.close()
    except CLIError as e:
        print_error(str(e))
        raise typer.Exit(code=e.exit_code) from None

    if fmt == "json":
        print_json(data)
    else:
        rows = [
            [
                p["name"],
                p.get("description", ""),
                str(len(p.get("prompts", {}))),
                str(len(p.get("defaults", {}))),
            ]
            for p in data
        ]
        print_table(["Name", "Description", "Prompts", "Defaults"], rows, quiet=quiet)


@app.command("ls", hidden=True)
def list_request_profiles_alias(ctx: typer.Context):
    """Alias for list."""
    list_request_profiles(ctx)


@app.command("show")
def show_request_profile(ctx: typer.Context, profile_name: str = typer.Argument(...)):
    """Show cycle request profile defaults and prompt metadata."""
    fmt = ctx.obj.get("format", "table") if ctx.obj else "table"
    quiet = ctx.obj.get("quiet", False) if ctx.obj else False

    try:
        client = _get_client(ctx)
        data = client.get(f"/api/v1/cycle-request-profiles/{profile_name}")
        client.close()
    except CLIError as e:
        print_error(str(e))
        raise typer.Exit(code=e.exit_code) from None

    if fmt == "json":
        print_json(data)
    else:
        print_detail(data, quiet=quiet)


@app.command("cat", hidden=True)
def show_request_profile_alias(ctx: typer.Context, profile_name: str = typer.Argument(...)):
    """Alias for show."""
    show_request_profile(ctx, profile_name)
