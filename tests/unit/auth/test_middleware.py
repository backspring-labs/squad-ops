"""Tests for JWT Auth Middleware (SIP-0062 Phase 2)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from squadops.api.middleware.auth import AuthMiddleware, RequestIDMiddleware
from squadops.auth.models import Identity, Role, Scope, TokenClaims


pytestmark = pytest.mark.auth


def _make_app(
    auth_port=None,
    provider: str = "keycloak",
    expose_docs: bool = False,
) -> FastAPI:
    """Build a minimal FastAPI app with auth middleware for testing."""
    app = FastAPI()

    # Add middleware in correct order (reverse of processing order)
    app.add_middleware(
        AuthMiddleware,
        auth_port=auth_port,
        provider=provider,
        expose_docs=expose_docs,
    )
    app.add_middleware(RequestIDMiddleware)

    @app.get("/health")
    async def health():
        return {"status": "ok"}

    @app.get("/health/infra")
    async def health_infra():
        return {"status": "ok"}

    @app.get("/docs")
    async def docs():
        return {"docs": "swagger"}

    @app.get("/openapi.json")
    async def openapi():
        return {"openapi": "3.0"}

    @app.get("/api/v1/tasks")
    async def tasks(request: Request):
        identity = getattr(request.state, "identity", None)
        if identity:
            return {"user": identity.user_id}
        return {"user": None}

    return app


def _make_auth_port(identity: Identity | None = None) -> MagicMock:
    """Create a mock AuthPort."""
    now = datetime.now(tz=timezone.utc)
    if identity is None:
        identity = Identity(
            user_id="test-user",
            display_name="Test User",
            roles=(Role.ADMIN,),
            scopes=(Scope.CYCLES_READ,),
        )

    claims = TokenClaims(
        subject=identity.user_id,
        issuer="http://keycloak:8080/realms/squadops",
        audience="squadops-runtime",
        expires_at=now + timedelta(hours=1),
        issued_at=now,
        roles=identity.roles,
        scopes=identity.scopes,
    )

    port = AsyncMock()
    port.validate_token = AsyncMock(return_value=claims)
    port.resolve_identity = AsyncMock(return_value=identity)
    return port


class TestHealthEndpointAllowlist:
    """/health and /health/infra always pass without token."""

    def test_health_no_token(self):
        app = _make_app()
        client = TestClient(app)
        resp = client.get("/health")
        assert resp.status_code == 200

    def test_health_infra_no_token(self):
        app = _make_app()
        client = TestClient(app)
        resp = client.get("/health/infra")
        assert resp.status_code == 200


class TestDocsAllowlist:
    """/docs allowed only when expose_docs=True."""

    def test_docs_allowed_when_expose_docs_true(self):
        auth_port = _make_auth_port()
        app = _make_app(auth_port=auth_port, expose_docs=True)
        client = TestClient(app)
        resp = client.get("/docs")
        assert resp.status_code == 200

    def test_docs_returns_401_when_expose_docs_false(self):
        auth_port = _make_auth_port()
        app = _make_app(auth_port=auth_port, expose_docs=False)
        client = TestClient(app)
        resp = client.get("/docs")
        assert resp.status_code == 401

    def test_openapi_json_allowed_when_expose_docs_true(self):
        auth_port = _make_auth_port()
        app = _make_app(auth_port=auth_port, expose_docs=True)
        client = TestClient(app)
        resp = client.get("/openapi.json")
        assert resp.status_code == 200

    def test_openapi_json_returns_401_when_expose_docs_false(self):
        auth_port = _make_auth_port()
        app = _make_app(auth_port=auth_port, expose_docs=False)
        client = TestClient(app)
        resp = client.get("/openapi.json")
        assert resp.status_code == 401


class TestMissingToken:
    """Missing or malformed Authorization header → 401."""

    def test_no_auth_header(self):
        auth_port = _make_auth_port()
        app = _make_app(auth_port=auth_port)
        client = TestClient(app)
        resp = client.get("/api/v1/tasks")
        assert resp.status_code == 401
        assert "Missing or invalid" in resp.json()["detail"]

    def test_wrong_auth_scheme(self):
        auth_port = _make_auth_port()
        app = _make_app(auth_port=auth_port)
        client = TestClient(app)
        resp = client.get("/api/v1/tasks", headers={"Authorization": "Basic abc123"})
        assert resp.status_code == 401


class TestInvalidToken:
    """Invalid token → 401."""

    def test_invalid_token(self):
        auth_port = AsyncMock()
        auth_port.validate_token = AsyncMock(side_effect=Exception("bad token"))
        app = _make_app(auth_port=auth_port)
        client = TestClient(app)
        resp = client.get("/api/v1/tasks", headers={"Authorization": "Bearer bad-token"})
        assert resp.status_code == 401
        assert "Invalid or expired" in resp.json()["detail"]


class TestValidToken:
    """Valid token → request.state.identity populated."""

    def test_valid_token_populates_identity(self):
        identity = Identity(
            user_id="alice",
            display_name="Alice",
            roles=(Role.ADMIN,),
        )
        auth_port = _make_auth_port(identity)
        app = _make_app(auth_port=auth_port)
        client = TestClient(app)
        resp = client.get("/api/v1/tasks", headers={"Authorization": "Bearer valid-token"})
        assert resp.status_code == 200
        assert resp.json()["user"] == "alice"


class TestDisabledProvider:
    """provider='disabled' → 503 for protected endpoints."""

    def test_disabled_returns_503(self):
        app = _make_app(provider="disabled")
        client = TestClient(app)
        resp = client.get("/api/v1/tasks")
        assert resp.status_code == 503
        assert "unavailable" in resp.json()["detail"].lower()

    def test_disabled_health_still_works(self):
        app = _make_app(provider="disabled")
        client = TestClient(app)
        resp = client.get("/health")
        assert resp.status_code == 200


class TestRequestID:
    """Auth failures include X-Request-ID."""

    def test_401_includes_request_id(self):
        auth_port = _make_auth_port()
        app = _make_app(auth_port=auth_port)
        client = TestClient(app)
        resp = client.get("/api/v1/tasks")
        assert "X-Request-ID" in resp.headers

    def test_503_includes_request_id(self):
        app = _make_app(provider="disabled")
        client = TestClient(app)
        resp = client.get("/api/v1/tasks")
        assert "X-Request-ID" in resp.headers

    def test_custom_request_id_preserved(self):
        auth_port = _make_auth_port()
        app = _make_app(auth_port=auth_port)
        client = TestClient(app)
        resp = client.get(
            "/api/v1/tasks",
            headers={
                "Authorization": "Bearer valid-token",
                "X-Request-ID": "custom-id-123",
            },
        )
        assert resp.headers["X-Request-ID"] == "custom-id-123"
