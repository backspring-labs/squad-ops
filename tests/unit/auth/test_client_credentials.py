"""Tests for ServiceTokenClient (SIP-0062 Phase 3b)."""

import asyncio
import time
from unittest.mock import AsyncMock, MagicMock

import pytest

from squadops.auth.client_credentials import ServiceToken, ServiceTokenClient


def _mock_response(access_token="tok-123", expires_in=300, status_code=200):
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = {
        "access_token": access_token,
        "expires_in": expires_in,
        "token_type": "Bearer",
    }
    resp.raise_for_status = MagicMock()
    if status_code >= 400:
        from httpx import HTTPStatusError

        resp.raise_for_status.side_effect = HTTPStatusError(
            "error", request=MagicMock(), response=resp
        )
    return resp


@pytest.mark.auth
class TestServiceToken:
    def test_frozen_dataclass(self):
        token = ServiceToken(access_token="abc", expires_at=100.0)
        assert token.access_token == "abc"
        assert token.expires_at == 100.0
        assert token.token_type == "Bearer"

        with pytest.raises(AttributeError):
            token.access_token = "new"  # type: ignore


@pytest.mark.auth
class TestServiceTokenClient:
    async def test_fetch_token(self):
        """Token fetch returns access_token from mocked HTTP."""
        client = ServiceTokenClient(
            token_endpoint="http://keycloak/token",
            client_id="svc",
            client_secret="secret",
        )
        mock_resp = _mock_response(access_token="fetched-tok", expires_in=300)
        client._http_client = AsyncMock()
        client._http_client.post.return_value = mock_resp

        token = await client.get_token()
        assert token == "fetched-tok"
        client._http_client.post.assert_awaited_once()

    async def test_caching_within_ttl(self):
        """Second call returns cached token without HTTP call."""
        client = ServiceTokenClient(
            token_endpoint="http://keycloak/token",
            client_id="svc",
            client_secret="secret",
            refresh_margin_seconds=30,
        )
        mock_resp = _mock_response(access_token="cached-tok", expires_in=300)
        client._http_client = AsyncMock()
        client._http_client.post.return_value = mock_resp

        tok1 = await client.get_token()
        tok2 = await client.get_token()
        assert tok1 == tok2 == "cached-tok"
        # Only one HTTP call
        assert client._http_client.post.await_count == 1

    async def test_refresh_near_expiry(self):
        """Refreshes token when within margin of expiry."""
        client = ServiceTokenClient(
            token_endpoint="http://keycloak/token",
            client_id="svc",
            client_secret="secret",
            refresh_margin_seconds=30,
        )
        # Manually set a cached token that's about to expire
        client._cached = ServiceToken(
            access_token="old-tok",
            expires_at=time.monotonic() + 5,  # 5 seconds left, within 30s margin
        )
        mock_resp = _mock_response(access_token="new-tok", expires_in=300)
        client._http_client = AsyncMock()
        client._http_client.post.return_value = mock_resp

        token = await client.get_token()
        assert token == "new-tok"
        client._http_client.post.assert_awaited_once()

    async def test_concurrent_get_token_only_fetches_once(self):
        """asyncio.Lock prevents concurrent refresh stampede."""
        call_count = 0

        async def _slow_post(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            await asyncio.sleep(0.05)
            return _mock_response(access_token=f"tok-{call_count}", expires_in=300)

        client = ServiceTokenClient(
            token_endpoint="http://keycloak/token",
            client_id="svc",
            client_secret="secret",
        )
        client._http_client = AsyncMock()
        client._http_client.post = _slow_post

        # Launch 5 concurrent get_token calls
        results = await asyncio.gather(
            client.get_token(),
            client.get_token(),
            client.get_token(),
            client.get_token(),
            client.get_token(),
        )
        # All should get the same token (only one fetch)
        assert all(r == results[0] for r in results)
        assert call_count == 1

    async def test_http_error_raises(self):
        """HTTP error is propagated."""
        client = ServiceTokenClient(
            token_endpoint="http://keycloak/token",
            client_id="svc",
            client_secret="secret",
        )
        mock_resp = _mock_response(status_code=401)
        client._http_client = AsyncMock()
        client._http_client.post.return_value = mock_resp

        with pytest.raises(Exception):
            await client.get_token()

    async def test_close(self):
        """close() releases httpx client."""
        client = ServiceTokenClient(
            token_endpoint="http://keycloak/token",
            client_id="svc",
            client_secret="secret",
        )
        client._http_client = AsyncMock()
        await client.close()
        client._http_client.aclose.assert_awaited_once()
