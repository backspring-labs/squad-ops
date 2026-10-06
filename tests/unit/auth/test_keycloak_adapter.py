"""Tests for KeycloakAuthAdapter (SIP-0062 Phase 2)."""

from __future__ import annotations

import time
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

        with patch(
            "adapters.auth.keycloak.auth_adapter.jwt.decode", return_value=claims
        ) as mock_decode:
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


class TestRoleScopeBridge:
    """#270: resolve_identity merges role-implied scopes into identity.scopes so
    #150's scope-gated cycle routes accept the role-bearing tokens Keycloak issues
    (the realm grants roles, not cycles:* scopes)."""

    async def _resolve(self, **claim_kwargs):
        adapter = KeycloakAuthAdapter(
            issuer_url="http://keycloak:8080/realms/squadops",
            audience="squadops-runtime",
        )
        adapter._jwks = FAKE_JWKS
        adapter._jwks_fetched_at = time.monotonic()
        claims = _make_claims(**claim_kwargs)
        with patch("adapters.auth.keycloak.auth_adapter.jwt.decode", return_value=claims):
            return await adapter.resolve_identity(await adapter.validate_token("token"))

    async def test_operator_role_grants_cycles_write(self):
        # The exact failure behind #270: scope claim empty, but the operator role
        # must satisfy require_scopes(cycles:write).
        identity = await self._resolve(roles=["operator"], scope="")
        assert "cycles:read" in identity.scopes
        assert "cycles:write" in identity.scopes

    async def test_viewer_role_is_read_only(self):
        identity = await self._resolve(roles=["viewer"], scope="")
        assert "cycles:read" in identity.scopes
        assert "cycles:write" not in identity.scopes

    async def test_unmapped_role_grants_no_implied_scopes(self):
        # No silent grant for an unrecognized role — still 403-able on cycle routes.
        identity = await self._resolve(roles=["randorole"], scope="")
        assert "cycles:read" not in identity.scopes
        assert "cycles:write" not in identity.scopes

    async def test_token_scopes_unioned_with_role_implied(self):
        # Explicit OAuth scopes on the token are preserved alongside role-implied.
        identity = await self._resolve(roles=["viewer"], scope="email profile")
        assert "email" in identity.scopes and "profile" in identity.scopes
        assert "cycles:read" in identity.scopes


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


class TestTheVerifierPinsItsAlgorithm:
    """GHSA-3qf3-8w2g-rqmx (CVE-2026-85394): python-jose through 3.5.0 verifies a token signed HS256
    with the service's DER-encoded public key as the HMAC secret "when algorithms are not explicitly
    restricted". The dependency audit accepts it because this verifier restricts them. These hold
    that against a real key set, with no JWT library in the test, so they outlast the library.

    Bug caught: an HMAC algorithm added to the allow-list, or the restriction dropped. The verifier
    would then rest on one barrier: the key's form, the JWKS's RSA keys, which python-jose refuses as
    an HMAC secret. The advisory is a bypass of exactly that kind of guard, and the realm's public key
    is published at the JWKS endpoint."""

    ISSUER = "http://keycloak:8080/realms/squadops"

    @staticmethod
    def _b64(raw: bytes) -> str:
        import base64

        return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()

    def _realm(self):
        from cryptography.hazmat.primitives.asymmetric import rsa

        key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        numbers = key.public_key().public_numbers()
        jwk = {
            "kty": "RSA",
            "kid": "realm-key",
            "use": "sig",
            "alg": "RS256",
            "n": self._b64(numbers.n.to_bytes((numbers.n.bit_length() + 7) // 8, "big")),
            "e": self._b64(numbers.e.to_bytes(3, "big")),
        }
        return key, {"keys": [jwk]}

    def _token(self, header: dict, claims: dict, sign) -> str:
        import json

        signing_input = (
            f"{self._b64(json.dumps(header).encode())}.{self._b64(json.dumps(claims).encode())}"
        )
        return f"{signing_input}.{self._b64(sign(signing_input.encode()))}"

    def _adapter(self, jwks):
        adapter = KeycloakAuthAdapter(issuer_url=self.ISSUER, audience="squadops-runtime")
        fetch = AsyncMock(return_value=jwks)
        adapter._fetch_jwks = fetch
        return adapter, fetch

    async def test_a_token_forged_with_the_realms_public_key_is_refused(self):
        import hashlib
        import hmac

        from cryptography.hazmat.primitives import serialization

        key, jwks = self._realm()
        der = key.public_key().public_bytes(
            serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo
        )
        forged = self._token(
            {"alg": "HS256", "typ": "JWT", "kid": "realm-key"},
            _make_claims(iss=self.ISSUER, roles=["admin"]),
            lambda data: hmac.new(der, data, hashlib.sha256).digest(),
        )
        adapter, fetch = self._adapter(jwks)

        with pytest.raises(TokenValidationError):
            await adapter.validate_token(forged)
        # Refused on its algorithm, never read as a rotated key: no forced re-fetch of the key set.
        assert fetch.await_count == 1

    async def test_a_token_the_realm_signed_still_verifies(self):
        """The control: the restriction refuses the forgery and nothing the realm issues."""
        from cryptography.hazmat.primitives import hashes
        from cryptography.hazmat.primitives.asymmetric import padding

        key, jwks = self._realm()
        genuine = self._token(
            {"alg": "RS256", "typ": "JWT", "kid": "realm-key"},
            _make_claims(iss=self.ISSUER, sub="user-9"),
            lambda data: key.sign(data, padding.PKCS1v15(), hashes.SHA256()),
        )
        adapter, _fetch = self._adapter(jwks)

        claims = await adapter.validate_token(genuine)

        assert claims.subject == "user-9"
