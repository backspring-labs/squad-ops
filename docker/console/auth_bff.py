"""Auth BFF — Backend-for-Frontend OIDC endpoints for SquadOps Console.

Implements PKCE authorization code flow against Keycloak.
Refresh tokens are stored server-side; only access tokens reach the browser.
"""

from __future__ import annotations

import hashlib
import base64
import os
import secrets
import time
from typing import Any

import httpx
from fastapi import APIRouter, HTTPException, Request, Response
from fastapi.responses import RedirectResponse

router = APIRouter(prefix="/auth", tags=["auth"])

# ── Configuration (set by main.py at startup) ───────────────────────────────

_config: dict[str, str] = {}


def configure(
    *,
    keycloak_url: str,
    keycloak_public_url: str,
    client_id: str,
    redirect_uri: str,
) -> None:
    """Inject Keycloak configuration. Called once at startup."""
    _config["keycloak_url"] = keycloak_url.rstrip("/")
    _config["keycloak_public_url"] = keycloak_public_url.rstrip("/")
    _config["client_id"] = client_id
    _config["redirect_uri"] = redirect_uri


def _token_endpoint() -> str:
    return f"{_config['keycloak_url']}/protocol/openid-connect/token"


def _auth_endpoint() -> str:
    return f"{_config['keycloak_public_url']}/protocol/openid-connect/auth"


def _logout_endpoint() -> str:
    return f"{_config['keycloak_url']}/protocol/openid-connect/logout"


# ── In-memory session stores ────────────────────────────────────────────────

_pending_logins: dict[str, dict[str, Any]] = {}  # state → {code_verifier, created_at}
_sessions: dict[str, dict[str, Any]] = {}  # session_id → {refresh_token, created_at}

_LOGIN_TTL_SECONDS = 600  # 10 minutes
_SESSION_TTL_SECONDS = 86400  # 24 hours


def _purge_expired_logins() -> None:
    now = time.time()
    expired = [k for k, v in _pending_logins.items() if now - v["created_at"] > _LOGIN_TTL_SECONDS]
    for k in expired:
        del _pending_logins[k]


def _generate_pkce() -> tuple[str, str]:
    """Generate code_verifier and code_challenge (S256)."""
    code_verifier = base64.urlsafe_b64encode(os.urandom(32)).rstrip(b"=").decode("ascii")
    digest = hashlib.sha256(code_verifier.encode("ascii")).digest()
    code_challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")
    return code_verifier, code_challenge


# ── Routes ───────────────────────────────────────────────────────────────────


@router.get("/login")
async def login() -> dict[str, str]:
    """Generate PKCE challenge and return Keycloak authorization URL.

    Returns JSON ``{"auth_url": "https://..."}``. The shell reads this and
    performs ``window.location = auth_url`` to redirect the browser.
    """
    _purge_expired_logins()

    state = secrets.token_urlsafe(32)
    code_verifier, code_challenge = _generate_pkce()

    _pending_logins[state] = {
        "code_verifier": code_verifier,
        "created_at": time.time(),
    }

    params = {
        "response_type": "code",
        "client_id": _config["client_id"],
        "redirect_uri": _config["redirect_uri"],
        "state": state,
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
        "scope": "openid profile email",
    }
    query = "&".join(f"{k}={v}" for k, v in params.items())
    auth_url = f"{_auth_endpoint()}?{query}"

    return {"auth_url": auth_url}


@router.get("/callback")
async def callback(code: str, state: str) -> Response:
    """Exchange authorization code for tokens.

    Stores refresh token server-side, sets session cookie, redirects to shell.
    The shell then calls /auth/refresh to obtain the access token.
    """
    pending = _pending_logins.pop(state, None)
    if pending is None:
        raise HTTPException(status_code=400, detail="Invalid or expired state parameter")

    if time.time() - pending["created_at"] > _LOGIN_TTL_SECONDS:
        raise HTTPException(status_code=400, detail="Login request expired")

    async with httpx.AsyncClient() as client:
        token_response = await client.post(
            _token_endpoint(),
            data={
                "grant_type": "authorization_code",
                "client_id": _config["client_id"],
                "code": code,
                "redirect_uri": _config["redirect_uri"],
                "code_verifier": pending["code_verifier"],
            },
        )

    if token_response.status_code != 200:
        raise HTTPException(
            status_code=502,
            detail=f"Token exchange failed: {token_response.text}",
        )

    tokens = token_response.json()
    session_id = secrets.token_urlsafe(32)

    _sessions[session_id] = {
        "refresh_token": tokens["refresh_token"],
        "created_at": time.time(),
    }

    response = RedirectResponse(url="/", status_code=302)
    response.set_cookie(
        key="session_id",
        value=session_id,
        httponly=True,
        samesite="lax",
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
    if not session_id or session_id not in _sessions:
        raise HTTPException(status_code=401, detail="No valid session")

    session = _sessions[session_id]

    async with httpx.AsyncClient() as client:
        token_response = await client.post(
            _token_endpoint(),
            data={
                "grant_type": "refresh_token",
                "client_id": _config["client_id"],
                "refresh_token": session["refresh_token"],
            },
        )

    if token_response.status_code != 200:
        # Refresh token expired or revoked — clear session
        _sessions.pop(session_id, None)
        response.delete_cookie("session_id", path="/")
        raise HTTPException(status_code=401, detail="Refresh token expired")

    tokens = token_response.json()

    # Update stored refresh token (Keycloak rotates them)
    _sessions[session_id] = {
        "refresh_token": tokens["refresh_token"],
        "created_at": time.time(),
    }

    return {
        "access_token": tokens["access_token"],
        "expires_in": tokens.get("expires_in", 300),
        "token_type": tokens.get("token_type", "Bearer"),
    }


@router.post("/logout")
async def logout(request: Request, response: Response) -> dict[str, str]:
    """Revoke refresh token at Keycloak and clear session."""
    session_id = request.cookies.get("session_id")

    if session_id and session_id in _sessions:
        session = _sessions.pop(session_id)

        # Best-effort revocation at Keycloak
        try:
            async with httpx.AsyncClient() as client:
                await client.post(
                    _logout_endpoint(),
                    data={
                        "client_id": _config["client_id"],
                        "refresh_token": session["refresh_token"],
                    },
                )
        except Exception:
            pass  # Revocation is best-effort

    response.delete_cookie("session_id", path="/")
    return {"status": "logged_out"}
