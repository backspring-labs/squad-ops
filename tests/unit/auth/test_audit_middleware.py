"""Tests for audit event emission in AuthMiddleware (SIP-0062 Phase 3b)."""

import pytest
from unittest.mock import AsyncMock, MagicMock, call

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


def _make_audit_port():
    port = MagicMock()
    port.record = MagicMock()
    return port


def _build_app(auth_port=None, audit_port=None, provider="keycloak"):
    app = FastAPI()

    @app.get("/protected")
    async def protected():
        return {"ok": True}

    app.add_middleware(
        AuthMiddleware,
        auth_port=auth_port,
        provider=provider,
        audit_port=audit_port,
    )
    app.add_middleware(RequestIDMiddleware)
    return app


@pytest.mark.auth
class TestAuditMiddleware:
    def test_success_emits_token_validated(self):
        auth_port = _make_auth_port()
        audit_port = _make_audit_port()
        app = _build_app(auth_port=auth_port, audit_port=audit_port)
        client = TestClient(app)

        resp = client.get("/protected", headers={"Authorization": "Bearer valid"})
        assert resp.status_code == 200

        audit_port.record.assert_called_once()
        event = audit_port.record.call_args[0][0]
        assert event.action == "auth.token_validated"
        assert event.actor_id == "u1"
        assert event.actor_type == "human"
        assert event.result == "success"

    def test_failure_emits_token_rejected(self):
        auth_port = _make_auth_port(fail=True)
        audit_port = _make_audit_port()
        app = _build_app(auth_port=auth_port, audit_port=audit_port)
        client = TestClient(app)

        resp = client.get("/protected", headers={"Authorization": "Bearer bad"})
        assert resp.status_code == 401

        audit_port.record.assert_called_once()
        event = audit_port.record.call_args[0][0]
        assert event.action == "auth.token_rejected"
        assert event.result == "denied"

    def test_events_include_request_id(self):
        auth_port = _make_auth_port()
        audit_port = _make_audit_port()
        app = _build_app(auth_port=auth_port, audit_port=audit_port)
        client = TestClient(app)

        resp = client.get(
            "/protected",
            headers={"Authorization": "Bearer valid", "X-Request-ID": "req-abc"},
        )
        assert resp.status_code == 200

        event = audit_port.record.call_args[0][0]
        assert event.request_id == "req-abc"

    def test_events_include_ip(self):
        auth_port = _make_auth_port()
        audit_port = _make_audit_port()
        app = _build_app(auth_port=auth_port, audit_port=audit_port)
        client = TestClient(app)

        resp = client.get("/protected", headers={"Authorization": "Bearer valid"})
        assert resp.status_code == 200

        event = audit_port.record.call_args[0][0]
        # TestClient uses testclient IP
        assert event.ip_address is not None

    def test_works_without_audit_port(self):
        """Middleware works normally when audit_port=None."""
        auth_port = _make_auth_port()
        app = _build_app(auth_port=auth_port, audit_port=None)
        client = TestClient(app)

        resp = client.get("/protected", headers={"Authorization": "Bearer valid"})
        assert resp.status_code == 200

    def test_exactly_one_audit_event_per_request(self):
        """No double-emit: exactly one audit event per request."""
        auth_port = _make_auth_port()
        audit_port = _make_audit_port()
        app = _build_app(auth_port=auth_port, audit_port=audit_port)
        client = TestClient(app)

        client.get("/protected", headers={"Authorization": "Bearer valid"})
        assert audit_port.record.call_count == 1

    def test_missing_bearer_emits_rejected(self):
        auth_port = _make_auth_port()
        audit_port = _make_audit_port()
        app = _build_app(auth_port=auth_port, audit_port=audit_port)
        client = TestClient(app)

        resp = client.get("/protected")
        assert resp.status_code == 401

        event = audit_port.record.call_args[0][0]
        assert event.action == "auth.token_rejected"
        assert event.denial_reason == "missing_bearer_token"

    def test_disabled_provider_emits_rejected(self):
        audit_port = _make_audit_port()
        app = _build_app(audit_port=audit_port, provider="disabled")
        client = TestClient(app)

        resp = client.get("/protected")
        assert resp.status_code == 503

        event = audit_port.record.call_args[0][0]
        assert event.action == "auth.token_rejected"
        assert event.denial_reason == "provider_disabled"
