"""
Model registry + management commands (SIP-0074 §5.10, SIP-0075 §2.4).
"""

from __future__ import annotations

import sys
import time

import typer

from squadops.cli.client import APIClient, CLIError
from squadops.cli.config import load_config
from squadops.cli.output import print_error, print_json, print_success, print_table

app = typer.Typer(name="models", help="View and manage models")


def _get_client(ctx: typer.Context) -> APIClient:
    config = load_config()
    return APIClient(config)


@app.command("list")
def list_models(ctx: typer.Context):
    """List known models with context windows."""
    fmt = ctx.obj.get("format", "table") if ctx.obj else "table"
    quiet = ctx.obj.get("quiet", False) if ctx.obj else False

    try:
        client = _get_client(ctx)
        data = client.get("/api/v1/models")
        client.close()
    except CLIError as e:
        print_error(str(e))
        raise typer.Exit(code=e.exit_code) from None

    if fmt == "json":
        print_json(data)
    else:
        rows = [
            [
                m["name"],
                f"{m['context_window']:,}",
                f"{m['default_max_completion']:,}",
            ]
            for m in data
        ]
        print_table(["Model", "Context Window", "Max Completion"], rows, quiet=quiet)


@app.command("ls", hidden=True)
def list_models_alias(ctx: typer.Context):
    """Alias for list."""
    list_models(ctx)


@app.command("pulled")
def pulled(ctx: typer.Context):
    """List locally pulled models with active profile info."""
    fmt = ctx.obj.get("format", "table") if ctx.obj else "table"
    quiet = ctx.obj.get("quiet", False) if ctx.obj else False

    try:
        client = _get_client(ctx)
        data = client.get("/api/v1/models/pulled")
        client.close()
    except CLIError as e:
        print_error(str(e))
        raise typer.Exit(code=e.exit_code) from None

    if fmt == "json":
        print_json(data)
    else:
        rows = []
        for m in data:
            size = m.get("size_bytes")
            size_str = _format_size(size) if size else "—"
            in_profile = "*" if m.get("in_active_profile") else ""
            agents = ", ".join(m.get("used_by_active_profile", []))
            rows.append([m["name"], size_str, in_profile, agents])
        print_table(
            ["Model", "Size", "Active", "Used By"],
            rows,
            quiet=quiet,
        )


@app.command("pull")
def pull_model(
    ctx: typer.Context,
    name: str = typer.Argument(..., help="Model name to pull (e.g. qwen2.5:7b)"),
):
    """Pull a model from the Ollama registry."""
    try:
        client = _get_client(ctx)
        data = client.post("/api/v1/models/pull", json={"name": name})
    except CLIError as e:
        print_error(str(e))
        raise typer.Exit(code=e.exit_code) from None

    pull_id = data.get("pull_id")
    if not pull_id:
        print_success(f"Pull started for {name}")
        client.close()
        return

    # Poll for completion
    typer.echo(f"Pulling {name}...", nl=False)
    while True:
        time.sleep(2)
        try:
            status_data = client.get(f"/api/v1/models/pull/{pull_id}/status")
        except CLIError:
            typer.echo()
            print_error("Lost connection while polling pull status")
            client.close()
            raise typer.Exit(code=1) from None

        status = status_data.get("status", "")
        if status == "complete":
            typer.echo()
            print_success(f"Model {name} pulled successfully")
            break
        elif status == "failed":
            typer.echo()
            error = status_data.get("error", "unknown error")
            print_error(f"Pull failed: {error}")
            client.close()
            raise typer.Exit(code=1)
        else:
            typer.echo(".", nl=False)
            sys.stdout.flush()

    client.close()


@app.command("remove")
def remove_model(
    ctx: typer.Context,
    name: str = typer.Argument(..., help="Model name to remove"),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation"),
):
    """Remove a locally pulled model."""
    if not yes:
        confirmed = typer.confirm(f"Delete model {name!r}?")
        if not confirmed:
            raise typer.Abort()

    try:
        client = _get_client(ctx)
        client.delete(f"/api/v1/models/{name}")
        client.close()
    except CLIError as e:
        print_error(str(e))
        raise typer.Exit(code=e.exit_code) from None

    print_success(f"Model {name} deleted")


def _format_size(size_bytes: int) -> str:
    """Format bytes into human-readable size."""
    for unit in ("B", "KB", "MB", "GB"):
        if size_bytes < 1024:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f} TB"
