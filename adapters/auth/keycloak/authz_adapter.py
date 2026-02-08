"""
Keycloak AuthorizationPort adapter (SIP-0062).

Role/scope evaluation against Identity.
"""

from __future__ import annotations

from squadops.auth.models import AuthContext, Identity
from squadops.ports.auth.authorization import AuthorizationPort


class KeycloakAuthzAdapter(AuthorizationPort):
    """Role/scope-based authorization against Keycloak-sourced identities."""

    def __init__(
        self,
        roles_mode: str = "realm",
        roles_client_id: str | None = None,
    ) -> None:
        self._roles_mode = roles_mode
        self._roles_client_id = roles_client_id

    def check_access(
        self,
        identity: Identity,
        required_roles: list[str],
        required_scopes: list[str],
    ) -> AuthContext:
        """Evaluate identity against required roles and scopes."""
        # Check roles (any match grants access)
        if required_roles:
            if not any(r in identity.roles for r in required_roles):
                return AuthContext(
                    granted=False,
                    identity=identity,
                    denial_reason=f"Missing required role. Need one of: {required_roles}",
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
