"""Tests for auth domain models (SIP-0062 Phase 1)."""

from datetime import datetime, timedelta

import pytest

from squadops.auth.models import (
    AuthContext,
    Identity,
    IdentityResolutionError,
    IdentityType,
    TokenClaims,
    TokenValidationError,
)

pytestmark = pytest.mark.auth


class TestTokenClaims:
    """TokenClaims frozen dataclass tests."""

    def test_construction(self):
        now = datetime.utcnow()
        claims = TokenClaims(
            subject="user-1",
            issuer="http://keycloak/realms/squadops",
            audience="squadops-runtime",
            expires_at=now + timedelta(hours=1),
            issued_at=now,
            roles=("admin",),
            scopes=("cycles:read",),
            raw_claims={"sub": "user-1"},
        )
        assert claims.subject == "user-1"
        assert claims.issuer == "http://keycloak/realms/squadops"
        assert claims.audience == "squadops-runtime"
        assert claims.roles == ("admin",)
        assert claims.scopes == ("cycles:read",)
        assert claims.raw_claims == {"sub": "user-1"}

    def test_frozen_immutability(self):
        now = datetime.utcnow()
        claims = TokenClaims(
            subject="user-1",
            issuer="test",
            audience="test",
            expires_at=now + timedelta(hours=1),
            issued_at=now,
        )
        with pytest.raises(AttributeError):
            claims.subject = "user-2"  # type: ignore[misc]

    def test_audience_single_string(self):
        now = datetime.utcnow()
        claims = TokenClaims(
            subject="u",
            issuer="i",
            audience="single-aud",
            expires_at=now,
            issued_at=now,
        )
        assert claims.audience == "single-aud"

    def test_audience_tuple(self):
        now = datetime.utcnow()
        claims = TokenClaims(
            subject="u",
            issuer="i",
            audience=("aud1", "aud2"),
            expires_at=now,
            issued_at=now,
        )
        assert claims.audience == ("aud1", "aud2")

    def test_default_roles_and_scopes(self):
        now = datetime.utcnow()
        claims = TokenClaims(
            subject="u",
            issuer="i",
            audience="a",
            expires_at=now,
            issued_at=now,
        )
        assert claims.roles == ()
        assert claims.scopes == ()
        assert claims.raw_claims == {}


class TestIdentity:
    """Identity frozen dataclass tests."""

    def test_construction(self):
        identity = Identity(
            user_id="user-1",
            display_name="Alice",
            roles=("admin", "operator"),
            scopes=("cycles:read", "cycles:write"),
            identity_type=IdentityType.HUMAN,
        )
        assert identity.user_id == "user-1"
        assert identity.display_name == "Alice"
        assert identity.roles == ("admin", "operator")
        assert identity.identity_type == "human"

    def test_frozen_immutability(self):
        identity = Identity(user_id="u", display_name="n")
        with pytest.raises(AttributeError):
            identity.user_id = "other"  # type: ignore[misc]

    def test_default_identity_type(self):
        identity = Identity(user_id="u", display_name="n")
        assert identity.identity_type == IdentityType.HUMAN


class TestAuthContext:
    """AuthContext frozen dataclass tests."""

    def test_granted(self):
        identity = Identity(user_id="u", display_name="n")
        ctx = AuthContext(granted=True, identity=identity)
        assert ctx.granted is True
        assert ctx.identity == identity
        assert ctx.denial_reason is None

    def test_frozen_immutability(self):
        ctx = AuthContext(granted=True)
        with pytest.raises(AttributeError):
            ctx.granted = False  # type: ignore[misc]


class TestExceptions:
    """Auth exception hierarchy."""

    def test_token_validation_error(self):
        err = TokenValidationError("bad token")
        assert str(err) == "bad token"
        assert isinstance(err, Exception)

    def test_identity_resolution_error(self):
        err = IdentityResolutionError("no such user")
        assert str(err) == "no such user"
        assert isinstance(err, Exception)
