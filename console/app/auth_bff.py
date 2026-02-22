"""Auth BFF — Backend-for-Frontend OIDC endpoints for SquadOps Console.

Implements PKCE authorization code flow against Keycloak.
Refresh tokens are stored server-side; only access tokens reach the browser.
"""

from __future__ import annotations

import base64
import hashlib
import json as _json
import logging
import os
import secrets
import time
import urllib.parse
from typing import Any

import httpx
from fastapi import APIRouter, HTTPException, Request, Response
from fastapi.responses import RedirectResponse
from session_store import MemorySessionStore, SessionStore

logger = logging.getLogger("squadops.console.auth_bff")

router = APIRouter(prefix="/auth", tags=["auth"])

# ── Configuration (set by main.py at startup) ───────────────────────────────

_config: dict[str, Any] = {}

_session_store: SessionStore = MemorySessionStore()
_login_store: SessionStore = MemorySessionStore()

_http_client: httpx.AsyncClient | None = None

_LOGIN_TTL_SECONDS = 600  # 10 minutes
_SESSION_TTL_SECONDS = 86400  # 24 hours


def configure(
    *,
    keycloak_url: str,
    keycloak_public_url: str,
    client_id: str,
    redirect_uri: str,
    session_store: SessionStore | None = None,
    login_store: SessionStore | None = None,
    secure_cookies: bool = False,
) -> None:
    """Inject Keycloak configuration. Called once at startup."""
    global _session_store, _login_store, _http_client

    _config["keycloak_url"] = keycloak_url.rstrip("/")
    _config["keycloak_public_url"] = keycloak_public_url.rstrip("/")
    _config["client_id"] = client_id
    _config["redirect_uri"] = redirect_uri
    _config["secure_cookies"] = secure_cookies

    if session_store is not None:
        _session_store = session_store
    if login_store is not None:
        _login_store = login_store

    _http_client = httpx.AsyncClient()


async def shutdown() -> None:
    """Close shared resources. Called at app shutdown."""
    global _http_client
    if _http_client:
        await _http_client.aclose()
        _http_client = None
    await _session_store.close()
    await _login_store.close()


def _token_endpoint() -> str:
    return f"{_config['keycloak_url']}/protocol/openid-connect/token"


def _auth_endpoint() -> str:
    return f"{_config['keycloak_public_url']}/protocol/openid-connect/auth"


def _logout_endpoint() -> str:
    return f"{_config['keycloak_url']}/protocol/openid-connect/logout"


def _public_end_session_endpoint() -> str:
    return f"{_config['keycloak_public_url']}/protocol/openid-connect/logout"


def _kc_backchannel_headers() -> dict[str, str]:
    """Return Host header matching the public Keycloak URL.

    Keycloak dynamically derives the token issuer from the request Host header.
    The browser initiates auth at the public URL (e.g. localhost:8180), so tokens
    carry that issuer.  Backchannel calls (token exchange, refresh, logout) go via
    the internal URL (e.g. squadops-keycloak:8080) but must present the public
    Host so Keycloak recognises the token issuer as its own.
    """
    public_url = _config["keycloak_public_url"]
    parsed = urllib.parse.urlparse(public_url)
    return {"Host": parsed.netloc}


def _generate_pkce() -> tuple[str, str]:
    """Generate code_verifier and code_challenge (S256)."""
    code_verifier = base64.urlsafe_b64encode(os.urandom(32)).rstrip(b"=").decode("ascii")
    digest = hashlib.sha256(code_verifier.encode("ascii")).digest()
    code_challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")
    return code_verifier, code_challenge


def _decode_jwt_payload(token: str) -> dict[str, Any]:
    """Base64url-decode the payload segment of a JWT (no signature verification).

    Signature verification is not required here because the token comes directly
    from the Keycloak token endpoint over a trusted internal channel
    (OIDC Core 1.0, Section 3.1.3.7).
    """
    parts = token.split(".")
    if len(parts) != 3:
        raise ValueError("Invalid JWT format")
    # Add padding for base64url
    payload_b64 = parts[1]
    payload_b64 += "=" * (-len(payload_b64) % 4)
    payload_bytes = base64.urlsafe_b64decode(payload_b64)
    return _json.loads(payload_bytes)


def _validate_id_token(id_token: str, expected_nonce: str) -> None:
    """Validate ID token claims: iss, aud, exp, nonce.

    Raises HTTPException on validation failure.
    """
    try:
        claims = _decode_jwt_payload(id_token)
    except (ValueError, _json.JSONDecodeError) as exc:
        raise HTTPException(status_code=502, detail="Invalid ID token") from exc

    # Accept both internal and public Keycloak URLs as valid issuers
    valid_issuers = {_config["keycloak_url"], _config["keycloak_public_url"]}
    if claims.get("iss") not in valid_issuers:
        raise HTTPException(status_code=502, detail="ID token issuer mismatch")

    # Audience must match our client_id
    aud = claims.get("aud")
    if isinstance(aud, list):
        if _config["client_id"] not in aud:
            raise HTTPException(status_code=502, detail="ID token audience mismatch")
    elif aud != _config["client_id"]:
        raise HTTPException(status_code=502, detail="ID token audience mismatch")

    # Token must not be expired
    if claims.get("exp", 0) < time.time():
        raise HTTPException(status_code=502, detail="ID token expired")

    # Nonce must match what we sent
    if claims.get("nonce") != expected_nonce:
        raise HTTPException(status_code=502, detail="ID token nonce mismatch")


# ── Routes ───────────────────────────────────────────────────────────────────


