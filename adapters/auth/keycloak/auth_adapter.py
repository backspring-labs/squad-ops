"""
Keycloak AuthPort adapter (SIP-0062).

JWT validation with JWKS caching, key rotation handling, and stampede protection.
"""

from __future__ import annotations

import logging
import time
from datetime import datetime, timezone

import httpx
from jose import JWTError, jwt
from jose.exceptions import ExpiredSignatureError

from squadops.auth.models import (
    Identity,
    IdentityResolutionError,
    IdentityType,
    TokenClaims,
    TokenValidationError,
)
from squadops.ports.auth.authentication import AuthPort

logger = logging.getLogger(__name__)


class KeycloakAuthAdapter(AuthPort):
    """OIDC token validation against a Keycloak realm via JWKS."""

    def __init__(
        self,
        issuer_url: str,
        audience: str,
        jwks_url: str | None = None,
        roles_claim_path: str = "realm_access.roles",
        jwks_cache_ttl_seconds: int = 3600,
        jwks_forced_refresh_min_interval_seconds: int = 30,
        clock_skew_seconds: int = 30,
        issuer_public_url: str | None = None,
    ) -> None:
        self._issuer_url = issuer_url.rstrip("/")
        self._audience = audience
        # Accept tokens with either the internal or public issuer URL
        self._allowed_issuers = {self._issuer_url}
        if issuer_public_url:
            self._allowed_issuers.add(issuer_public_url.rstrip("/"))
        self._jwks_url = jwks_url or f"{self._issuer_url}/protocol/openid-connect/certs"
        self._roles_claim_path = roles_claim_path
        self._jwks_cache_ttl = jwks_cache_ttl_seconds
        self._forced_refresh_min_interval = jwks_forced_refresh_min_interval_seconds
        self._clock_skew = clock_skew_seconds

        self._jwks: dict | None = None
        self._jwks_fetched_at: float = 0.0
        self._last_forced_refresh: float = 0.0
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=10.0)
        return self._client

    async def _fetch_jwks(self, *, force: bool = False) -> dict:
        """Fetch JWKS key set, with caching and stampede protection."""
        now = time.monotonic()

        if not force and self._jwks is not None:
            if (now - self._jwks_fetched_at) < self._jwks_cache_ttl:
                return self._jwks

        if force and (now - self._last_forced_refresh) < self._forced_refresh_min_interval:
            logger.debug("Skipping forced JWKS refresh (stampede protection)")
            if self._jwks is not None:
                return self._jwks

        try:
            client = await self._get_client()
            response = await client.get(self._jwks_url)
            response.raise_for_status()
            self._jwks = response.json()
            self._jwks_fetched_at = now
            if force:
                self._last_forced_refresh = now
            logger.debug("JWKS fetched from %s", self._jwks_url)
            return self._jwks
        except Exception as e:
            if self._jwks is not None:
                logger.warning("JWKS fetch failed, using cached keys: %s", e)
                return self._jwks
            raise TokenValidationError(f"Failed to fetch JWKS: {e}") from e

    async def validate_token(self, token: str) -> TokenClaims:
        """Decode and validate a JWT against JWKS."""
        jwks = await self._fetch_jwks()

        # When multiple issuers are allowed (internal + public URL), we validate
        # the issuer manually after decoding to accept tokens from either.
        verify_iss = len(self._allowed_issuers) == 1
        decode_opts = {
            "leeway": self._clock_skew,
            "verify_exp": True,
            "verify_aud": True,
            "verify_iss": verify_iss,
        }
        decode_kwargs = {"token": token, "key": jwks, "algorithms": ["RS256"],
                         "audience": self._audience, "options": decode_opts}
        if verify_iss:
            decode_kwargs["issuer"] = self._issuer_url

        try:
            payload = jwt.decode(**decode_kwargs)
        except ExpiredSignatureError as e:
            raise TokenValidationError("Token has expired") from e
        except JWTError as e:
            # On signature failure, try a forced JWKS refresh once (key rotation)
            if "signature" in str(e).lower() or "verification" in str(e).lower():
                logger.info("JWT signature failed, attempting JWKS refresh for key rotation")
                jwks = await self._fetch_jwks(force=True)
                decode_kwargs["key"] = jwks
                try:
                    payload = jwt.decode(**decode_kwargs)
                except JWTError as retry_e:
                    raise TokenValidationError(f"Token validation failed after JWKS refresh: {retry_e}") from retry_e
            else:
                raise TokenValidationError(f"Token validation failed: {e}") from e

        # Manual issuer check when multiple issuers are allowed
        if not verify_iss:
            token_issuer = payload.get("iss", "")
            if token_issuer not in self._allowed_issuers:
                raise TokenValidationError(
                    f"Invalid issuer: {token_issuer} (allowed: {self._allowed_issuers})"
                )

        # Extract roles from configurable claim path
        roles = self._extract_claim_path(payload, self._roles_claim_path)
        if not isinstance(roles, (list, tuple)):
            roles = []

        # Extract scopes
        scope_str = payload.get("scope", "")
        scopes = tuple(scope_str.split()) if scope_str else ()

        # Parse timestamps
        exp = payload.get("exp", 0)
        iat = payload.get("iat", 0)

        # Handle audience (can be string or list)
        aud = payload.get("aud", self._audience)
        if isinstance(aud, list):
            aud = tuple(aud)

        return TokenClaims(
            subject=payload.get("sub", ""),
            issuer=payload.get("iss", ""),
            audience=aud,
            expires_at=datetime.fromtimestamp(exp, tz=timezone.utc),
            issued_at=datetime.fromtimestamp(iat, tz=timezone.utc),
            roles=tuple(roles),
            scopes=scopes,
            raw_claims=payload,
        )

    async def resolve_identity(self, claims: TokenClaims) -> Identity:
        """Map token claims to a domain Identity."""
        if not claims.subject:
            raise IdentityResolutionError("Token claims missing 'sub' (subject)")

        raw = claims.raw_claims
        display_name = (
            raw.get("preferred_username")
            or raw.get("name")
            or raw.get("email")
            or claims.subject
        )

        # Determine identity type
        azp = raw.get("azp", "")
        identity_type = IdentityType.SERVICE if azp and not raw.get("preferred_username") else IdentityType.HUMAN

        return Identity(
            user_id=claims.subject,
            display_name=display_name,
            roles=claims.roles,
            scopes=claims.scopes,
            identity_type=identity_type,
        )

    async def close(self) -> None:
        """Release HTTP client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None

    @staticmethod
    def _extract_claim_path(payload: dict, path: str) -> list | None:
        """Extract a value from a nested dict using a dot-delimited path."""
        parts = path.split(".")
        current = payload
        for part in parts:
            if isinstance(current, dict):
                current = current.get(part)
            else:
                return None
            if current is None:
                return None
        return current
