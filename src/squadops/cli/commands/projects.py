"""
Project commands (SIP-0065 §6.3).
"""

from __future__ import annotations

import typer

from squadops.cli import exit_codes
from squadops.cli.client import APIClient, CLIError
from squadops.cli.config import load_config
from squadops.cli.output import print_detail, print_error, print_json, print_table

app = typer.Typer(name="projects", help="Manage projects")


def _get_client(ctx: typer.Context) -> APIClient:
    config = load_config()
    return APIClient(config)


@app.command("list")
def list_projects(ctx: typer.Context):
    """List all projects."""
    fmt = ctx.obj.get("format", "table") if ctx.obj else "table"
    quiet = ctx.obj.get("quiet", False) if ctx.obj else False

    try:
        client = _get_client(ctx)
        data = client.get("/api/v1/projects")
        client.close()
    except CLIError as e:
        print_error(str(e))
        raise typer.Exit(code=e.exit_code)

    if fmt == "json":
        print_json(data)
    else:
        rows = [
            [p["project_id"], p["name"], p.get("description", "")]
            for p in data
        ]
        print_table(["Project ID", "Name", "Description"], rows, quiet=quiet)


@app.command("ls", hidden=True)
def list_projects_alias(ctx: typer.Context):
    """Alias for list."""
    list_projects(ctx)


@app.command("show")
def show_project(ctx: typer.Context, project_id: str = typer.Argument(...)):
    """Show project details."""
    fmt = ctx.obj.get("format", "table") if ctx.obj else "table"
    quiet = ctx.obj.get("quiet", False) if ctx.obj else False

    try:
        client = _get_client(ctx)
        data = client.get(f"/api/v1/projects/{project_id}")
        client.close()
    except CLIError as e:
        print_error(str(e))
        raise typer.Exit(code=e.exit_code)

    if fmt == "json":
        print_json(data)
    else:
        print_detail(data, quiet=quiet)


@app.command("cat", hidden=True)
def show_project_alias(ctx: typer.Context, project_id: str = typer.Argument(...)):
    """Alias for show."""
    show_project(ctx, project_id)
