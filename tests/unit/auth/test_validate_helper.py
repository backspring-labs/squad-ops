"""Tests for validate_and_resolve_identity() shared helper (SIP-0062 Phase 3a)."""

import pytest
from unittest.mock import AsyncMock

from squadops.auth.models import Identity, IdentityResolutionError, TokenClaims, TokenValidationError
from squadops.api.middleware.auth import validate_and_resolve_identity


@pytest.fixture
def mock_auth_port():
    return AsyncMock()


@pytest.fixture
def sample_claims():
    from datetime import datetime, timezone

    return TokenClaims(
        subject="user-1",
        issuer="http://keycloak/realms/test",
        audience="test-client",
        expires_at=datetime.now(timezone.utc),
        issued_at=datetime.now(timezone.utc),
        roles=("admin",),
        scopes=("openid",),
    )


@pytest.fixture
def sample_identity():
    return Identity(
        user_id="user-1",
        display_name="Test User",
        roles=("admin",),
        scopes=("openid",),
        identity_type="human",
    )


@pytest.mark.auth
class TestValidateAndResolveIdentity:
    async def test_valid_token_returns_identity(self, mock_auth_port, sample_claims, sample_identity):
        mock_auth_port.validate_token.return_value = sample_claims
        mock_auth_port.resolve_identity.return_value = sample_identity

        result = await validate_and_resolve_identity("valid-token", mock_auth_port)

        assert result == sample_identity
        mock_auth_port.validate_token.assert_awaited_once_with("valid-token")
        mock_auth_port.resolve_identity.assert_awaited_once_with(sample_claims)

    async def test_invalid_token_raises(self, mock_auth_port):
        mock_auth_port.validate_token.side_effect = TokenValidationError("expired")

        with pytest.raises(TokenValidationError):
            await validate_and_resolve_identity("bad-token", mock_auth_port)

    async def test_identity_resolution_error_raises(self, mock_auth_port, sample_claims):
        mock_auth_port.validate_token.return_value = sample_claims
        mock_auth_port.resolve_identity.side_effect = IdentityResolutionError("no mapping")

        with pytest.raises(IdentityResolutionError):
            await validate_and_resolve_identity("token", mock_auth_port)

    async def test_shared_by_middleware_and_dependency(self):
        """validate_and_resolve_identity is importable from auth middleware module."""
        from squadops.api.middleware.auth import validate_and_resolve_identity as fn

        assert callable(fn)
