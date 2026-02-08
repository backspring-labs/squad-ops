"""
Auth domain models for SquadOps (SIP-0062).

Identity, TokenClaims, AuthContext, Role, Scope, and auth exceptions.
"""

from squadops.auth.models import (
    AuthContext,
    Identity,
    IdentityResolutionError,
    IdentityType,
    Role,
    Scope,
    TokenClaims,
    TokenValidationError,
)

__all__ = [
    "AuthContext",
    "Identity",
    "IdentityResolutionError",
    "IdentityType",
    "Role",
    "Scope",
    "TokenClaims",
    "TokenValidationError",
]
