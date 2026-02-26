"""Tests for require_auth() FastAPI dependency (SIP-0062 Phase 3a)."""

from datetime import UTC
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from squadops.api.middleware.auth import require_auth
from squadops.auth.models import Identity, TokenClaims, TokenValidationError


def _make_identity(**overrides):
    defaults = dict(
        user_id="user-1",
        display_name="Test User",
        roles=("admin",),
        scopes=("openid",),
        identity_type="human",
    )
    defaults.update(overrides)
    return Identity(**defaults)


def _make_claims():
    from datetime import datetime

    return TokenClaims(
        subject="user-1",
        issuer="http://keycloak/realms/test",
        audience="test-client",
        expires_at=datetime.now(UTC),
        issued_at=datetime.now(UTC),
    )


@pytest.mark.auth
class TestRequireAuth:
    def _build_app(self, auth_port_getter=None):
        app = FastAPI()
        dep = require_auth(auth_port_getter)

        @app.get("/protected")
        async def protected(identity=Depends(dep)):
            return {"user_id": identity.user_id}

        return app

    def test_valid_token_returns_identity(self):
        mock_port = AsyncMock()
        mock_port.validate_token.return_value = _make_claims()
        mock_port.resolve_identity.return_value = _make_identity()

        app = self._build_app(auth_port_getter=lambda: mock_port)
        client = TestClient(app)

        resp = client.get("/protected", headers={"Authorization": "Bearer valid-token"})
        assert resp.status_code == 200
        assert resp.json()["user_id"] == "user-1"

    def test_missing_header_returns_401(self):
        app = self._build_app(auth_port_getter=lambda: AsyncMock())
        client = TestClient(app)

        resp = client.get("/protected")
        assert resp.status_code == 401
        assert "Missing" in resp.json()["detail"]

    def test_non_bearer_header_returns_401(self):
        app = self._build_app(auth_port_getter=lambda: AsyncMock())
        client = TestClient(app)

        resp = client.get("/protected", headers={"Authorization": "Basic abc"})
        assert resp.status_code == 401

    def test_invalid_token_returns_401(self):
        mock_port = AsyncMock()
        mock_port.validate_token.side_effect = TokenValidationError("bad")

        app = self._build_app(auth_port_getter=lambda: mock_port)
        client = TestClient(app)

        resp = client.get("/protected", headers={"Authorization": "Bearer bad-token"})
        assert resp.status_code == 401
        assert "Invalid" in resp.json()["detail"]

    def test_auth_port_none_returns_503(self):
        app = self._build_app(auth_port_getter=lambda: None)
        client = TestClient(app)

        resp = client.get("/protected", headers={"Authorization": "Bearer some-token"})
        assert resp.status_code == 503
        assert "unavailable" in resp.json()["detail"].lower()

    def test_custom_auth_port_getter(self):
        """Custom getter is called instead of default deps."""
        called = []

        def getter():
            called.append(True)
            port = AsyncMock()
            port.validate_token.return_value = _make_claims()
            port.resolve_identity.return_value = _make_identity()
            return port

        app = self._build_app(auth_port_getter=getter)
        client = TestClient(app)

        resp = client.get("/protected", headers={"Authorization": "Bearer tok"})
        assert resp.status_code == 200
        assert len(called) == 1

    def test_default_getter_uses_runtime_deps(self):
        """When no getter provided, falls back to runtime deps."""
        mock_port = AsyncMock()
        mock_port.validate_token.return_value = _make_claims()
        mock_port.resolve_identity.return_value = _make_identity()

        app = self._build_app()  # No getter
        client = TestClient(app)

        with patch("squadops.api.runtime.deps.get_auth_port", return_value=mock_port):
            resp = client.get("/protected", headers={"Authorization": "Bearer tok"})
            assert resp.status_code == 200
