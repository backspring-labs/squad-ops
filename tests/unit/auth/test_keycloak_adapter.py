"""Tests for KeycloakAuthAdapter (SIP-0062 Phase 2)."""

from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

import pytest

from adapters.auth.keycloak.auth_adapter import KeycloakAuthAdapter
from squadops.auth.models import IdentityType, TokenValidationError


pytestmark = pytest.mark.auth


# Helpers for building test tokens
def _make_claims(
    sub: str = "user-1",
    iss: str = "http://keycloak:8080/realms/squadops",
    aud: str = "squadops-runtime",
    exp_offset: int = 3600,
    iat_offset: int = 0,
    roles: list[str] | None = None,
    scope: str = "",
    preferred_username: str = "alice",
    **extra,
) -> dict:
    now = int(time.time())
    claims = {
        "sub": sub,
        "iss": iss,
        "aud": aud,
        "exp": now + exp_offset,
        "iat": now + iat_offset,
        "scope": scope,
        "preferred_username": preferred_username,
        "realm_access": {"roles": roles or ["viewer"]},
        **extra,
    }
    return claims


FAKE_JWKS = {"keys": [{"kty": "RSA", "kid": "test-key-1", "n": "fake", "e": "AQAB"}]}


class TestJWKSFetchAndCaching:
    """JWKS fetch and caching tests."""

    async def test_jwks_fetch(self):
        adapter = KeycloakAuthAdapter(
            issuer_url="http://keycloak:8080/realms/squadops",
            audience="squadops-runtime",
        )
        from unittest.mock import MagicMock

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = lambda: None
        mock_response.json.return_value = FAKE_JWKS

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.is_closed = False
        adapter._client = mock_client

        result = await adapter._fetch_jwks()
        assert result == FAKE_JWKS
        mock_client.get.assert_called_once()

    async def test_jwks_caching_skips_refetch(self):
        adapter = KeycloakAuthAdapter(
            issuer_url="http://keycloak:8080/realms/squadops",
            audience="squadops-runtime",
            jwks_cache_ttl_seconds=3600,
        )
        adapter._jwks = FAKE_JWKS
        adapter._jwks_fetched_at = time.monotonic()

        result = await adapter._fetch_jwks()
        assert result == FAKE_JWKS
        # No HTTP call should have been made
        assert adapter._client is None  # client never created

    async def test_jwks_cache_expired_refetches(self):
        adapter = KeycloakAuthAdapter(
            issuer_url="http://keycloak:8080/realms/squadops",
            audience="squadops-runtime",
            jwks_cache_ttl_seconds=1,
        )
        adapter._jwks = FAKE_JWKS
        adapter._jwks_fetched_at = time.monotonic() - 10  # expired

        from unittest.mock import MagicMock

        new_jwks = {"keys": [{"kty": "RSA", "kid": "new-key", "n": "fake2", "e": "AQAB"}]}
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = lambda: None
        mock_response.json.return_value = new_jwks

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.is_closed = False
        adapter._client = mock_client

        result = await adapter._fetch_jwks()
        assert result == new_jwks

    async def test_stampede_protection(self):
        adapter = KeycloakAuthAdapter(
            issuer_url="http://keycloak:8080/realms/squadops",
            audience="squadops-runtime",
            jwks_forced_refresh_min_interval_seconds=60,
        )
        adapter._jwks = FAKE_JWKS
        adapter._jwks_fetched_at = time.monotonic()
        adapter._last_forced_refresh = time.monotonic()  # Just refreshed

        # Force refresh should be blocked by stampede protection
        result = await adapter._fetch_jwks(force=True)
        assert result == FAKE_JWKS
        # No HTTP call — used cache
        assert adapter._client is None


