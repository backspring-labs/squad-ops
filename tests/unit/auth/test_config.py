"""Tests for AuthConfig validation (SIP-0062 Phase 1)."""

import pytest

from squadops.config.schema import AuthConfig

pytestmark = pytest.mark.auth


class TestAuthConfig:
    """AuthConfig Pydantic model validation."""

    def test_invalid_roles_mode_client_without_client_id(self):
        with pytest.raises(ValueError, match="roles_client_id is required"):
            AuthConfig(
                enabled=True,
                provider="disabled",
                roles_mode="client",
            )

    def test_unknown_provider(self):
        with pytest.raises(ValueError, match="Unknown auth provider"):
            AuthConfig(
                enabled=True,
                provider="unknown-provider",
            )

    def test_enabled_keycloak_without_oidc_fails(self):
        with pytest.raises(ValueError, match="oidc configuration is required"):
            AuthConfig(
                enabled=True,
                provider="keycloak",
                oidc=None,
            )

    def test_service_clients_default_empty(self):
        cfg = AuthConfig(enabled=False)
        assert cfg.service_clients == {}
