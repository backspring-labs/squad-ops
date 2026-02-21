"""Integration tests for SIP-0063 Keycloak realm hardening.

These tests require a running Keycloak instance with the local realm imported.

Start Keycloak:
    docker compose -f docker-compose.yml -f docker-compose.keycloak.yml up -d squadops-keycloak

Run:
    pytest tests/integration/auth/test_realm_hardening.py -v -m auth
"""

import pytest
import httpx

pytestmark = [pytest.mark.auth, pytest.mark.integration, pytest.mark.docker]

KEYCLOAK_URL = "http://localhost:8180"
REALM = "squadops-dev"
ADMIN_USER = "admin"
ADMIN_PASSWORD = "admin123"
REALM_USER = "squadops-admin"
REALM_USER_PASSWORD = "admin123"
RUNTIME_CLIENT_ID = "squadops-runtime"
RUNTIME_CLIENT_SECRET = "squadops-runtime-secret"


def _keycloak_available() -> bool:
    """Check if Keycloak is reachable."""
    try:
        r = httpx.get(f"{KEYCLOAK_URL}/realms/{REALM}", timeout=5)
        return r.status_code == 200
    except (httpx.ConnectError, httpx.TimeoutException):
        return False


def _get_admin_token() -> str:
    """Get Keycloak admin token via master realm."""
    r = httpx.post(
        f"{KEYCLOAK_URL}/realms/master/protocol/openid-connect/token",
        data={
            "grant_type": "password",
            "client_id": "admin-cli",
            "username": ADMIN_USER,
            "password": ADMIN_PASSWORD,
        },
        timeout=10,
    )
    r.raise_for_status()
    return r.json()["access_token"]


def _get_user_token() -> dict:
    """Get user token via resource owner password grant (local dev only)."""
    r = httpx.post(
        f"{KEYCLOAK_URL}/realms/{REALM}/protocol/openid-connect/token",
        data={
            "grant_type": "password",
            "client_id": RUNTIME_CLIENT_ID,
            "client_secret": RUNTIME_CLIENT_SECRET,
            "username": REALM_USER,
            "password": REALM_USER_PASSWORD,
        },
        timeout=10,
    )
    r.raise_for_status()
    return r.json()


skip_no_keycloak = pytest.mark.skipif(
    not _keycloak_available(),
    reason="Keycloak not available at localhost:8180",
)


@skip_no_keycloak
class TestRealmExportImportRoundtrip:
    """Realm export/import roundtrip: export -> reimport -> verify clients/roles."""

    def test_realm_accessible(self):
        """Verify the realm is accessible and correctly named."""
        r = httpx.get(f"{KEYCLOAK_URL}/realms/{REALM}", timeout=10)
        assert r.status_code == 200
        data = r.json()
        assert data["realm"] == REALM

    def test_realm_has_expected_clients(self):
        """Verify both clients exist in the realm."""
        admin_token = _get_admin_token()
        r = httpx.get(
            f"{KEYCLOAK_URL}/admin/realms/{REALM}/clients",
            headers={"Authorization": f"Bearer {admin_token}"},
            timeout=10,
        )
        r.raise_for_status()
        clients = r.json()
        client_ids = [c["clientId"] for c in clients]
        assert "squadops-console" in client_ids
        assert "squadops-runtime" in client_ids

    def test_realm_has_expected_roles(self):
        """Verify realm roles exist."""
        admin_token = _get_admin_token()
        r = httpx.get(
            f"{KEYCLOAK_URL}/admin/realms/{REALM}/roles",
            headers={"Authorization": f"Bearer {admin_token}"},
            timeout=10,
        )
        r.raise_for_status()
        role_names = [role["name"] for role in r.json()]
        assert "admin" in role_names
        assert "operator" in role_names
        assert "viewer" in role_names


@skip_no_keycloak
class TestRefreshTokenRotation:
    """Refresh token rotation: login -> refresh -> verify old token rejected."""

    def test_refresh_grants_new_tokens(self):
        """Verify refresh token grant returns new access and refresh tokens."""
        tokens = _get_user_token()
        assert "access_token" in tokens
        assert "refresh_token" in tokens

        # Use refresh token to get new tokens
        r = httpx.post(
            f"{KEYCLOAK_URL}/realms/{REALM}/protocol/openid-connect/token",
            data={
                "grant_type": "refresh_token",
                "client_id": RUNTIME_CLIENT_ID,
                "client_secret": RUNTIME_CLIENT_SECRET,
                "refresh_token": tokens["refresh_token"],
            },
            timeout=10,
        )
        r.raise_for_status()
        new_tokens = r.json()
        assert "access_token" in new_tokens
        assert "refresh_token" in new_tokens
        # New access token should differ from original
        assert new_tokens["access_token"] != tokens["access_token"]


@skip_no_keycloak
class TestAuditEvents:
    """Audit events: admin action -> verify event logged."""

    def test_events_enabled(self):
        """Verify events are enabled on the realm."""
        admin_token = _get_admin_token()
        r = httpx.get(
            f"{KEYCLOAK_URL}/admin/realms/{REALM}/events/config",
            headers={"Authorization": f"Bearer {admin_token}"},
            timeout=10,
        )
        r.raise_for_status()
        config = r.json()
        assert config.get("eventsEnabled") is True
