"""Tests for middleware ordering invariants (SIP-0062 Phase 3a)."""

import pytest
from unittest.mock import AsyncMock

from fastapi import FastAPI
from fastapi.testclient import TestClient

from squadops.api.middleware.auth import AuthMiddleware, RequestIDMiddleware
from squadops.auth.models import Identity, TokenClaims, TokenValidationError


def _make_auth_port(*, fail=False):
    from datetime import datetime, timezone

    port = AsyncMock()
    if fail:
        port.validate_token.side_effect = TokenValidationError("bad token")
    else:
        port.validate_token.return_value = TokenClaims(
            subject="u1",
            issuer="http://keycloak/realms/test",
            audience="test",
            expires_at=datetime.now(timezone.utc),
            issued_at=datetime.now(timezone.utc),
        )
        port.resolve_identity.return_value = Identity(
            user_id="u1",
            display_name="User",
            roles=("admin",),
            scopes=(),
            identity_type="human",
        )
    return port


def _build_app(auth_port=None, provider="keycloak"):
    app = FastAPI()

    @app.get("/protected")
    async def protected():
        return {"ok": True}

    app.add_middleware(
        AuthMiddleware,
        auth_port=auth_port,
        provider=provider,
    )
    app.add_middleware(RequestIDMiddleware)
    return app


@pytest.mark.auth
class TestMiddlewareInvariants:
    def test_request_id_present_on_401(self):
        """X-Request-ID MUST be present on 401 responses."""
        app = _build_app(auth_port=_make_auth_port(fail=True))
        client = TestClient(app)

        resp = client.get("/protected", headers={"Authorization": "Bearer bad"})
        assert resp.status_code == 401
        assert "x-request-id" in resp.headers

    def test_request_id_present_on_503(self):
        """X-Request-ID MUST be present on 503 responses."""
        app = _build_app(provider="disabled")
        client = TestClient(app)

        resp = client.get("/protected")
        assert resp.status_code == 503
        assert "x-request-id" in resp.headers

    def test_request_id_present_on_missing_bearer(self):
        """X-Request-ID MUST be present on 401 for missing bearer."""
        app = _build_app(auth_port=_make_auth_port())
        client = TestClient(app)

        resp = client.get("/protected")
        assert resp.status_code == 401
        assert "x-request-id" in resp.headers

    def test_options_preflight_never_triggers_auth(self):
        """OPTIONS preflight must return 200/204, not 401/403."""
        app = _build_app(auth_port=_make_auth_port())
        client = TestClient(app)

        resp = client.options("/protected")
        # OPTIONS without CORS middleware returns 405 (Method Not Allowed) from the
        # route itself, but the key assertion is that auth does NOT block it.
        # The auth middleware skips OPTIONS, so it passes through.
        assert resp.status_code != 401
        assert resp.status_code != 403

    def test_request_id_on_success(self):
        """X-Request-ID present on successful responses too."""
        app = _build_app(auth_port=_make_auth_port())
        client = TestClient(app)

        resp = client.get("/protected", headers={"Authorization": "Bearer valid"})
        assert resp.status_code == 200
        assert "x-request-id" in resp.headers

    def test_custom_request_id_preserved(self):
        """Client-provided X-Request-ID is preserved."""
        app = _build_app(auth_port=_make_auth_port())
        client = TestClient(app)

        resp = client.get(
            "/protected",
            headers={"Authorization": "Bearer valid", "X-Request-ID": "my-req-123"},
        )
        assert resp.status_code == 200
        assert resp.headers["x-request-id"] == "my-req-123"

    def test_auth_port_none_returns_503(self):
        """When auth port is None, returns 503 with request ID."""
        app = _build_app(auth_port=None, provider="keycloak")
        client = TestClient(app)

        # Patch deps to return None
        from unittest.mock import patch

        with patch("squadops.api.runtime.deps.get_auth_port", return_value=None):
            resp = client.get("/protected", headers={"Authorization": "Bearer token"})
            assert resp.status_code == 503
            assert "x-request-id" in resp.headers
