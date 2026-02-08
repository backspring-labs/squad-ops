"""
Test-only auth stubs (SIP-0062).

These implement AuthPort and AuthorizationPort for testing purposes.
NOT registered in the factory. NOT importable from production code.
"""

from __future__ import annotations

from squadops.auth.models import AuthContext, Identity, TokenClaims
from squadops.ports.auth.authentication import AuthPort
from squadops.ports.auth.authorization import AuthorizationPort


class TestStubAuthAdapter(AuthPort):
    """Test stub for AuthPort.

    Requires explicit default_identity in constructor — no implicit admin.
    """

    def __init__(
        self,
        default_identity: Identity,
        default_claims: TokenClaims | None = None,
    ) -> None:
        self._default_identity = default_identity
        self._default_claims = default_claims
        self._closed = False

    async def validate_token(self, token: str) -> TokenClaims:
        if self._default_claims is not None:
            return self._default_claims
        from datetime import datetime, timedelta

        return TokenClaims(
            subject=self._default_identity.user_id,
            issuer="test-issuer",
            audience="test-audience",
            expires_at=datetime.utcnow() + timedelta(hours=1),
            issued_at=datetime.utcnow(),
            roles=self._default_identity.roles,
            scopes=self._default_identity.scopes,
            raw_claims={"sub": self._default_identity.user_id},
        )

    async def resolve_identity(self, claims: TokenClaims) -> Identity:
        return self._default_identity

    async def close(self) -> None:
        self._closed = True

    @property
    def closed(self) -> bool:
        return self._closed


class TestStubAuthzAdapter(AuthorizationPort):
    """Test stub for AuthorizationPort.

    Requires explicit grant/deny configuration — no implicit allow-all.
    """

    def __init__(self, *, grant_all: bool = False, deny_reason: str = "Access denied") -> None:
        self._grant_all = grant_all
        self._deny_reason = deny_reason

    def check_access(
        self,
        identity: Identity,
        required_roles: list[str],
        required_scopes: list[str],
    ) -> AuthContext:
        if self._grant_all:
            return AuthContext(granted=True, identity=identity)

        # Check roles (any match)
        if required_roles:
            if not any(r in identity.roles for r in required_roles):
                return AuthContext(
                    granted=False,
                    identity=identity,
                    denial_reason=f"Missing required role: {required_roles}",
                )

        # Check scopes (all must be present)
        if required_scopes:
            missing = [s for s in required_scopes if s not in identity.scopes]
            if missing:
                return AuthContext(
                    granted=False,
                    identity=identity,
                    denial_reason=f"Missing required scopes: {missing}",
                )

        return AuthContext(granted=True, identity=identity)
