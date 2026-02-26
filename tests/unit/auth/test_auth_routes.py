"""Tests for /auth/userinfo endpoint (SIP-0062 Phase 3a)."""

from datetime import UTC
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from squadops.api.middleware.auth import AuthMiddleware, RequestIDMiddleware
from squadops.api.routes.auth import router as auth_router
from squadops.auth.models import Identity


def _make_app(auth_port=None, provider="keycloak"):
    """Build a minimal app with auth middleware and the auth router."""
    app = FastAPI()
    app.include_router(auth_router)
    app.add_middleware(
        AuthMiddleware,
        auth_port=auth_port,
        provider=provider,
    )
    app.add_middleware(RequestIDMiddleware)
    return app


def _make_auth_port(identity=None):
    from datetime import datetime

    from squadops.auth.models import TokenClaims

    port = AsyncMock()
    port.validate_token.return_value = TokenClaims(
        subject=identity.user_id if identity else "u1",
        issuer="http://keycloak/realms/test",
        audience="test",
        expires_at=datetime.now(UTC),
        issued_at=datetime.now(UTC),
    )
    port.resolve_identity.return_value = identity or Identity(
        user_id="u1",
        display_name="User One",
        roles=("admin",),
        scopes=("openid",),
        identity_type="human",
    )
    return port


@pytest.mark.auth
class TestUserinfoEndpoint:
    def test_returns_identity_when_authenticated(self):
        identity = Identity(
            user_id="user-42",
            display_name="Alice",
            roles=("admin", "operator"),
            scopes=("openid", "profile"),
            identity_type="human",
        )
        app = _make_app(auth_port=_make_auth_port(identity))
        client = TestClient(app)

        resp = client.get("/auth/userinfo", headers={"Authorization": "Bearer valid"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["user_id"] == "user-42"
        assert data["display_name"] == "Alice"
        assert data["roles"] == ["admin", "operator"]
        assert data["scopes"] == ["openid", "profile"]
        assert data["identity_type"] == "human"

    def test_returns_401_without_token(self):
        app = _make_app(auth_port=_make_auth_port())
        client = TestClient(app)

        resp = client.get("/auth/userinfo")
        assert resp.status_code == 401

    def test_correct_fields_for_service_identity(self):
        identity = Identity(
            user_id="svc-runtime",
            display_name="Runtime Service",
            roles=("service",),
            scopes=("openid",),
            identity_type="service",
        )
        app = _make_app(auth_port=_make_auth_port(identity))
        client = TestClient(app)

        resp = client.get("/auth/userinfo", headers={"Authorization": "Bearer svc-tok"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["identity_type"] == "service"
        assert data["user_id"] == "svc-runtime"

    def test_returns_request_id_header(self):
        app = _make_app(auth_port=_make_auth_port())
        client = TestClient(app)

        resp = client.get("/auth/userinfo", headers={"Authorization": "Bearer valid"})
        assert "x-request-id" in resp.headers
