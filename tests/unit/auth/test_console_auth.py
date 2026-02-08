"""Tests for console route auth (SIP-0062 Phase 3a)."""

import pytest
from unittest.mock import AsyncMock

from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from squadops.api.routes import console as console_routes
from squadops.api.middleware.auth import require_auth
from squadops.auth.models import Identity, TokenClaims


def _make_auth_port(identity=None):
    from datetime import datetime, timezone

    port = AsyncMock()
    port.validate_token.return_value = TokenClaims(
        subject="u1",
        issuer="http://keycloak/realms/test",
        audience="test",
        expires_at=datetime.now(timezone.utc),
        issued_at=datetime.now(timezone.utc),
    )
    port.resolve_identity.return_value = identity or Identity(
        user_id="u1",
        display_name="User One",
        roles=("admin",),
        scopes=("openid",),
        identity_type="human",
    )
    return port


class _StubHealthChecker:
    async def get_agent_status(self):
        return []


class _StubCommandHandler:
    def __init__(self, hc):
        pass

    async def handle_help(self):
        return ["help"]


def _build_app(auth_dep=None):
    """Build a minimal app with console routes."""
    app = FastAPI()
    # Reset module-level state
    console_routes._health_checker = None
    console_routes._console_sessions = {}
    console_routes._parse_command = None
    console_routes._create_console_session = None
    console_routes._get_console_session = None
    console_routes._CommandHandler = None
    console_routes._auth_dependency = None

    app.include_router(console_routes.router)

    hc = _StubHealthChecker()
    sessions = {}

    console_routes.init_routes(
        health_checker=hc,
        console_sessions=sessions,
        parse_command=lambda cmd: {"command": cmd.strip().lower(), "args": []},
        create_console_session=lambda: "sess-1",
        get_console_session=lambda sid: sessions.get(sid),
        command_handler_cls=_StubCommandHandler,
        auth_dependency=auth_dep,
    )
    return app


@pytest.mark.auth
class TestConsoleAuth:
    def test_requires_bearer_when_auth_enabled(self):
        """Console routes require Bearer token when auth_dependency is set."""
        mock_port = _make_auth_port()
        dep = require_auth(lambda: mock_port)
        app = _build_app(auth_dep=dep)
        client = TestClient(app, raise_server_exceptions=False)

        resp = client.post(
            "/console/command",
            json={"session_id": "s1", "command": "help"},
        )
        assert resp.status_code == 401

    def test_401_without_token(self):
        mock_port = _make_auth_port()
        dep = require_auth(lambda: mock_port)
        app = _build_app(auth_dep=dep)
        client = TestClient(app, raise_server_exceptions=False)

        resp = client.get("/console/session")
        assert resp.status_code == 401

    def test_503_when_provider_disabled(self):
        """When provider=disabled, console routes return 503."""

        async def _disabled_dep(request):
            raise HTTPException(503, "Authentication service unavailable")

        app = _build_app(auth_dep=_disabled_dep)
        client = TestClient(app, raise_server_exceptions=False)

        resp = client.post(
            "/console/command",
            json={"session_id": "s1", "command": "help"},
        )
        assert resp.status_code == 503

    def test_routes_open_when_no_auth(self):
        """When auth_dependency is None, console routes are open."""
        app = _build_app(auth_dep=None)
        client = TestClient(app, raise_server_exceptions=False)

        # Session creation should work without auth
        resp = client.get("/console/session")
        # It will fail because create_console_session returns "sess-1" but
        # that's functional, not auth. The key assertion is it's not 401/503.
        assert resp.status_code == 200

    def test_session_endpoint_requires_auth(self):
        mock_port = _make_auth_port()
        dep = require_auth(lambda: mock_port)
        app = _build_app(auth_dep=dep)
        client = TestClient(app, raise_server_exceptions=False)

        resp = client.get("/console/session")
        assert resp.status_code == 401

    def test_responses_endpoint_requires_auth(self):
        mock_port = _make_auth_port()
        dep = require_auth(lambda: mock_port)
        app = _build_app(auth_dep=dep)
        client = TestClient(app, raise_server_exceptions=False)

        resp = client.get("/console/responses/sess-1")
        assert resp.status_code == 401
