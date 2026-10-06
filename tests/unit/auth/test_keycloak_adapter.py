"""Tests for KeycloakAuthAdapter (SIP-0062 Phase 2).

Tokens are signed here with a real realm key and ``cryptography`` alone, and verified end to
end: nothing patches the decode. So they say what the verifier accepts, whichever JWT library
it uses (#2073).
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from unittest.mock import AsyncMock, MagicMock

import pytest
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa

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


ISSUER = "http://keycloak:8080/realms/squadops"
PUBLIC_ISSUER = "http://spark:8180/realms/squadops"


def _b64(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


class _Realm:
    """A realm's signing key and the JWKS that publishes it."""

    def __init__(self, kid: str = "realm-key") -> None:
        self.key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        self.kid = kid
        numbers = self.key.public_key().public_numbers()
        self.jwks = {
            "keys": [
                {
                    "kty": "RSA",
                    "kid": kid,
                    "use": "sig",
                    "alg": "RS256",
                    "n": _b64(numbers.n.to_bytes((numbers.n.bit_length() + 7) // 8, "big")),
                    "e": _b64(numbers.e.to_bytes(3, "big")),
                }
            ]
        }

    def token(self, claims: dict, header: dict | None = None, sign=None) -> str:
        header = header or {"alg": "RS256", "typ": "JWT", "kid": self.kid}
        signing_input = f"{_b64(json.dumps(header).encode())}.{_b64(json.dumps(claims).encode())}"
        sign = sign or (lambda data: self.key.sign(data, padding.PKCS1v15(), hashes.SHA256()))
        return f"{signing_input}.{_b64(sign(signing_input.encode()))}"


@pytest.fixture(scope="module")
def realm() -> _Realm:
    return _Realm()


def _adapter(realm: _Realm, **kwargs) -> KeycloakAuthAdapter:
    """An adapter whose key cache holds the realm's JWKS, fetched just now."""
    adapter = KeycloakAuthAdapter(issuer_url=ISSUER, audience="squadops-runtime", **kwargs)
    adapter._jwks = realm.jwks
    adapter._jwks_fetched_at = time.monotonic()
    return adapter


def _serving(adapter: KeycloakAuthAdapter, jwks: dict) -> AsyncMock:
    """The realm's JWKS endpoint, answering ``jwks`` to the adapter's next fetch."""
    response = MagicMock()
    response.raise_for_status = lambda: None
    response.json.return_value = jwks
    client = AsyncMock()
    client.get = AsyncMock(return_value=response)
    client.is_closed = False
    adapter._client = client
    return client.get


FAKE_JWKS = {"keys": [{"kty": "RSA", "kid": "test-key-1", "n": "fake", "e": "AQAB"}]}


class TestJWKSFetchAndCaching:
    """JWKS fetch and caching tests."""

    async def test_jwks_fetch(self):
        adapter = KeycloakAuthAdapter(
            issuer_url="http://keycloak:8080/realms/squadops",
            audience="squadops-runtime",
        )

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
    async def test_valid_token(self, realm):
        token = realm.token(_make_claims(roles=["admin", "operator"]))

        tc = await _adapter(realm).validate_token(token)

        assert tc.subject == "user-1"
        assert tc.issuer == ISSUER
        assert tc.roles == ("admin", "operator")
        assert tc.audience == "squadops-runtime"

    @pytest.mark.parametrize(
        ("claims", "public_issuer", "audience"),
        [
            ({"iss": PUBLIC_ISSUER}, PUBLIC_ISSUER, "squadops-runtime"),
            ({"aud": ["account", "squadops-runtime"]}, None, ("account", "squadops-runtime")),
        ],
        ids=["the-public-issuer-the-cli-holds", "an-audience-list-naming-the-runtime"],
    )
    async def test_a_token_the_deploy_issues_is_accepted(
        self, realm, claims, public_issuer, audience
    ):
        """The CLI's tokens carry the public issuer URL (``http://spark:8180/...``), which the
        runtime accepts beside its internal one."""
        adapter = _adapter(realm, issuer_public_url=public_issuer)

        tc = await adapter.validate_token(realm.token(_make_claims(**claims)))

        assert (tc.issuer, tc.audience) == (claims.get("iss", ISSUER), audience)

    @pytest.mark.parametrize(
        ("claims", "public_issuer"),
        [
            ({"iss": "http://elsewhere:8080/realms/squadops"}, None),
            ({"iss": "http://elsewhere:8080/realms/squadops"}, PUBLIC_ISSUER),
            ({"aud": "another-client"}, None),
            ({"aud": ["account"]}, None),
        ],
        ids=[
            "another-issuer",
            "another-issuer-beside-a-public-one",
            "another-audience",
            "an-audience-list-without-the-runtime",
        ],
    )
    async def test_a_token_for_another_issuer_or_audience_is_refused(
        self, realm, claims, public_issuer
    ):
        adapter = _adapter(realm, issuer_public_url=public_issuer)

        with pytest.raises(TokenValidationError):
            await adapter.validate_token(realm.token(_make_claims(**claims)))

    @pytest.mark.parametrize(
        ("dropped_claim", "header", "iat_offset"),
        [
            ("aud", None, 0),
            (None, {"alg": "RS256", "typ": "JWT"}, 0),
            (None, None, 120),
        ],
        ids=["no-audience", "no-key-id", "issued-beyond-the-skew-ahead"],
    )
    async def test_what_python_jose_accepted_and_no_realm_client_issues_is_refused(
        self, realm, dropped_claim, header, iat_offset
    ):
        """#2073: python-jose accepted all three, PyJWT refuses them. Every client in every realm
        has an audience mapper adding ``squadops-runtime``, Keycloak names its signing key, and a
        token issued 120s ahead is outside the 30s skew. Refused at once, never read as a rotated
        key."""
        claims = _make_claims(iat_offset=iat_offset)
        if dropped_claim:
            del claims[dropped_claim]
        adapter = _adapter(realm)
        get = _serving(adapter, realm.jwks)

        with pytest.raises(TokenValidationError):
            await adapter.validate_token(realm.token(claims, header=header))
        assert get.await_count == 0

    async def test_a_malformed_token_is_refused(self, realm):
        with pytest.raises(TokenValidationError, match="Token validation failed"):
            await _adapter(realm).validate_token("not-a-jwt")

    @pytest.mark.parametrize(("skew", "accepted"), [(60, True), (0, False)])
    async def test_an_expiry_inside_the_clock_skew_is_accepted(self, realm, skew, accepted):
        token = realm.token(_make_claims(exp_offset=-30))
        adapter = _adapter(realm, clock_skew_seconds=skew)

        if accepted:
            assert (await adapter.validate_token(token)).subject == "user-1"
        else:
            with pytest.raises(TokenValidationError, match="expired"):
                await adapter.validate_token(token)

    async def test_a_token_signed_by_a_rotated_key_verifies_after_one_forced_refresh(self, realm):
        rotated = _Realm(kid="rotated-key")
        adapter = _adapter(realm)  # the cache still holds the key before the rotation
        get = _serving(adapter, rotated.jwks)

        tc = await adapter.validate_token(rotated.token(_make_claims(sub="user-2")))

        assert tc.subject == "user-2"
        assert get.await_count == 1

    async def test_a_signature_no_realm_key_verifies_is_refused_after_one_refresh(self, realm):
        """A stranger's key under the realm's ``kid``: the refresh finds the same key set, and
        the token is still refused."""
        stranger = _Realm(kid=realm.kid)
        adapter = _adapter(realm)
        get = _serving(adapter, realm.jwks)

        with pytest.raises(TokenValidationError, match="after JWKS refresh"):
            await adapter.validate_token(stranger.token(_make_claims()))
        assert get.await_count == 1


class TestRoleExtraction:
    """Role extraction from configurable claim path."""

    async def test_realm_mode_roles(self, realm):
        adapter = _adapter(realm, roles_claim_path="realm_access.roles")

        tc = await adapter.validate_token(realm.token(_make_claims(roles=["admin", "viewer"])))

        assert tc.roles == ("admin", "viewer")

    async def test_client_mode_roles(self, realm):
        adapter = _adapter(realm, roles_claim_path="resource_access.my-client.roles")
        claims = _make_claims()
        claims["resource_access"] = {"my-client": {"roles": ["editor", "viewer"]}}

        tc = await adapter.validate_token(realm.token(claims))

        assert tc.roles == ("editor", "viewer")


class TestResolveIdentity:
    """Identity resolution from claims."""

    async def test_human_identity(self, realm):
        adapter = _adapter(realm)
        token = realm.token(_make_claims(preferred_username="alice", roles=["admin"]))

        identity = await adapter.resolve_identity(await adapter.validate_token(token))

        assert identity.user_id == "user-1"
        assert identity.display_name == "alice"
        assert identity.identity_type == IdentityType.HUMAN
        assert identity.roles == ("admin",)

    async def test_service_identity(self, realm):
        adapter = _adapter(realm)
        claims = _make_claims(sub="service-account-runtime")
        # Service accounts have azp but no preferred_username
        del claims["preferred_username"]
        claims["azp"] = "squadops-runtime"
        claims["name"] = "Runtime Service"

        identity = await adapter.resolve_identity(await adapter.validate_token(realm.token(claims)))

        assert identity.identity_type == IdentityType.SERVICE
        assert identity.display_name == "Runtime Service"


class TestRoleScopeBridge:
    """#270: resolve_identity merges role-implied scopes into identity.scopes so
    #150's scope-gated cycle routes accept the role-bearing tokens Keycloak issues
    (the realm grants roles, not cycles:* scopes)."""

    @pytest.fixture(autouse=True)
    def _realm(self, realm):
        self.realm = realm

    async def _resolve(self, **claim_kwargs):
        adapter = _adapter(self.realm)
        token = self.realm.token(_make_claims(**claim_kwargs))
        return await adapter.resolve_identity(await adapter.validate_token(token))

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
    restricted". The dependency audit accepted it because this verifier restricts them. These hold
    that against a real key set, with no JWT library in the test, so they outlast the library.

    Bug caught: an HMAC algorithm added to the allow-list, or the restriction dropped. The verifier
    would then rest on one barrier: the key's form, the JWKS's RSA keys, which the library refuses
    as an HMAC secret. The advisory is a bypass of exactly that kind of guard, and the realm's
    public key is published at the JWKS endpoint."""

    @staticmethod
    def _adapter(jwks):
        adapter = KeycloakAuthAdapter(issuer_url=ISSUER, audience="squadops-runtime")
        fetch = AsyncMock(return_value=jwks)
        adapter._fetch_jwks = fetch
        return adapter, fetch

    async def test_a_token_forged_with_the_realms_public_key_is_refused(self, realm):
        der = realm.key.public_key().public_bytes(
            serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo
        )
        forged = realm.token(
            _make_claims(roles=["admin"]),
            header={"alg": "HS256", "typ": "JWT", "kid": realm.kid},
            sign=lambda data: hmac.new(der, data, hashlib.sha256).digest(),
        )
        adapter, fetch = self._adapter(realm.jwks)

        with pytest.raises(TokenValidationError):
            await adapter.validate_token(forged)
        # Refused on its algorithm, never read as a rotated key: no forced re-fetch of the key set.
        assert fetch.await_count == 1

    async def test_a_token_the_realm_signed_still_verifies(self, realm):
        """The control: the restriction refuses the forgery and nothing the realm issues."""
        adapter, _fetch = self._adapter(realm.jwks)

        claims = await adapter.validate_token(realm.token(_make_claims(sub="user-9")))

        assert claims.subject == "user-9"
