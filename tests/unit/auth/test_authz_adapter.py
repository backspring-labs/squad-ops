"""Tests for KeycloakAuthzAdapter (SIP-0062 Phase 2)."""

import pytest

from adapters.auth.keycloak.authz_adapter import KeycloakAuthzAdapter
from squadops.auth.models import Identity, Role, Scope


pytestmark = pytest.mark.auth


@pytest.fixture
def admin_identity():
    return Identity(
        user_id="admin-1",
        display_name="Admin User",
        roles=(Role.ADMIN, Role.OPERATOR),
        scopes=(Scope.CYCLES_READ, Scope.CYCLES_WRITE, Scope.ADMIN_WRITE),
    )


@pytest.fixture
def viewer_identity():
    return Identity(
        user_id="viewer-1",
        display_name="Viewer User",
        roles=(Role.VIEWER,),
        scopes=(Scope.CYCLES_READ,),
    )


class TestCheckAccess:
    """Authorization evaluation."""

    def test_role_match_grants(self, admin_identity):
        adapter = KeycloakAuthzAdapter()
        ctx = adapter.check_access(admin_identity, [Role.ADMIN], [])
        assert ctx.granted is True
        assert ctx.identity == admin_identity

    def test_any_role_match_grants(self, admin_identity):
        adapter = KeycloakAuthzAdapter()
        ctx = adapter.check_access(admin_identity, [Role.VIEWER, Role.ADMIN], [])
        assert ctx.granted is True

    def test_missing_role_denies(self, viewer_identity):
        adapter = KeycloakAuthzAdapter()
        ctx = adapter.check_access(viewer_identity, [Role.ADMIN], [])
        assert ctx.granted is False
        assert "Missing required role" in ctx.denial_reason

    def test_scope_match_grants(self, admin_identity):
        adapter = KeycloakAuthzAdapter()
        ctx = adapter.check_access(admin_identity, [], [Scope.CYCLES_READ, Scope.CYCLES_WRITE])
        assert ctx.granted is True

    def test_missing_scope_denies(self, viewer_identity):
        adapter = KeycloakAuthzAdapter()
        ctx = adapter.check_access(viewer_identity, [], [Scope.CYCLES_READ, Scope.CYCLES_WRITE])
        assert ctx.granted is False
        assert "Missing required scopes" in ctx.denial_reason

    def test_no_requirements_grants(self, viewer_identity):
        adapter = KeycloakAuthzAdapter()
        ctx = adapter.check_access(viewer_identity, [], [])
        assert ctx.granted is True

    def test_role_and_scope_combined(self, admin_identity):
        adapter = KeycloakAuthzAdapter()
        ctx = adapter.check_access(admin_identity, [Role.ADMIN], [Scope.ADMIN_WRITE])
        assert ctx.granted is True
