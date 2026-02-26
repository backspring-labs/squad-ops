"""
SquadOps CLI entry point (SIP-0065 §6.1).

Typer app with global flags stored in ctx.obj (D7).
Entry point: squadops.cli.main:app (via console_scripts).
"""

from __future__ import annotations

import typer

from squadops.cli.commands.artifacts import artifacts_app, baseline_app
from squadops.cli.commands.auth import auth_app, login, logout
from squadops.cli.commands.cycles import app as cycles_app
from squadops.cli.commands.meta import app as meta_app
from squadops.cli.commands.models import app as models_app
from squadops.cli.commands.profiles import app as profiles_app
from squadops.cli.commands.projects import app as projects_app
from squadops.cli.commands.request_profiles import app as request_profiles_app
from squadops.cli.commands.runs import app as runs_app

app = typer.Typer(
    name="squadops",
    help="SquadOps CLI for cycle execution management (SIP-0065)",
)


def _version_callback(value: bool) -> None:
    """Print version and exit when --version is passed."""
    if value:
        from squadops import __version__

        typer.echo(f"squadops {__version__}")
        raise typer.Exit()


def _validate_format(value: str) -> str:
    if value not in ("table", "json"):
        raise typer.BadParameter(f"Must be 'table' or 'json', got {value!r}")
    return value


@app.callback()
def main(
    ctx: typer.Context,
    version: bool = typer.Option(
        False,
        "--version",
        "-V",
        callback=_version_callback,
        is_eager=True,
        help="Show CLI version and exit.",
    ),
    format: str = typer.Option(
        "table",
        "--format",
        "-o",
        callback=_validate_format,
        help="Output format: table|json",
    ),
    json_flag: bool = typer.Option(False, "--json", help="Shorthand for -o json"),
    quiet: bool = typer.Option(False, "--quiet", "-q", help="Minimal output for scripting"),
):
    """SquadOps CLI — operate the SIP-0064 cycle execution API."""
    ctx.ensure_object(dict)
    ctx.obj["format"] = "json" if json_flag else format  # D7: --json wins
    ctx.obj["quiet"] = quiet


# Register status as a root command (index 1 = status in meta.py)
app.command("status")(meta_app.registered_commands[1].callback)

# Register login/logout as root commands
app.command("login")(login)
app.command("logout")(logout)

# Register command groups
app.add_typer(projects_app, name="projects")
app.add_typer(cycles_app, name="cycles")
app.add_typer(runs_app, name="runs")
app.add_typer(profiles_app, name="squad-profiles")
app.add_typer(artifacts_app, name="artifacts")
app.add_typer(baseline_app, name="baseline")
app.add_typer(auth_app, name="auth")
app.add_typer(request_profiles_app, name="request-profiles")  # SIP-0074
app.add_typer(models_app, name="models")  # SIP-0074
