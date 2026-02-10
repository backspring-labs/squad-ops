"""
Auth commands: login, logout, whoami.

login/logout are registered as root commands (squadops login, squadops logout).
whoami is registered under the auth group (squadops auth whoami).
"""

from __future__ import annotations

import getpass
from datetime import UTC, datetime

import httpx
import typer

from squadops.cli import exit_codes
from squadops.cli.auth import (
    _build_token_endpoint,
    clear_token,
    client_credentials_login,
    is_expired,
    load_cached_token,
    password_login,
    save_token,
)
from squadops.cli.output import print_detail, print_error, print_json, print_success

auth_app = typer.Typer(name="auth", help="Authentication management")

# Defaults for local dev
_DEFAULT_KEYCLOAK_URL = "http://localhost:8180"
_DEFAULT_REALM = "squadops-local"
_DEFAULT_CLIENT_ID = "squadops-cli"


def login(
    ctx: typer.Context,
    username: str | None = typer.Option(None, "--username", "-u", help="Username"),
    password: str | None = typer.Option(None, "--password", "-p", help="Password"),
    client_credentials: bool = typer.Option(
        False, "--client-credentials", help="Use client_credentials grant"
    ),
    client_id: str = typer.Option(
        _DEFAULT_CLIENT_ID, "--client-id", help="OIDC client ID"
    ),
    client_secret: str | None = typer.Option(
        None, "--client-secret", help="Client secret (for client_credentials)"
    ),
    keycloak_url: str = typer.Option(
        _DEFAULT_KEYCLOAK_URL, "--keycloak-url", help="Keycloak base URL"
    ),
    realm: str = typer.Option(
        _DEFAULT_REALM, "--realm", help="Keycloak realm"
    ),
    token_endpoint: str | None = typer.Option(
        None, "--token-endpoint", help="Override full token endpoint URL"
    ),
):
    """Authenticate with the SquadOps runtime API."""
    fmt = ctx.obj.get("format", "table") if ctx.obj else "table"
    endpoint = token_endpoint or _build_token_endpoint(keycloak_url, realm)

    try:
        if client_credentials:
            if not client_secret:
                print_error("Error: --client-secret is required with --client-credentials")
                raise typer.Exit(code=exit_codes.GENERAL_ERROR)
            token = client_credentials_login(endpoint, client_id, client_secret)
        else:
            if not username:
                print_error("Error: --username/-u is required for password login")
                raise typer.Exit(code=exit_codes.GENERAL_ERROR)
            if not password:
                password = getpass.getpass("Password: ")
            token = password_login(endpoint, client_id, username, password)
    except httpx.HTTPStatusError as exc:
        status = exc.response.status_code
        if status in (401, 403):
            print_error("Error: invalid credentials")
        else:
            print_error(f"Error: authentication failed (HTTP {status})")
        raise typer.Exit(code=exit_codes.AUTH_ERROR) from None
    except httpx.ConnectError:
        print_error(f"Error: cannot reach {endpoint}")
        raise typer.Exit(code=exit_codes.NETWORK_ERROR) from None
    except httpx.TimeoutException:
        print_error(f"Error: request to {endpoint} timed out")
        raise typer.Exit(code=exit_codes.NETWORK_ERROR) from None

    save_token(token)

    if fmt == "json":
        print_json({
            "status": "authenticated",
            "grant_type": token.grant_type,
            "client_id": token.client_id,
            "expires_at": datetime.fromtimestamp(
                token.expires_at, tz=UTC
            ).isoformat(),
            "has_refresh_token": token.refresh_token is not None,
        })
    else:
        print_success("Login successful")


def logout(ctx: typer.Context):
    """Clear cached authentication token."""
    fmt = ctx.obj.get("format", "table") if ctx.obj else "table"
    removed = clear_token()

    if fmt == "json":
        print_json({"status": "logged_out", "token_removed": removed})
    else:
        if removed:
            print_success("Logged out (token removed)")
        else:
            typer.echo("No cached token found")


@auth_app.command()
def whoami(ctx: typer.Context):
    """Show current authentication status."""
    fmt = ctx.obj.get("format", "table") if ctx.obj else "table"
    token = load_cached_token()

    if token is None:
        if fmt == "json":
            print_json({"status": "unauthenticated"})
        else:
            typer.echo("Not authenticated (no cached token)")
        raise typer.Exit(code=exit_codes.AUTH_ERROR)

    expired = is_expired(token, margin_seconds=0)
    info = {
        "status": "expired" if expired else "authenticated",
        "grant_type": token.grant_type,
        "client_id": token.client_id,
        "expires_at": datetime.fromtimestamp(
            token.expires_at, tz=UTC
        ).isoformat(),
        "has_refresh_token": token.refresh_token is not None,
    }

    if fmt == "json":
        print_json(info)
    else:
        print_detail(info)

    if expired:
        raise typer.Exit(code=exit_codes.AUTH_ERROR)
