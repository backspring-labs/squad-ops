"""Tests for the SquadOps Console Auth BFF (Backend-for-Frontend).

Exercises the PKCE authorization code flow routes: login, callback,
refresh, and logout, using httpx.AsyncClient with ASGITransport.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

# Add docker/console to sys.path so we can import the auth_bff module
sys.path.insert(0, str(Path(__file__).parents[3] / "docker" / "console"))
from auth_bff import (  # noqa: E402
    _pending_logins,
    _sessions,
    configure,
    router,
    _LOGIN_TTL_SECONDS,
)


@pytest.fixture(autouse=True)
def _clear_stores():
    """Clear in-memory session/login stores before each test."""
    _pending_logins.clear()
    _sessions.clear()
    yield
    _pending_logins.clear()
    _sessions.clear()


@pytest.fixture()
def auth_app() -> FastAPI:
    """Create a test FastAPI app with the auth BFF router mounted."""
    test_app = FastAPI()
    test_app.include_router(router)
    configure(
        keycloak_url="http://keycloak-test:8080/realms/test",
        keycloak_public_url="http://localhost:8180/realms/test",
        client_id="test-client",
        redirect_uri="http://localhost:4040/auth/callback",
    )
    return test_app


@pytest.fixture()
async def client(auth_app: FastAPI) -> AsyncClient:
    """Create an httpx async client for the test app."""
    transport = ASGITransport(app=auth_app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        yield ac


@pytest.mark.auth
class TestAuthBFF:
    """Tests for Auth BFF routes."""

    async def test_login_returns_auth_url(self, client: AsyncClient):
        """GET /auth/login returns JSON with an auth_url containing expected params."""
        resp = await client.get("/auth/login")
        assert resp.status_code == 200
        body = resp.json()
        assert "auth_url" in body
        auth_url = body["auth_url"]
        assert "state=" in auth_url
        assert "code_challenge=" in auth_url
        assert "client_id=test-client" in auth_url
        assert "code_challenge_method=S256" in auth_url

    async def test_login_creates_pending_login(self, client: AsyncClient):
        """After GET /auth/login, _pending_logins has exactly one entry."""
        await client.get("/auth/login")
        assert len(_pending_logins) == 1
        state = next(iter(_pending_logins))
        entry = _pending_logins[state]
        assert "code_verifier" in entry
        assert "created_at" in entry

    async def test_callback_invalid_state_returns_400(self, client: AsyncClient):
        """GET /auth/callback with unknown state returns 400."""
        resp = await client.get("/auth/callback", params={"code": "abc", "state": "bad-state"})
        assert resp.status_code == 400
        assert "Invalid or expired" in resp.json()["detail"]

    async def test_callback_expired_state_returns_400(self, client: AsyncClient):
        """GET /auth/callback with expired pending login returns 400."""
        state = "expired-state"
        _pending_logins[state] = {
            "code_verifier": "test-verifier",
            "created_at": time.time() - _LOGIN_TTL_SECONDS - 1,
        }
        resp = await client.get("/auth/callback", params={"code": "abc", "state": state})
        assert resp.status_code == 400
        assert "expired" in resp.json()["detail"].lower()

    async def test_callback_success_redirects_and_sets_cookie(self, client: AsyncClient):
        """Successful callback exchanges code, sets session cookie, redirects to /."""
        state = "valid-state"
        _pending_logins[state] = {
            "code_verifier": "test-verifier",
            "created_at": time.time(),
        }

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "access_token": "test-access-token",
            "refresh_token": "test-refresh-token",
            "expires_in": 300,
            "token_type": "Bearer",
        }

        mock_client_instance = AsyncMock()
        mock_client_instance.post.return_value = mock_response
        mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
        mock_client_instance.__aexit__ = AsyncMock(return_value=False)

        with patch("auth_bff.httpx.AsyncClient", return_value=mock_client_instance):
            resp = await client.get(
                "/auth/callback",
                params={"code": "auth-code", "state": state},
                follow_redirects=False,
            )

        # Callback redirects to shell root
        assert resp.status_code == 302
        assert resp.headers["location"] == "/"

        # Verify session cookie was set
        cookies = resp.headers.get_list("set-cookie")
        assert any("session_id=" in c for c in cookies)

        # Verify a session was stored
        assert len(_sessions) == 1

    async def test_refresh_no_session_returns_401(self, client: AsyncClient):
        """POST /auth/refresh without a session cookie returns 401."""
        resp = await client.post("/auth/refresh")
        assert resp.status_code == 401
        assert "No valid session" in resp.json()["detail"]

    async def test_refresh_success(self, client: AsyncClient):
        """POST /auth/refresh with valid session returns new access token."""
        session_id = "test-session-id"
        _sessions[session_id] = {
            "refresh_token": "old-refresh-token",
            "created_at": time.time(),
        }

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "access_token": "new-access-token",
            "refresh_token": "new-refresh-token",
            "expires_in": 300,
            "token_type": "Bearer",
        }

        mock_client_instance = AsyncMock()
        mock_client_instance.post.return_value = mock_response
        mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
        mock_client_instance.__aexit__ = AsyncMock(return_value=False)

        with patch("auth_bff.httpx.AsyncClient", return_value=mock_client_instance):
            resp = await client.post(
                "/auth/refresh", cookies={"session_id": session_id}
            )

        assert resp.status_code == 200
        body = resp.json()
        assert body["access_token"] == "new-access-token"

        # Verify stored refresh token was updated
        assert _sessions[session_id]["refresh_token"] == "new-refresh-token"

    async def test_logout_clears_session(self, client: AsyncClient):
        """POST /auth/logout removes the session from the store."""
        session_id = "logout-session"
        _sessions[session_id] = {
            "refresh_token": "refresh-to-revoke",
            "created_at": time.time(),
        }

        mock_client_instance = AsyncMock()
        mock_client_instance.post.return_value = MagicMock(status_code=200)
        mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
        mock_client_instance.__aexit__ = AsyncMock(return_value=False)

        with patch("auth_bff.httpx.AsyncClient", return_value=mock_client_instance):
            resp = await client.post(
                "/auth/logout", cookies={"session_id": session_id}
            )

        assert resp.status_code == 200
        assert resp.json()["status"] == "logged_out"
        assert session_id not in _sessions

    async def test_logout_without_session_succeeds(self, client: AsyncClient):
        """POST /auth/logout without a session still returns 200."""
        resp = await client.post("/auth/logout")
        assert resp.status_code == 200
        assert resp.json()["status"] == "logged_out"

    async def test_purge_expired_logins(self, client: AsyncClient):
        """Calling login purges expired pending logins."""
        expired_state = "expired-purge-state"
        _pending_logins[expired_state] = {
            "code_verifier": "old-verifier",
            "created_at": time.time() - _LOGIN_TTL_SECONDS - 100,
        }

        # login triggers _purge_expired_logins before creating new entry
        await client.get("/auth/login")

        # Expired entry should have been purged
        assert expired_state not in _pending_logins
        # New entry should exist (the one just created by /login)
        assert len(_pending_logins) == 1
