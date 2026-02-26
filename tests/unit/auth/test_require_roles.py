"""Tests for require_roles and require_scopes decorators (SIP-0062 Phase 2)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from squadops.api.middleware.auth import (
    AuthMiddleware,
    RequestIDMiddleware,
    require_roles,
    require_scopes,
)
from squadops.auth.models import Identity, Role, Scope, TokenClaims

pytestmark = pytest.mark.auth


def _make_auth_port(identity: Identity):
    """Create a mock AuthPort that returns the given identity."""
    now = datetime.now(tz=UTC)
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


def _make_app_with_roles(auth_port, authz_port):
    """Build app with role-protected endpoint."""
    app = FastAPI()

    app.add_middleware(
        AuthMiddleware,
        auth_port=auth_port,
        provider="keycloak",
        expose_docs=False,
    )
    app.add_middleware(RequestIDMiddleware)

    @app.get("/admin-only")
    async def admin_only(identity: Identity = Depends(require_roles(Role.ADMIN))):
        return {"user": identity.user_id, "roles": identity.roles}

    @app.get("/write-cycles")
    async def write_cycles(identity: Identity = Depends(require_scopes(Scope.CYCLES_WRITE))):
        return {"user": identity.user_id}

    return app


class TestRequireRoles:
    """require_roles() decorator tests."""

    def test_grants_access_for_matching_role(self):
        identity = Identity(
            user_id="admin-user",
            display_name="Admin",
            roles=(Role.ADMIN, Role.OPERATOR),
            scopes=(Scope.ADMIN_WRITE,),
        )
        auth_port = _make_auth_port(identity)

        from adapters.auth.keycloak.authz_adapter import KeycloakAuthzAdapter

        authz_port = KeycloakAuthzAdapter()

        app = _make_app_with_roles(auth_port, authz_port)

        with patch("squadops.api.runtime.deps.get_authz_port", return_value=authz_port):
            client = TestClient(app)
            resp = client.get(
                "/admin-only",
                headers={"Authorization": "Bearer valid-token"},
            )
            assert resp.status_code == 200
            assert resp.json()["user"] == "admin-user"

    def test_denies_with_403_for_missing_role(self):
        identity = Identity(
            user_id="viewer-user",
            display_name="Viewer",
            roles=(Role.VIEWER,),
            scopes=(Scope.CYCLES_READ,),
        )
        auth_port = _make_auth_port(identity)

        from adapters.auth.keycloak.authz_adapter import KeycloakAuthzAdapter

        authz_port = KeycloakAuthzAdapter()

        app = _make_app_with_roles(auth_port, authz_port)

        with patch("squadops.api.runtime.deps.get_authz_port", return_value=authz_port):
            client = TestClient(app)
            resp = client.get(
                "/admin-only",
                headers={"Authorization": "Bearer valid-token"},
            )
            assert resp.status_code == 403


class TestRequireScopes:
    """require_scopes() decorator tests."""

    def test_grants_access_for_matching_scopes(self):
        identity = Identity(
            user_id="writer",
            display_name="Writer",
            roles=(Role.OPERATOR,),
            scopes=(Scope.CYCLES_READ, Scope.CYCLES_WRITE),
        )
        auth_port = _make_auth_port(identity)

        from adapters.auth.keycloak.authz_adapter import KeycloakAuthzAdapter

        authz_port = KeycloakAuthzAdapter()

        app = _make_app_with_roles(auth_port, authz_port)

        with patch("squadops.api.runtime.deps.get_authz_port", return_value=authz_port):
            client = TestClient(app)
            resp = client.get(
                "/write-cycles",
                headers={"Authorization": "Bearer valid-token"},
            )
            assert resp.status_code == 200

    def test_denies_with_403_for_missing_scopes(self):
        identity = Identity(
            user_id="reader",
            display_name="Reader",
            roles=(Role.VIEWER,),
            scopes=(Scope.CYCLES_READ,),
        )
        auth_port = _make_auth_port(identity)

        from adapters.auth.keycloak.authz_adapter import KeycloakAuthzAdapter

        authz_port = KeycloakAuthzAdapter()

        app = _make_app_with_roles(auth_port, authz_port)

        with patch("squadops.api.runtime.deps.get_authz_port", return_value=authz_port):
            client = TestClient(app)
            resp = client.get(
                "/write-cycles",
                headers={"Authorization": "Bearer valid-token"},
            )
            assert resp.status_code == 403
