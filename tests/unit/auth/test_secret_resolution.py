"""Tests for factory secret resolution (SIP-0062 Phase 3b)."""

import pytest
from unittest.mock import MagicMock

from adapters.auth.factory import create_service_token_client


def _make_oidc_config(issuer_url="http://keycloak:8080/realms/test"):
    cfg = MagicMock()
    cfg.issuer_url = issuer_url
    return cfg


def _make_service_config(client_id="svc", client_secret="plain-secret"):
    cfg = MagicMock()
    cfg.client_id = client_id
    cfg.client_secret = client_secret
    return cfg


@pytest.mark.auth
class TestSecretResolution:
    def test_resolves_secret_ref(self):
        """create_service_token_client resolves secret:// via SecretManager."""
        sm = MagicMock()
        sm.resolve.return_value = "resolved-secret"

        svc_cfg = _make_service_config(client_secret="secret://my_svc_secret")
        oidc_cfg = _make_oidc_config()

        client = create_service_token_client("my-svc", svc_cfg, oidc_cfg, secret_manager=sm)

        sm.resolve.assert_called_once_with("secret://my_svc_secret")
        assert client._client_secret == "resolved-secret"

    def test_passes_through_literal_secret(self):
        """Literal (non-secret://) secrets pass through unchanged."""
        sm = MagicMock()
        svc_cfg = _make_service_config(client_secret="literal-password")
        oidc_cfg = _make_oidc_config()

        client = create_service_token_client("my-svc", svc_cfg, oidc_cfg, secret_manager=sm)

        sm.resolve.assert_not_called()
        assert client._client_secret == "literal-password"

    def test_no_secret_manager_passes_through(self):
        """Without SecretManager, secret:// refs pass through (no resolution)."""
        svc_cfg = _make_service_config(client_secret="secret://unresolved")
        oidc_cfg = _make_oidc_config()

        client = create_service_token_client("my-svc", svc_cfg, oidc_cfg, secret_manager=None)
        assert client._client_secret == "secret://unresolved"

    def test_token_endpoint_derived_from_issuer(self):
        """Token endpoint is derived from OIDC issuer_url."""
        svc_cfg = _make_service_config()
        oidc_cfg = _make_oidc_config(issuer_url="http://keycloak:8080/realms/squadops")

        client = create_service_token_client("my-svc", svc_cfg, oidc_cfg)

        assert client._token_endpoint == (
            "http://keycloak:8080/realms/squadops/protocol/openid-connect/token"
        )

    def test_secret_manager_resolve_error_propagates(self):
        """If SecretManager.resolve raises, it propagates."""
        sm = MagicMock()
        sm.resolve.side_effect = ValueError("Secret not found: my_secret")

        svc_cfg = _make_service_config(client_secret="secret://my_secret")
        oidc_cfg = _make_oidc_config()

        with pytest.raises(ValueError, match="Secret not found"):
            create_service_token_client("my-svc", svc_cfg, oidc_cfg, secret_manager=sm)
