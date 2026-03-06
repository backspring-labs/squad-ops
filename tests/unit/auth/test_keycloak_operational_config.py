"""Tests for KeycloakOperationalConfig and related models (SIP-0063)."""

import pytest

from squadops.config.schema import (
    AuthConfig,
    KeycloakAdminConfig,
    KeycloakOperationalConfig,
    KeycloakSessionPolicyConfig,
    KeycloakTokenPolicyConfig,
    KeycloakTotpPolicyConfig,
    OIDCConfig,
)

pytestmark = pytest.mark.auth


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _dev_config(**overrides):
    """Build a valid dev KeycloakOperationalConfig with defaults."""
    defaults = {
        "realm": "squadops-dev",
        "base_url": "http://localhost:8180",
        "proxy_mode": "none",
        "hostname_strict": False,
        "admin": {"username": "admin", "password": "secret://kc_admin"},
    }
    defaults.update(overrides)
    return KeycloakOperationalConfig(**defaults)


def _local_config(**overrides):
    """Build a valid local (DGX Spark) KeycloakOperationalConfig."""
    defaults = {
        "realm": "squadops-local",
        "base_url": "http://squadops-keycloak:8080",
        "public_url": "https://auth.local.squadops.example",
        "db_dsn": "secret://keycloak_db_dsn",
        "proxy_mode": "edge",
        "external_tls_termination": True,
        "hostname_strict": True,
        "admin": {"username": "admin", "password": "secret://kc_admin"},
    }
    defaults.update(overrides)
    return KeycloakOperationalConfig(**defaults)


def _lab_config(**overrides):
    """Build a valid lab KeycloakOperationalConfig."""
    defaults = {
        "realm": "squadops-lab",
        "base_url": "http://squadops-keycloak:8080",
        "public_url": "https://auth.lab.squadops.example",
        "db_dsn": "secret://keycloak_db_dsn",
        "proxy_mode": "edge",
        "external_tls_termination": True,
        "hostname_strict": True,
        "admin": {"username": "admin", "password": "secret://kc_admin"},
    }
    defaults.update(overrides)
    return KeycloakOperationalConfig(**defaults)


def _cloud_config(**overrides):
    """Build a valid cloud KeycloakOperationalConfig."""
    defaults = {
        "realm": "squadops-cloud",
        "base_url": "http://squadops-keycloak:8080",
        "public_url": "https://auth.squadops.example",
        "db_dsn": "secret://keycloak_db_dsn",
        "proxy_mode": "edge",
        "external_tls_termination": True,
        "hostname_strict": True,
        "admin": {"username": "admin", "password": "secret://kc_admin"},
    }
    defaults.update(overrides)
    return KeycloakOperationalConfig(**defaults)


# ---------------------------------------------------------------------------
# Happy-path tests
# ---------------------------------------------------------------------------


class TestKeycloakOperationalConfigValid:
    """Valid configurations should pass validation."""

    def test_dev_config_all_defaults(self):
        cfg = _dev_config()
        assert cfg.realm == "squadops-dev"
        assert cfg.proxy_mode == "none"
        assert cfg.hostname_strict is False
        assert cfg.db_dsn is None

    def test_local_config_valid(self):
        cfg = _local_config()
        assert cfg.realm == "squadops-local"
        assert cfg.proxy_mode == "edge"
        assert cfg.external_tls_termination is True
        assert cfg.hostname_strict is True
        assert cfg.db_dsn == "secret://keycloak_db_dsn"

    def test_lab_config_valid(self):
        cfg = _lab_config()
        assert cfg.realm == "squadops-lab"
        assert cfg.proxy_mode == "edge"
        assert cfg.db_dsn == "secret://keycloak_db_dsn"

    def test_cloud_config_valid(self):
        cfg = _cloud_config()
        assert cfg.realm == "squadops-cloud"

    def test_default_token_policy(self):
        cfg = _dev_config()
        assert cfg.token_policy.access_token_minutes == 10
        assert cfg.token_policy.refresh_token_minutes == 1440
        assert cfg.token_policy.refresh_token_rotation is True

    def test_default_session_policy(self):
        cfg = _dev_config()
        assert cfg.session_policy.idle_minutes == 30
        assert cfg.session_policy.max_minutes == 480

    def test_default_security(self):
        cfg = _dev_config()
        assert cfg.security.mfa_required_for_admin is True
        assert cfg.security.brute_force_protection is True
        assert cfg.security.max_login_failures == 5

    def test_default_logging(self):
        cfg = _dev_config()
        assert cfg.logging.admin_events_enabled is True
        assert cfg.logging.login_events_enabled is True

    def test_admin_password_supports_secret_ref(self):
        cfg = _dev_config()
        assert cfg.admin.password == "secret://kc_admin"


