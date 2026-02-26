"""
Model registry commands (SIP-0074 §5.10).
"""

from __future__ import annotations

import typer

from squadops.cli.client import APIClient, CLIError
from squadops.cli.config import load_config
from squadops.cli.output import print_error, print_json, print_table

app = typer.Typer(name="models", help="View model registry information")


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
        print_table(
            ["Model", "Context Window", "Max Completion"], rows, quiet=quiet
        )


@app.command("ls", hidden=True)
def list_models_alias(ctx: typer.Context):
    """Alias for list."""
    list_models(ctx)
