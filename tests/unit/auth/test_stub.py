"""Tests for auth test stubs (SIP-0062 Phase 1)."""

from datetime import datetime, timedelta

import pytest

from squadops.auth.models import (
    AuthContext,
    Identity,
    IdentityType,
    Role,
    Scope,
    TokenClaims,
)
from tests._stubs.auth import TestStubAuthAdapter, TestStubAuthzAdapter


pytestmark = pytest.mark.auth


class TestStubAuthAdapterTests:
    """TestStubAuthAdapter tests."""

    @pytest.fixture
    def test_identity(self):
        return Identity(
            user_id="test-user",
            display_name="Test User",
            roles=(Role.ADMIN,),
            scopes=(Scope.CYCLES_READ,),
        )

    async def test_requires_explicit_identity(self, test_identity):
        """Stub requires explicit identity — no implicit admin."""
        adapter = TestStubAuthAdapter(default_identity=test_identity)
        claims = await adapter.validate_token("any-token")
        identity = await adapter.resolve_identity(claims)
        assert identity.user_id == "test-user"
        assert identity.display_name == "Test User"

    async def test_validate_token_returns_controllable_claims(self, test_identity):
        now = datetime.utcnow()
        custom_claims = TokenClaims(
            subject="custom-sub",
            issuer="custom-issuer",
            audience="custom-aud",
            expires_at=now + timedelta(hours=2),
            issued_at=now,
            roles=("viewer",),
        )
        adapter = TestStubAuthAdapter(
            default_identity=test_identity,
            default_claims=custom_claims,
        )
        claims = await adapter.validate_token("any-token")
        assert claims.subject == "custom-sub"
        assert claims.issuer == "custom-issuer"
        assert claims.roles == ("viewer",)

    async def test_validate_token_generates_claims_from_identity(self, test_identity):
        adapter = TestStubAuthAdapter(default_identity=test_identity)
        claims = await adapter.validate_token("any-token")
        assert claims.subject == "test-user"
        assert claims.roles == (Role.ADMIN,)
        assert claims.scopes == (Scope.CYCLES_READ,)

    async def test_close(self, test_identity):
        adapter = TestStubAuthAdapter(default_identity=test_identity)
        assert adapter.closed is False
        await adapter.close()
        assert adapter.closed is True


class TestStubAuthzAdapterTests:
    """TestStubAuthzAdapter tests."""

    @pytest.fixture
    def admin_identity(self):
        return Identity(
            user_id="admin-user",
            display_name="Admin",
            roles=(Role.ADMIN, Role.OPERATOR),
            scopes=(Scope.CYCLES_READ, Scope.CYCLES_WRITE, Scope.ADMIN_WRITE),
        )

    @pytest.fixture
    def viewer_identity(self):
        return Identity(
            user_id="viewer-user",
            display_name="Viewer",
            roles=(Role.VIEWER,),
            scopes=(Scope.CYCLES_READ,),
        )

    def test_grant_all(self, viewer_identity):
        adapter = TestStubAuthzAdapter(grant_all=True)
        ctx = adapter.check_access(viewer_identity, [Role.ADMIN], [])
        assert ctx.granted is True

    def test_role_check_passes(self, admin_identity):
        adapter = TestStubAuthzAdapter()
        ctx = adapter.check_access(admin_identity, [Role.ADMIN], [])
        assert ctx.granted is True
        assert ctx.identity == admin_identity

    def test_role_check_fails(self, viewer_identity):
        adapter = TestStubAuthzAdapter()
        ctx = adapter.check_access(viewer_identity, [Role.ADMIN], [])
        assert ctx.granted is False
        assert "Missing required role" in ctx.denial_reason

    def test_scope_check_passes(self, admin_identity):
        adapter = TestStubAuthzAdapter()
        ctx = adapter.check_access(admin_identity, [], [Scope.CYCLES_READ, Scope.CYCLES_WRITE])
        assert ctx.granted is True

    def test_scope_check_fails(self, viewer_identity):
        adapter = TestStubAuthzAdapter()
        ctx = adapter.check_access(viewer_identity, [], [Scope.CYCLES_READ, Scope.CYCLES_WRITE])
        assert ctx.granted is False
        assert "Missing required scopes" in ctx.denial_reason

    def test_no_requirements_grants(self, viewer_identity):
        adapter = TestStubAuthzAdapter()
        ctx = adapter.check_access(viewer_identity, [], [])
        assert ctx.granted is True