# ---------------------------------------------------------------------------
# Staging/prod environment validators
# ---------------------------------------------------------------------------


class TestDeployedRealmValidation:
    """Non-dev (deployed) realms enforce stricter constraints."""

    def test_local_without_db_dsn_fails(self):
        with pytest.raises(ValueError, match="db_dsn required for deployed"):
            _local_config(db_dsn=None)

    def test_cloud_without_db_dsn_fails(self):
        with pytest.raises(ValueError, match="db_dsn required for deployed"):
            _cloud_config(db_dsn=None)

    def test_lab_without_db_dsn_fails(self):
        with pytest.raises(ValueError, match="db_dsn required for deployed"):
            _lab_config(db_dsn=None)

    def test_local_proxy_mode_none_fails(self):
        with pytest.raises(ValueError, match="proxy_mode must not be 'none'"):
            _local_config(
                proxy_mode="none",
                external_tls_termination=False,
            )

    def test_cloud_proxy_mode_none_fails(self):
        with pytest.raises(ValueError, match="proxy_mode must not be 'none'"):
            _cloud_config(
                proxy_mode="none",
                external_tls_termination=False,
            )

    def test_local_hostname_strict_false_fails(self):
        with pytest.raises(ValueError, match="hostname_strict must be true"):
            _local_config(hostname_strict=False)

    def test_local_public_url_http_fails(self):
        with pytest.raises(ValueError, match="public_url must use HTTPS"):
            _local_config(public_url="http://auth.local.squadops.example")

    def test_cloud_public_url_http_fails(self):
        with pytest.raises(ValueError, match="public_url must use HTTPS"):
            _cloud_config(public_url="http://auth.squadops.example")

    def test_local_base_url_localhost_fails(self):
        with pytest.raises(ValueError, match="base_url must not reference loopback"):
            _local_config(base_url="http://localhost:8180")

    def test_local_base_url_127_fails(self):
        with pytest.raises(ValueError, match="base_url must not reference loopback"):
            _local_config(base_url="http://127.0.0.1:8180")

    def test_local_base_url_ipv6_loopback_fails(self):
        with pytest.raises(ValueError, match="base_url must not reference loopback"):
            _local_config(base_url="http://[::1]:8180")


# ---------------------------------------------------------------------------
# Proxy + TLS mutual consistency
# ---------------------------------------------------------------------------


class TestProxyTlsConsistency:
    """Proxy mode and TLS termination must be mutually consistent."""

    def test_edge_without_tls_termination_fails(self):
        with pytest.raises(ValueError, match="external_tls_termination must be true"):
            _dev_config(
                proxy_mode="edge",
                external_tls_termination=False,
                public_url="https://example.com",
            )

    def test_none_with_tls_termination_fails(self):
        with pytest.raises(ValueError, match="external_tls_termination must be false"):
            _dev_config(
                proxy_mode="none",
                external_tls_termination=True,
                public_url="https://example.com",
            )

    def test_tls_termination_without_public_url_fails(self):
        with pytest.raises(ValueError, match="public_url required"):
            _dev_config(
                proxy_mode="edge",
                external_tls_termination=True,
                public_url=None,
            )

    def test_non_none_proxy_without_public_url_fails(self):
        with pytest.raises(ValueError, match="public_url required"):
            _dev_config(
                proxy_mode="reencrypt",
                public_url=None,
            )

    def test_passthrough_without_public_url_fails(self):
        with pytest.raises(ValueError, match="public_url required"):
            _dev_config(
                proxy_mode="passthrough",
                public_url=None,
            )


# ---------------------------------------------------------------------------
# CIDR validation
# ---------------------------------------------------------------------------


class TestAdminCidrValidation:
    """KeycloakAdminConfig.allowed_networks CIDR validation."""

    def test_valid_cidrs_pass(self):
        admin = KeycloakAdminConfig(
            password="secret://pw",
            allowed_networks=["10.0.0.0/8", "192.168.1.0/24"],
        )
        assert admin.allowed_networks == ["10.0.0.0/8", "192.168.1.0/24"]

    def test_invalid_cidr_fails(self):
        with pytest.raises(ValueError, match="Invalid CIDR"):
            KeycloakAdminConfig(
                password="secret://pw",
                allowed_networks=["not-a-cidr"],
            )

    def test_empty_allowed_networks_passes(self):
        admin = KeycloakAdminConfig(password="secret://pw")
        assert admin.allowed_networks == []


# ---------------------------------------------------------------------------
# Token / session / TOTP bounds
# ---------------------------------------------------------------------------


