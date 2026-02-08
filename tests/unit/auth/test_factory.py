"""Tests for auth factory functions (SIP-0062 Phase 1)."""

from unittest.mock import patch

import pytest

from adapters.auth.factory import create_auth_provider, create_authorization_provider


pytestmark = pytest.mark.auth


class TestCreateAuthProvider:
    """Factory function for AuthPort."""

    def test_raises_for_disabled(self):
        with pytest.raises(ValueError, match="disabled"):
            create_auth_provider("disabled")

    def test_raises_for_unknown(self):
        with pytest.raises(ValueError, match="Unknown auth provider"):
            create_auth_provider("cognito")

    def test_keycloak_creates_adapter(self):
        """Factory returns KeycloakAuthAdapter for 'keycloak' (lazy import)."""
        # Keycloak adapter module must exist for the import to work.
        # If not yet implemented, the factory will ImportError — skip gracefully.
        try:
            result = create_auth_provider(
                "keycloak",
                issuer_url="http://kc:8080/realms/test",
                audience="test",
            )
            from squadops.ports.auth.authentication import AuthPort

            assert isinstance(result, AuthPort)
        except (ImportError, ModuleNotFoundError):
            pytest.skip("KeycloakAuthAdapter not yet implemented (Phase 2)")


class TestCreateAuthorizationProvider:
    """Factory function for AuthorizationPort."""

    def test_raises_for_disabled(self):
        with pytest.raises(ValueError, match="disabled"):
            create_authorization_provider("disabled")

    def test_raises_for_unknown(self):
        with pytest.raises(ValueError, match="Unknown auth provider"):
            create_authorization_provider("cognito")