class TestTokenValidation:
    """Token validation tests using mocked jwt.decode."""

    async def test_valid_token(self):
        adapter = KeycloakAuthAdapter(
            issuer_url="http://keycloak:8080/realms/squadops",
            audience="squadops-runtime",
        )
        adapter._jwks = FAKE_JWKS
        adapter._jwks_fetched_at = time.monotonic()

        claims = _make_claims(roles=["admin", "operator"])

        with patch("adapters.auth.keycloak.auth_adapter.jwt.decode", return_value=claims):
            tc = await adapter.validate_token("valid-token")

        assert tc.subject == "user-1"
        assert tc.issuer == "http://keycloak:8080/realms/squadops"
        assert tc.roles == ("admin", "operator")
        assert tc.audience == "squadops-runtime"

    async def test_expired_token(self):
        adapter = KeycloakAuthAdapter(
            issuer_url="http://keycloak:8080/realms/squadops",
            audience="squadops-runtime",
        )
        adapter._jwks = FAKE_JWKS
        adapter._jwks_fetched_at = time.monotonic()

        from jose.exceptions import ExpiredSignatureError

        with patch(
            "adapters.auth.keycloak.auth_adapter.jwt.decode",
            side_effect=ExpiredSignatureError("expired"),
        ):
            with pytest.raises(TokenValidationError, match="expired"):
                await adapter.validate_token("expired-token")

    async def test_wrong_issuer(self):
        adapter = KeycloakAuthAdapter(
            issuer_url="http://keycloak:8080/realms/squadops",
            audience="squadops-runtime",
        )
        adapter._jwks = FAKE_JWKS
        adapter._jwks_fetched_at = time.monotonic()

        from jose import JWTError

        with patch(
            "adapters.auth.keycloak.auth_adapter.jwt.decode",
            side_effect=JWTError("Invalid issuer"),
        ):
            with pytest.raises(TokenValidationError, match="Token validation failed"):
                await adapter.validate_token("wrong-issuer-token")

    async def test_wrong_audience(self):
        adapter = KeycloakAuthAdapter(
            issuer_url="http://keycloak:8080/realms/squadops",
            audience="squadops-runtime",
        )
        adapter._jwks = FAKE_JWKS
        adapter._jwks_fetched_at = time.monotonic()

        from jose import JWTError

        with patch(
            "adapters.auth.keycloak.auth_adapter.jwt.decode",
            side_effect=JWTError("Invalid audience"),
        ):
            with pytest.raises(TokenValidationError, match="Token validation failed"):
                await adapter.validate_token("wrong-audience-token")

    async def test_bad_signature_triggers_jwks_refresh(self):
        adapter = KeycloakAuthAdapter(
            issuer_url="http://keycloak:8080/realms/squadops",
            audience="squadops-runtime",
        )
        adapter._jwks = FAKE_JWKS
        adapter._jwks_fetched_at = time.monotonic()

        from jose import JWTError

        claims = _make_claims()

        call_count = 0

        def mock_decode(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise JWTError("Signature verification failed")
            return claims

        from unittest.mock import MagicMock as SyncMock

        mock_response = SyncMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = lambda: None
        mock_response.json.return_value = FAKE_JWKS

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.is_closed = False
        adapter._client = mock_client

        with patch("adapters.auth.keycloak.auth_adapter.jwt.decode", side_effect=mock_decode):
            tc = await adapter.validate_token("rotated-key-token")

        assert tc.subject == "user-1"
        assert call_count == 2  # First failed, then succeeded after refresh

    async def test_clock_skew_tolerance(self):
        adapter = KeycloakAuthAdapter(
            issuer_url="http://keycloak:8080/realms/squadops",
            audience="squadops-runtime",
            clock_skew_seconds=60,
        )
        adapter._jwks = FAKE_JWKS
        adapter._jwks_fetched_at = time.monotonic()

        claims = _make_claims()

        with patch("adapters.auth.keycloak.auth_adapter.jwt.decode", return_value=claims) as mock_decode:
            await adapter.validate_token("skewed-token")

        # Verify leeway was passed to jwt.decode
        call_args = mock_decode.call_args
        assert call_args[1]["options"]["leeway"] == 60


class TestRoleExtraction:
    """Role extraction from configurable claim path."""

    async def test_realm_mode_roles(self):
        adapter = KeycloakAuthAdapter(
            issuer_url="http://keycloak:8080/realms/squadops",
            audience="squadops-runtime",
            roles_claim_path="realm_access.roles",
        )
        adapter._jwks = FAKE_JWKS
        adapter._jwks_fetched_at = time.monotonic()

        claims = _make_claims(roles=["admin", "viewer"])

        with patch("adapters.auth.keycloak.auth_adapter.jwt.decode", return_value=claims):
            tc = await adapter.validate_token("token")

        assert tc.roles == ("admin", "viewer")

    async def test_client_mode_roles(self):
        adapter = KeycloakAuthAdapter(
            issuer_url="http://keycloak:8080/realms/squadops",
            audience="squadops-runtime",
            roles_claim_path="resource_access.my-client.roles",
        )
        adapter._jwks = FAKE_JWKS
        adapter._jwks_fetched_at = time.monotonic()

        claims = _make_claims()
        claims["resource_access"] = {"my-client": {"roles": ["editor", "viewer"]}}

        with patch("adapters.auth.keycloak.auth_adapter.jwt.decode", return_value=claims):
            tc = await adapter.validate_token("token")

        assert tc.roles == ("editor", "viewer")


class TestResolveIdentity:
    """Identity resolution from claims."""

    async def test_human_identity(self):
        adapter = KeycloakAuthAdapter(
            issuer_url="http://keycloak:8080/realms/squadops",
            audience="squadops-runtime",
        )
        adapter._jwks = FAKE_JWKS
        adapter._jwks_fetched_at = time.monotonic()

        claims = _make_claims(preferred_username="alice", roles=["admin"])

        with patch("adapters.auth.keycloak.auth_adapter.jwt.decode", return_value=claims):
            tc = await adapter.validate_token("token")
            identity = await adapter.resolve_identity(tc)

        assert identity.user_id == "user-1"
        assert identity.display_name == "alice"
        assert identity.identity_type == IdentityType.HUMAN
        assert identity.roles == ("admin",)

    async def test_service_identity(self):
        adapter = KeycloakAuthAdapter(
            issuer_url="http://keycloak:8080/realms/squadops",
            audience="squadops-runtime",
        )
        adapter._jwks = FAKE_JWKS
        adapter._jwks_fetched_at = time.monotonic()

        claims = _make_claims(sub="service-account-runtime")
        # Service accounts have azp but no preferred_username
        del claims["preferred_username"]
        claims["azp"] = "squadops-runtime"
        claims["name"] = "Runtime Service"

        with patch("adapters.auth.keycloak.auth_adapter.jwt.decode", return_value=claims):
            tc = await adapter.validate_token("token")
            identity = await adapter.resolve_identity(tc)

        assert identity.identity_type == IdentityType.SERVICE
        assert identity.display_name == "Runtime Service"


class TestClose:
    """Resource cleanup."""

    async def test_close_releases_client(self):
        adapter = KeycloakAuthAdapter(
            issuer_url="http://keycloak:8080/realms/squadops",
            audience="squadops-runtime",
        )
        mock_client = AsyncMock()
        mock_client.is_closed = False
        adapter._client = mock_client

        await adapter.close()
        mock_client.aclose.assert_awaited_once()
        assert adapter._client is None
