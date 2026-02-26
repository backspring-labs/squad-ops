"""Tests for AuthConfig validation (SIP-0062 Phase 1)."""

import pytest

from squadops.config.schema import AuthConfig, OIDCConfig

pytestmark = pytest.mark.auth


class TestAuthConfig:
    """AuthConfig Pydantic model validation."""

    def test_valid_keycloak_config(self):
        cfg = AuthConfig(
            enabled=True,
            provider="keycloak",
            oidc=OIDCConfig(
                issuer_url="http://keycloak:8080/realms/squadops",
                audience="squadops-runtime",
            ),
        )
        assert cfg.enabled is True
        assert cfg.provider == "keycloak"
        assert cfg.oidc.issuer_url == "http://keycloak:8080/realms/squadops"

    def test_disabled_provider(self):
        cfg = AuthConfig(enabled=True, provider="disabled")
        assert cfg.provider == "disabled"
        assert cfg.oidc is None  # oidc not required when disabled

    def test_auth_disabled(self):
        cfg = AuthConfig(enabled=False)
        assert cfg.enabled is False

    def test_invalid_roles_mode_client_without_client_id(self):
        with pytest.raises(ValueError, match="roles_client_id is required"):
            AuthConfig(
                enabled=True,
                provider="disabled",
                roles_mode="client",
            )

    def test_valid_roles_mode_client_with_client_id(self):
        cfg = AuthConfig(
            enabled=True,
            provider="disabled",
            roles_mode="client",
            roles_client_id="my-client",
        )
        assert cfg.roles_mode == "client"
        assert cfg.roles_client_id == "my-client"

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

    def test_expose_docs_default_false(self):
        cfg = AuthConfig(enabled=False)
        assert cfg.expose_docs is False

    def test_expose_docs_true(self):
        cfg = AuthConfig(enabled=False, expose_docs=True)
        assert cfg.expose_docs is True

    def test_console_optional(self):
        """Console config is optional (deferred to Phase 3a)."""
        cfg = AuthConfig(enabled=False)
        assert cfg.console is None

    def test_service_clients_default_empty(self):
        cfg = AuthConfig(enabled=False)
        assert cfg.service_clients == {}


class TestOIDCConfig:
    """OIDCConfig defaults and validation."""

    def test_defaults(self):
        cfg = OIDCConfig(
            issuer_url="http://kc:8080/realms/test",
            audience="test-aud",
        )
        assert cfg.jwks_url is None
        assert cfg.roles_claim_path == "realm_access.roles"
        assert cfg.jwks_cache_ttl_seconds == 3600
        assert cfg.jwks_forced_refresh_min_interval_seconds == 30
        assert cfg.clock_skew_seconds == 60

    def test_custom_values(self):
        cfg = OIDCConfig(
            issuer_url="http://kc:8080/realms/test",
            audience="test-aud",
            jwks_url="http://kc:8080/realms/test/certs",
            roles_claim_path="resource_access.client.roles",
            jwks_cache_ttl_seconds=1800,
            clock_skew_seconds=60,
        )
        assert cfg.jwks_url == "http://kc:8080/realms/test/certs"
        assert cfg.roles_claim_path == "resource_access.client.roles"
        assert cfg.jwks_cache_ttl_seconds == 1800
