"""
AuthPort — abstract interface for token validation and identity resolution (SIP-0062).
"""

from abc import ABC, abstractmethod

from squadops.auth.models import Identity, TokenClaims


class AuthPort(ABC):
    """Port for OIDC token validation and identity resolution."""

    @abstractmethod
    async def validate_token(self, token: str) -> TokenClaims:
        """Validate a JWT token and return parsed claims.

        Raises:
            TokenValidationError: If the token is invalid, expired, or has a bad signature.
        """

    @abstractmethod
    async def resolve_identity(self, claims: TokenClaims) -> Identity:
        """Map validated token claims to a domain Identity.

        Raises:
            IdentityResolutionError: If claims cannot be mapped to an Identity.
        """

    @abstractmethod
    async def close(self) -> None:
        """Release resources (HTTP clients, caches, etc.)."""
