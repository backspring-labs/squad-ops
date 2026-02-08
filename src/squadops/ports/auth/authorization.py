"""
AuthorizationPort — abstract interface for role/scope enforcement (SIP-0062).
"""

from abc import ABC, abstractmethod

from squadops.auth.models import AuthContext, Identity


class AuthorizationPort(ABC):
    """Port for role/scope-based authorization checks."""

    @abstractmethod
    def check_access(
        self,
        identity: Identity,
        required_roles: list[str],
        required_scopes: list[str],
    ) -> AuthContext:
        """Evaluate whether an identity meets role/scope requirements.

        Args:
            identity: The resolved domain identity.
            required_roles: Roles the identity must hold (any match grants access). Pass [] to skip.
            required_scopes: Scopes the identity must hold (all must be present). Pass [] to skip.

        Returns:
            AuthContext with granted=True/False and optional denial_reason.
        """