class TestPolicyBounds:
    """Pydantic ge/le constraints on policy fields."""

    def test_access_token_minutes_zero_fails(self):
        with pytest.raises(ValueError):
            KeycloakTokenPolicyConfig(access_token_minutes=0)

    def test_session_idle_zero_fails(self):
        with pytest.raises(ValueError):
            KeycloakSessionPolicyConfig(idle_minutes=0)

    def test_totp_digits_below_6_fails(self):
        with pytest.raises(ValueError):
            KeycloakTotpPolicyConfig(digits=5)

    def test_totp_digits_above_8_fails(self):
        with pytest.raises(ValueError):
            KeycloakTotpPolicyConfig(digits=9)

    def test_totp_period_below_20_fails(self):
        with pytest.raises(ValueError):
            KeycloakTotpPolicyConfig(period=10)

    def test_totp_period_above_60_fails(self):
        with pytest.raises(ValueError):
            KeycloakTotpPolicyConfig(period=90)


# ---------------------------------------------------------------------------
# AuthConfig integration
# ---------------------------------------------------------------------------


class TestAuthConfigKeycloak:
    """KeycloakOperationalConfig nested under AuthConfig."""

    def test_auth_config_with_keycloak_section(self):
        cfg = AuthConfig(
            enabled=True,
            provider="keycloak",
            oidc=OIDCConfig(
                issuer_url="http://kc:8080/realms/squadops-dev",
                audience="squadops-runtime",
            ),
            keycloak=KeycloakOperationalConfig(
                admin=KeycloakAdminConfig(password="secret://kc_admin"),
            ),
        )
        assert cfg.keycloak is not None
        assert cfg.keycloak.realm == "squadops-dev"


# ---------------------------------------------------------------------------
# Realm lint function tests
# ---------------------------------------------------------------------------


class TestRealmLintFunction:
    """Unit tests for the lint_realm function from lint_realm_exports.py."""

    @staticmethod
    def _lint(realm_dict, filename="test.json"):
        """Import and call lint_realm."""
        import importlib.util

        spec = importlib.util.spec_from_file_location(
            "lint_realm_exports",
            str(Path(__file__).resolve().parents[3] / "scripts" / "dev" / "lint_realm_exports.py"),
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod.lint_realm(realm_dict, filename)

    def _valid_local_realm(self) -> dict:
        """Return a minimal valid local (deployed) realm dict."""
        return {
            "realm": "squadops-local",
            "sslRequired": "external",
            "revokeRefreshToken": True,
            "refreshTokenMaxReuse": 0,
            "eventsEnabled": True,
            "adminEventsEnabled": True,
            "bruteForceProtected": True,
            "authenticationFlows": [{"alias": "squadops-browser-with-mfa"}],
            "clients": [
                {
                    "clientId": "squadops-console",
                    "redirectUris": ["https://console.local.example/*"],
                    "webOrigins": ["https://console.local.example"],
                }
            ],
        }

    def test_valid_local_passes(self):
        errors = self._lint(self._valid_local_realm())
        assert errors == []

    def test_valid_lab_passes(self):
        realm = self._valid_local_realm()
        realm["realm"] = "squadops-lab"
        errors = self._lint(realm)
        assert errors == []

    def test_missing_revoke_refresh_token(self):
        realm = self._valid_local_realm()
        realm["revokeRefreshToken"] = False
        errors = self._lint(realm)
        assert any("revokeRefreshToken" in e for e in errors)

    def test_refresh_token_max_reuse_nonzero(self):
        realm = self._valid_local_realm()
        realm["refreshTokenMaxReuse"] = 1
        errors = self._lint(realm)
        assert any("refreshTokenMaxReuse" in e for e in errors)

    def test_localhost_in_redirect_uri(self):
        realm = self._valid_local_realm()
        realm["clients"][0]["redirectUris"] = ["http://localhost:3000/*"]
        errors = self._lint(realm)
        assert any("localhost" in e for e in errors)

    def test_missing_mfa_flow(self):
        realm = self._valid_local_realm()
        realm["authenticationFlows"] = []
        errors = self._lint(realm)
        assert any("squadops-browser-with-mfa" in e for e in errors)

    def test_cloud_ssl_required_all(self):
        realm = self._valid_local_realm()
        realm["realm"] = "squadops-cloud"
        realm["sslRequired"] = "external"  # should be "all" for cloud
        errors = self._lint(realm)
        assert any("sslRequired" in e and "'all'" in e for e in errors)

    def test_events_disabled(self):
        realm = self._valid_local_realm()
        realm["eventsEnabled"] = False
        errors = self._lint(realm)
        assert any("eventsEnabled" in e for e in errors)

    def test_brute_force_disabled(self):
        realm = self._valid_local_realm()
        realm["bruteForceProtected"] = False
        errors = self._lint(realm)
        assert any("bruteForceProtected" in e for e in errors)


# Need Path for lint function import
from pathlib import Path  # noqa: E402
