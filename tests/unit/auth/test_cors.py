"""Tests for CORS middleware on Runtime API (SIP-0062 Phase 3a)."""

from datetime import UTC
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.testclient import TestClient

from squadops.api.middleware.auth import AuthMiddleware, RequestIDMiddleware
from squadops.api.routes.auth import router as auth_router
from squadops.auth.models import Identity, TokenClaims


def _make_auth_port():
    from datetime import datetime

    port = AsyncMock()
    port.validate_token.return_value = TokenClaims(
        subject="u1",
        issuer="http://keycloak/realms/test",
        audience="test",
        expires_at=datetime.now(UTC),
        issued_at=datetime.now(UTC),
    )
    port.resolve_identity.return_value = Identity(
        user_id="u1",
        display_name="User One",
        roles=("admin",),
        scopes=("openid",),
        identity_type="human",
    )
    return port


def _build_app(allowed_origins=None, auth_port=None):
    """Build a minimal app with CORS + auth middleware + auth routes."""
    app = FastAPI()
    app.include_router(auth_router)

    if allowed_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=allowed_origins,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    app.add_middleware(
        AuthMiddleware,
        auth_port=auth_port or _make_auth_port(),
        provider="keycloak",
    )
    app.add_middleware(RequestIDMiddleware)
    return app


@pytest.mark.auth
class TestCORS:
    def test_preflight_from_allowed_origin_returns_cors_headers(self):
        app = _build_app(allowed_origins=["http://localhost:8000"])
        client = TestClient(app)

        resp = client.options(
            "/auth/userinfo",
            headers={
                "Origin": "http://localhost:8000",
                "Access-Control-Request-Method": "GET",
                "Access-Control-Request-Headers": "Authorization",
            },
        )
        assert resp.status_code == 200
        assert resp.headers.get("access-control-allow-origin") == "http://localhost:8000"

    def test_preflight_does_not_trigger_auth(self):
        """OPTIONS preflight must never trigger auth (returns 200, not 401)."""
        app = _build_app(
            allowed_origins=["http://localhost:8000"],
            auth_port=_make_auth_port(),
        )
        client = TestClient(app)

        resp = client.options(
            "/auth/userinfo",
            headers={
                "Origin": "http://localhost:8000",
                "Access-Control-Request-Method": "GET",
            },
        )
        # Must be 200, not 401 or 503
        assert resp.status_code == 200

    def test_unknown_origin_gets_no_cors_headers(self):
        app = _build_app(allowed_origins=["http://localhost:8000"])
        client = TestClient(app)

        resp = client.options(
            "/auth/userinfo",
            headers={
                "Origin": "http://evil.com",
                "Access-Control-Request-Method": "GET",
            },
        )
        assert resp.headers.get("access-control-allow-origin") is None

    def test_userinfo_includes_cors_headers_for_allowed_origin(self):
        auth_port = _make_auth_port()
        app = _build_app(
            allowed_origins=["http://localhost:8000"],
            auth_port=auth_port,
        )
        client = TestClient(app)

        resp = client.get(
            "/auth/userinfo",
            headers={
                "Authorization": "Bearer valid-token",
                "Origin": "http://localhost:8000",
            },
        )
        assert resp.status_code == 200
        assert resp.headers.get("access-control-allow-origin") == "http://localhost:8000"

    def test_no_cors_middleware_means_no_cors_headers(self):
        """Without CORS middleware, no CORS headers appear."""
        app = _build_app(allowed_origins=None, auth_port=_make_auth_port())
        client = TestClient(app)

        resp = client.get(
            "/auth/userinfo",
            headers={
                "Authorization": "Bearer valid",
                "Origin": "http://localhost:8000",
            },
        )
        assert resp.status_code == 200
        assert "access-control-allow-origin" not in resp.headers
