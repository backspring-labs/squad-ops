"""
ServiceTokenClient — client credentials flow (SIP-0062 Phase 3b).

Domain-level code (no adapter imports). Acquires tokens via OAuth2
grant_type=client_credentials for service-to-service authentication.
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass

import httpx

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ServiceToken:
    """A cached service token, with its expiry on both clocks (#2493).

    The monotonic clock doesn't advance while the host is suspended, so after a sleep a token
    whose wall-clock ``exp`` has passed at the issuer still reads as fresh on it. The wall clock
    counts the suspended interval, but can be stepped back when it is corrected. So the token is
    due when either clock says it is.
    """

    access_token: str
    expires_at: float  # time.monotonic() base + expires_in
    wall_expires_at: float  # time.time() base + expires_in: counts a suspended interval
    token_type: str = "Bearer"

    def is_due(self, margin: float) -> bool:
        """Whether either clock has reached the expiry less ``margin``."""
        return (
            time.monotonic() >= self.expires_at - margin
            or time.time() >= self.wall_expires_at - margin
        )


class ServiceTokenClient:
    """Acquire and cache OAuth2 client_credentials tokens.

    Uses asyncio.Lock to prevent concurrent refresh stampede.
    """

    def __init__(
        self,
        token_endpoint: str,
        client_id: str,
        client_secret: str,
        *,
        refresh_margin_seconds: int = 30,
    ) -> None:
        self._token_endpoint = token_endpoint
        self._client_id = client_id
        self._client_secret = client_secret
        self._refresh_margin = refresh_margin_seconds
        self._cached: ServiceToken | None = None
        self._lock = asyncio.Lock()
        self._http_client = httpx.AsyncClient()

    async def get_token(self) -> str:
        """Return cached token, refreshing if near expiry.

        Guarded by asyncio.Lock so concurrent callers don't
        simultaneously trigger token fetches.
        """
        async with self._lock:
            if self._cached and not self._cached.is_due(self._refresh_margin):
                return self._cached.access_token
            token = await self._fetch_token()
            self._cached = token
            return token.access_token

    async def _fetch_token(self) -> ServiceToken:
        """POST to token endpoint with client_credentials grant."""
        response = await self._http_client.post(
            self._token_endpoint,
            data={
                "grant_type": "client_credentials",
                "client_id": self._client_id,
                "client_secret": self._client_secret,
            },
        )
        response.raise_for_status()
        data = response.json()
        expires_in = data["expires_in"]
        return ServiceToken(
            access_token=data["access_token"],
            expires_at=time.monotonic() + expires_in,
            wall_expires_at=time.time() + expires_in,
            token_type=data.get("token_type", "Bearer"),
        )

    async def close(self) -> None:
        """Release httpx client."""
        await self._http_client.aclose()