@router.get("/login")
async def login() -> dict[str, str]:
    """Generate PKCE challenge and return Keycloak authorization URL.

    Returns JSON ``{"auth_url": "https://..."}``. The shell reads this and
    performs ``window.location = auth_url`` to redirect the browser.
    """
    state = secrets.token_urlsafe(32)
    nonce = secrets.token_urlsafe(32)
    code_verifier, code_challenge = _generate_pkce()

    await _login_store.set(
        state,
        {"code_verifier": code_verifier, "nonce": nonce},
        _LOGIN_TTL_SECONDS,
    )

    params = {
        "response_type": "code",
        "client_id": _config["client_id"],
        "redirect_uri": _config["redirect_uri"],
        "state": state,
        "nonce": nonce,
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
        "scope": "openid profile email",
    }
    auth_url = f"{_auth_endpoint()}?{urllib.parse.urlencode(params)}"

    return {"auth_url": auth_url}


@router.get("/callback")
async def callback(code: str, state: str) -> Response:
    """Exchange authorization code for tokens.

    Stores refresh token server-side, sets session cookie, redirects to shell.
    The shell then calls /auth/refresh to obtain the access token.
    """
    pending = await _login_store.get(state)
    await _login_store.delete(state)

    if pending is None:
        logger.warning("OIDC callback with invalid/expired state — restarting login")
        return RedirectResponse(url="/", status_code=302)

    assert _http_client is not None
    token_response = await _http_client.post(
        _token_endpoint(),
        data={
            "grant_type": "authorization_code",
            "client_id": _config["client_id"],
            "code": code,
            "redirect_uri": _config["redirect_uri"],
            "code_verifier": pending["code_verifier"],
        },
        headers=_kc_backchannel_headers(),
    )

    if token_response.status_code != 200:
        logger.error("Token exchange failed: %s", token_response.text)
        raise HTTPException(status_code=502, detail="Token exchange failed")

    tokens = token_response.json()

    # Validate ID token (nonce, iss, aud, exp)
    id_token = tokens.get("id_token")
    if id_token:
        _validate_id_token(id_token, expected_nonce=pending["nonce"])

    session_id = secrets.token_urlsafe(32)
    session_data: dict[str, str] = {"refresh_token": tokens["refresh_token"]}
    if id_token:
        session_data["id_token"] = id_token
    await _session_store.set(
        session_id,
        session_data,
        _SESSION_TTL_SECONDS,
    )

    response = RedirectResponse(url="/", status_code=302)
    response.set_cookie(
        key="session_id",
        value=session_id,
        httponly=True,
        samesite="lax",
        secure=_config.get("secure_cookies", False),
        path="/",
        max_age=_SESSION_TTL_SECONDS,
    )

    return response


@router.post("/refresh")
async def refresh(request: Request, response: Response) -> dict[str, Any]:
    """Refresh access token using server-side refresh token.

    Requires session_id cookie.
    """
    session_id = request.cookies.get("session_id")
    if not session_id:
        raise HTTPException(status_code=401, detail="No valid session")

    session = await _session_store.get(session_id)
    if session is None:
        raise HTTPException(status_code=401, detail="No valid session")

    assert _http_client is not None
    token_response = await _http_client.post(
        _token_endpoint(),
        data={
            "grant_type": "refresh_token",
            "client_id": _config["client_id"],
            "refresh_token": session["refresh_token"],
        },
        headers=_kc_backchannel_headers(),
    )

    if token_response.status_code != 200:
        # Refresh token expired or revoked — clear session
        await _session_store.delete(session_id)
        response.delete_cookie("session_id", path="/")
        raise HTTPException(status_code=401, detail="Refresh token expired")

    tokens = token_response.json()

    # Update stored refresh token (Keycloak rotates them) + sliding window
    await _session_store.set(
        session_id,
        {"refresh_token": tokens["refresh_token"]},
        _SESSION_TTL_SECONDS,
    )
    await _session_store.touch(session_id, _SESSION_TTL_SECONDS)

    return {
        "access_token": tokens["access_token"],
        "expires_in": tokens.get("expires_in", 300),
        "token_type": tokens.get("token_type", "Bearer"),
    }


@router.api_route("/logout", methods=["GET", "POST"])
async def logout(request: Request) -> Response:
    """RP-Initiated Logout: revoke tokens, clear session, redirect to Keycloak end_session.

    Ends both the local BFF session and the Keycloak SSO session so the user
    is presented with the login page on next visit.
    """
    session_id = request.cookies.get("session_id")
    id_token_hint = None

    if session_id:
        session = await _session_store.get(session_id)
        await _session_store.delete(session_id)

        if session:
            id_token_hint = session.get("id_token")
            # Best-effort backchannel revocation of the refresh token
            try:
                assert _http_client is not None
                await _http_client.post(
                    _logout_endpoint(),
                    data={
                        "client_id": _config["client_id"],
                        "refresh_token": session["refresh_token"],
                    },
                    headers=_kc_backchannel_headers(),
                )
            except Exception:
                pass  # Revocation is best-effort

    # Build Keycloak end_session URL (browser-facing, uses public URL)
    # Derive post_logout_redirect_uri from the configured redirect_uri
    # e.g. "http://localhost:4040/auth/callback" → "http://localhost:4040/"
    base_url = _config["redirect_uri"].split("/auth/callback")[0] + "/"
    params: dict[str, str] = {
        "client_id": _config["client_id"],
        "post_logout_redirect_uri": base_url,
    }
    if id_token_hint:
        params["id_token_hint"] = id_token_hint

    end_session_url = f"{_public_end_session_endpoint()}?{urllib.parse.urlencode(params)}"

    response = RedirectResponse(url=end_session_url, status_code=302)
    response.delete_cookie("session_id", path="/")
    return response
