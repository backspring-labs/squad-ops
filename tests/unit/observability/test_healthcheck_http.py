"""
Unit tests for HealthCheckHttpReporter (#326).

The reporter posts heartbeats to the authed /api/v1 lane and attaches a
Bearer token when a token provider (agent service identity) is configured.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from adapters.observability.healthcheck_http import HealthCheckHttpReporter

pytestmark = pytest.mark.domain_agents


def _mock_async_client(status_code: int = 200, text: str = "ok"):
    """Mock httpx.AsyncClient context manager capturing post() calls."""
    response = MagicMock(status_code=status_code, text=text)
    client = MagicMock()
    client.post = AsyncMock(return_value=response)
    ctx = MagicMock()
    ctx.__aenter__ = AsyncMock(return_value=client)
    ctx.__aexit__ = AsyncMock(return_value=False)
    return ctx, client


async def _send(reporter, **kwargs):
    defaults = {"agent_id": "max", "lifecycle_state": "READY"}
    defaults.update(kwargs)
    await reporter.send_status(**defaults)


class TestSendStatus:
    async def test_posts_to_authed_lane(self):
        """#326: heartbeats go to /api/v1/agents/status, not the removed
        /health write route (which would 404 and drop every heartbeat)."""
        ctx, client = _mock_async_client()
        reporter = HealthCheckHttpReporter(base_url="http://api:8001")
        with patch("adapters.observability.healthcheck_http.httpx.AsyncClient", return_value=ctx):
            await _send(reporter, tps=2.7, current_task_id="t-1")

        (url,), kwargs = client.post.call_args
        assert url == "http://api:8001/api/v1/agents/status"
        assert kwargs["json"]["agent_id"] == "max"
        assert kwargs["json"]["lifecycle_state"] == "READY"
        assert kwargs["json"]["tps"] == 2  # floats truncate to int
        assert kwargs["json"]["current_task_id"] == "t-1"

    async def test_bearer_token_attached_when_provider_configured(self):
        ctx, client = _mock_async_client()
        reporter = HealthCheckHttpReporter(
            base_url="http://api:8001",
            token_provider=AsyncMock(return_value="svc-token-abc"),
        )
        with patch("adapters.observability.healthcheck_http.httpx.AsyncClient", return_value=ctx):
            await _send(reporter)

        _, kwargs = client.post.call_args
        assert kwargs["headers"]["Authorization"] == "Bearer svc-token-abc"

    async def test_no_auth_header_without_provider(self):
        ctx, client = _mock_async_client()
        reporter = HealthCheckHttpReporter(base_url="http://api:8001")
        with patch("adapters.observability.healthcheck_http.httpx.AsyncClient", return_value=ctx):
            await _send(reporter)

        _, kwargs = client.post.call_args
        assert "Authorization" not in kwargs["headers"]

    async def test_http_error_swallowed_when_fail_silently(self):
        """An auth misconfiguration (401) must not crash the heartbeat loop."""
        ctx, _ = _mock_async_client(status_code=401, text="Invalid or expired token")
        reporter = HealthCheckHttpReporter(base_url="http://api:8001")
        with patch("adapters.observability.healthcheck_http.httpx.AsyncClient", return_value=ctx):
            await _send(reporter)  # no raise

    async def test_http_error_raises_when_not_silent(self):
        ctx, _ = _mock_async_client(status_code=401, text="Invalid or expired token")
        reporter = HealthCheckHttpReporter(base_url="http://api:8001", fail_silently=False)
        with patch("adapters.observability.healthcheck_http.httpx.AsyncClient", return_value=ctx):
            with pytest.raises(RuntimeError, match="401"):
                await _send(reporter)

    async def test_token_provider_failure_swallowed_when_fail_silently(self):
        """Keycloak being down must not crash the heartbeat loop — the send
        fails silently and the next tick retries."""
        ctx, client = _mock_async_client()
        reporter = HealthCheckHttpReporter(
            base_url="http://api:8001",
            token_provider=AsyncMock(side_effect=ConnectionError("keycloak down")),
        )
        with patch("adapters.observability.healthcheck_http.httpx.AsyncClient", return_value=ctx):
            await _send(reporter)  # no raise
        client.post.assert_not_awaited()
