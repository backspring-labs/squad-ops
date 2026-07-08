"""
Unit tests for agent status write routes (#326).

Handler behavior (ported from the old /health lane) plus the authorization
guard: routes are gated on agents:write, which the `agent` realm role implies
via the #270 role→scope bridge.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from starlette.middleware.base import BaseHTTPMiddleware

from adapters.auth.keycloak.authz_adapter import KeycloakAuthzAdapter
from squadops.api.routes.agent_status import router
from squadops.auth.models import Identity, Role, scopes_for_roles

pytestmark = pytest.mark.auth


@pytest.fixture()
def mock_health_checker():
    hc = MagicMock()
    hc.pg_pool = MagicMock()
    hc.update_agent_status_in_db = AsyncMock(return_value={"status": "updated", "agent_id": "max"})
    return hc


@pytest.fixture()
def client(mock_health_checker):
    """Test client with no authz backend configured — guards no-op (auth-off
    deployment behavior), so handler logic is exercised directly."""
    app = FastAPI()
    app.include_router(router)

    with patch(
        "squadops.api.routes.agent_status._get_health_checker",
        return_value=mock_health_checker,
    ):
        yield TestClient(app)


def _identity_for_roles(*roles: str) -> Identity:
    """Identity as the auth middleware would build it: effective scopes are
    the role-implied set (#270)."""
    return Identity(
        user_id=f"svc-{'-'.join(roles)}",
        display_name="test",
        roles=roles,
        scopes=tuple(sorted(scopes_for_roles(roles))),
    )


def _guarded_client(mock_health_checker, identity: Identity | None):
    """Test client with the REAL authz adapter wired and an optional identity
    injected (as AuthMiddleware would after token validation)."""
    app = FastAPI()

    class InjectIdentity(BaseHTTPMiddleware):
        async def dispatch(self, request: Request, call_next):
            if identity is not None:
                request.state.identity = identity
            return await call_next(request)

    app.add_middleware(InjectIdentity)
    app.include_router(router)
    return TestClient(app)


class TestCreateOrUpdateAgentStatus:
    def test_valid_heartbeat(self, client, mock_health_checker):
        resp = client.post(
            "/api/v1/agents/status",
            json={"agent_id": "max", "lifecycle_state": "READY"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "updated"
        mock_health_checker.update_agent_status_in_db.assert_awaited_once()

    def test_invalid_lifecycle_state_returns_400(self, client, mock_health_checker):
        resp = client.post(
            "/api/v1/agents/status",
            json={"agent_id": "max", "lifecycle_state": "INVALID"},
        )
        assert resp.status_code == 400
        assert "Invalid lifecycle_state" in resp.json()["detail"]
        mock_health_checker.update_agent_status_in_db.assert_not_awaited()


class TestUpdateAgentStatus:
    def test_update_with_no_fields_returns_400(self, client):
        resp = client.put("/api/v1/agents/status/max", json={})
        assert resp.status_code == 400
        assert "No fields" in resp.json()["detail"]

    def test_update_valid_fields(self, client, mock_health_checker):
        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock(return_value="UPDATE 1")
        mock_conn.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_conn.__aexit__ = AsyncMock(return_value=False)
        mock_health_checker.pg_pool.acquire.return_value = mock_conn

        resp = client.put(
            "/api/v1/agents/status/max",
            json={"lifecycle_state": "WORKING", "tps": 10},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "updated"

    def test_update_not_found(self, client, mock_health_checker):
        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock(return_value="UPDATE 0")
        mock_conn.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_conn.__aexit__ = AsyncMock(return_value=False)
        mock_health_checker.pg_pool.acquire.return_value = mock_conn

        resp = client.put(
            "/api/v1/agents/status/ghost",
            json={"lifecycle_state": "READY"},
        )
        assert resp.status_code == 404


class TestAgentsWriteGuard:
    """The routes enforce agents:write when an authz backend is configured.
    Uses the real KeycloakAuthzAdapter (pure logic) + the real role→scope
    bridge, so a ROLE_SCOPES regression (e.g. agent role losing agents:write)
    fails here, not in production."""

    HEARTBEAT = {"agent_id": "max", "lifecycle_state": "READY"}

    def _post(self, identity, mock_health_checker):
        client = _guarded_client(mock_health_checker, identity)
        with (
            patch(
                "squadops.api.routes.agent_status._get_health_checker",
                return_value=mock_health_checker,
            ),
            patch(
                "squadops.api.runtime.deps.get_authz_port",
                return_value=KeycloakAuthzAdapter(),
            ),
        ):
            return client.post("/api/v1/agents/status", json=self.HEARTBEAT)

    def test_anonymous_write_is_401(self, mock_health_checker):
        resp = self._post(None, mock_health_checker)
        assert resp.status_code == 401
        mock_health_checker.update_agent_status_in_db.assert_not_awaited()

    def test_viewer_role_is_403(self, mock_health_checker):
        resp = self._post(_identity_for_roles(Role.VIEWER), mock_health_checker)
        assert resp.status_code == 403
        assert "agents:write" in resp.json()["detail"]
        mock_health_checker.update_agent_status_in_db.assert_not_awaited()

    def test_operator_role_is_403(self, mock_health_checker):
        # Operator manages cycles/tasks but does NOT hold agents:write —
        # status writes are the agents' own lane (plus admin).
        resp = self._post(_identity_for_roles(Role.OPERATOR), mock_health_checker)
        assert resp.status_code == 403

    def test_agent_role_is_granted(self, mock_health_checker):
        resp = self._post(_identity_for_roles(Role.AGENT), mock_health_checker)
        assert resp.status_code == 200
        mock_health_checker.update_agent_status_in_db.assert_awaited_once()

    def test_admin_role_is_granted(self, mock_health_checker):
        resp = self._post(_identity_for_roles(Role.ADMIN), mock_health_checker)
        assert resp.status_code == 200

    def test_put_is_guarded_too(self, mock_health_checker):
        client = _guarded_client(mock_health_checker, None)
        with patch(
            "squadops.api.runtime.deps.get_authz_port",
            return_value=KeycloakAuthzAdapter(),
        ):
            resp = client.put("/api/v1/agents/status/max", json={"lifecycle_state": "WORKING"})
        assert resp.status_code == 401
