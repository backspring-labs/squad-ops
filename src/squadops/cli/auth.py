"""
Token storage and OIDC helpers for CLI authentication.

Provides cached token persistence (~/.config/squadops/token.json),
OIDC password/client-credentials login, and silent token refresh.
No passwords are stored on disk — only OIDC tokens.
"""

from __future__ import annotations

import json
import os
import stat
import time
from dataclasses import asdict, dataclass
from pathlib import Path

import httpx


@dataclass
class CachedToken:
    """Persisted OIDC token with metadata for refresh."""

    access_token: str
    refresh_token: str | None
    expires_at: float  # time.time() epoch
    token_endpoint: str  # for refresh requests
    client_id: str
    grant_type: str  # "password" | "client_credentials"


def _token_path() -> Path:
    """Resolve token file path respecting XDG_CONFIG_HOME."""
    xdg = os.environ.get("XDG_CONFIG_HOME")
    if xdg:
        return Path(xdg) / "squadops" / "token.json"
    return Path.home() / ".config" / "squadops" / "token.json"


def load_cached_token() -> CachedToken | None:
    """Load cached token from disk. Returns None if missing or malformed."""
    path = _token_path()
    if not path.is_file():
        return None
    try:
        raw = json.loads(path.read_text())
        return CachedToken(
            access_token=raw["access_token"],
            refresh_token=raw.get("refresh_token"),
            expires_at=raw["expires_at"],
            token_endpoint=raw["token_endpoint"],
            client_id=raw["client_id"],
            grant_type=raw["grant_type"],
        )
    except (json.JSONDecodeError, KeyError, TypeError):
        return None


def save_token(token: CachedToken) -> None:
    """Write token to disk with restricted permissions (0600)."""
    path = _token_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(asdict(token), indent=2))
    path.chmod(stat.S_IRUSR | stat.S_IWUSR)


def clear_token() -> bool:
    """Delete the cached token file. Returns True if a file was removed."""
    path = _token_path()
    if path.is_file():
        path.unlink()
        return True
    return False


def is_expired(token: CachedToken, margin_seconds: int = 30) -> bool:
    """Check whether the token is expired (with safety margin)."""
    return time.time() >= (token.expires_at - margin_seconds)


def _build_token_endpoint(keycloak_url: str, realm: str) -> str:
    """Build the OIDC token endpoint URL."""
    return f"{keycloak_url}/realms/{realm}/protocol/openid-connect/token"


def _parse_token_response(
    data: dict,
    token_endpoint: str,
    client_id: str,
    grant_type: str,
) -> CachedToken:
    """Parse an OIDC token response into a CachedToken."""
    expires_in = data.get("expires_in", 300)
    return CachedToken(
        access_token=data["access_token"],
        refresh_token=data.get("refresh_token"),
        expires_at=time.time() + expires_in,
        token_endpoint=token_endpoint,
        client_id=client_id,
        grant_type=grant_type,
    )


def password_login(
    token_endpoint: str,
    client_id: str,
    username: str,
    password: str,
) -> CachedToken:
    """Perform OIDC Resource Owner Password Credentials login.

    Raises:
        httpx.HTTPStatusError: On non-2xx response.
    """
    resp = httpx.post(
        token_endpoint,
        data={
            "grant_type": "password",
            "client_id": client_id,
            "username": username,
            "password": password,
        },
        timeout=15,
    )
    resp.raise_for_status()
    return _parse_token_response(resp.json(), token_endpoint, client_id, "password")


def client_credentials_login(
    token_endpoint: str,
    client_id: str,
    client_secret: str,
) -> CachedToken:
    """Perform OIDC Client Credentials login.

    Raises:
        httpx.HTTPStatusError: On non-2xx response.
    """
    resp = httpx.post(
        token_endpoint,
        data={
            "grant_type": "client_credentials",
            "client_id": client_id,
            "client_secret": client_secret,
        },
        timeout=15,
    )
    resp.raise_for_status()
    return _parse_token_response(resp.json(), token_endpoint, client_id, "client_credentials")


def refresh_access_token(token: CachedToken) -> CachedToken | None:
    """Attempt to refresh the access token. Returns None on any failure."""
    if not token.refresh_token:
        return None
    try:
        resp = httpx.post(
            token.token_endpoint,
            data={
                "grant_type": "refresh_token",
                "client_id": token.client_id,
                "refresh_token": token.refresh_token,
            },
            timeout=15,
        )
        resp.raise_for_status()
        return _parse_token_response(
            resp.json(), token.token_endpoint, token.client_id, token.grant_type
        )
    except (httpx.HTTPError, KeyError):
        return None
