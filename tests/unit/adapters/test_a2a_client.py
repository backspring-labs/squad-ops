"""Tests for A2AClientAdapter (SIP-0085 Phase 1)."""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from adapters.comms.a2a_client import A2AClientAdapter

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class _FakeStreamResponse:
    """Fake httpx streaming response."""

    def __init__(self, lines: list[str], status_code: int = 200):
        self._lines = lines
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            raise httpx.HTTPStatusError(
                "error", request=MagicMock(), response=MagicMock(status_code=self.status_code)
            )

    async def aiter_lines(self):
        for line in self._lines:
            yield line


class _AsyncContextManager:
    """Fake async context manager for httpx.stream()."""

    def __init__(self, response: Any = None, raise_on_enter: Exception | None = None):
        self._response = response
        self._raise = raise_on_enter

    async def __aenter__(self):
        if self._raise:
            raise self._raise
        return self._response

    async def __aexit__(self, *args: Any):
        pass


# ---------------------------------------------------------------------------
# Agent card tests
# ---------------------------------------------------------------------------


class TestGetAgentCard:
    """Tests for get_agent_card()."""

    async def test_fetches_agent_card(self):
        client = A2AClientAdapter()
        card_data = {"name": "Joi", "description": "Comms agent", "version": "1.0.0"}

        mock_response = AsyncMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json = MagicMock(return_value=card_data)

        mock_http = AsyncMock()
        mock_http.get = AsyncMock(return_value=mock_response)
        client._client = mock_http

        result = await client.get_agent_card("http://localhost:5000")
        assert result == card_data
        mock_http.get.assert_called_once_with(
            "http://localhost:5000/.well-known/agent.json",
            timeout=10.0,
        )

    async def test_strips_trailing_slash_from_base_url(self):
        client = A2AClientAdapter()
        mock_response = AsyncMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {}

        mock_http = AsyncMock()
        mock_http.get = AsyncMock(return_value=mock_response)
        client._client = mock_http

        await client.get_agent_card("http://localhost:5000/")
        mock_http.get.assert_called_once_with(
            "http://localhost:5000/.well-known/agent.json",
            timeout=10.0,
        )

    async def test_connection_error_propagates(self):
        client = A2AClientAdapter()
        mock_http = AsyncMock()
        mock_http.get = AsyncMock(side_effect=httpx.ConnectError("refused"))
        client._client = mock_http

        with pytest.raises(httpx.ConnectError):
            await client.get_agent_card("http://localhost:5000")


# ---------------------------------------------------------------------------
# Streaming tests
# ---------------------------------------------------------------------------


class TestSendMessageStream:
    """Tests for send_message_stream()."""

    async def test_extracts_text_from_status_parts(self):
        """SSE data with status.message.parts text is extracted."""
        client = A2AClientAdapter()
        sse_lines = [
            "data: "
            + json.dumps(
                {
                    "result": {
                        "status": {
                            "message": {
                                "parts": [{"kind": "text", "text": "hello"}],
                            }
                        }
                    }
                }
            ),
            "data: "
            + json.dumps(
                {
                    "result": {
                        "status": {
                            "message": {
                                "parts": [{"kind": "text", "text": " world"}],
                            }
                        }
                    }
                }
            ),
            "",  # empty line — should be skipped
        ]

        mock_http = AsyncMock()
        mock_http.stream = MagicMock(
            return_value=_AsyncContextManager(_FakeStreamResponse(sse_lines))
        )
        client._client = mock_http

        chunks = [c async for c in client.send_message_stream("http://localhost:5000", "hi")]
        assert chunks == ["hello", " world"]

    async def test_extracts_text_from_artifact_parts(self):
        """SSE data with artifact.parts text is extracted."""
        client = A2AClientAdapter()
        sse_lines = [
            "data: "
            + json.dumps(
                {
                    "result": {
                        "artifact": {
                            "parts": [{"kind": "text", "text": "result text"}],
                        }
                    }
                }
            ),
        ]

        mock_http = AsyncMock()
        mock_http.stream = MagicMock(
            return_value=_AsyncContextManager(_FakeStreamResponse(sse_lines))
        )
        client._client = mock_http

        chunks = [c async for c in client.send_message_stream("http://localhost:5000", "hi")]
        assert chunks == ["result text"]

    async def test_skips_non_data_lines(self):
        """Non-data SSE lines (event:, id:, retry:) are ignored."""
        client = A2AClientAdapter()
        sse_lines = [
            "event: message",
            "id: 123",
            "data: "
            + json.dumps(
                {"result": {"status": {"message": {"parts": [{"kind": "text", "text": "ok"}]}}}}
            ),
            "retry: 5000",
        ]

        mock_http = AsyncMock()
        mock_http.stream = MagicMock(
            return_value=_AsyncContextManager(_FakeStreamResponse(sse_lines))
        )
        client._client = mock_http

        chunks = [c async for c in client.send_message_stream("http://localhost:5000", "hi")]
        assert chunks == ["ok"]

    async def test_skips_invalid_json(self):
        """Malformed JSON in SSE data is skipped, not raised."""
        client = A2AClientAdapter()
        sse_lines = [
            "data: not-json",
            "data: "
            + json.dumps(
                {"result": {"status": {"message": {"parts": [{"kind": "text", "text": "ok"}]}}}}
            ),
        ]

        mock_http = AsyncMock()
        mock_http.stream = MagicMock(
            return_value=_AsyncContextManager(_FakeStreamResponse(sse_lines))
        )
        client._client = mock_http

        chunks = [c async for c in client.send_message_stream("http://localhost:5000", "hi")]
        assert chunks == ["ok"]

    async def test_timeout_propagates(self):
        """Timeout during streaming raises httpx.TimeoutException."""
        client = A2AClientAdapter()

        mock_http = AsyncMock()
        mock_http.stream = MagicMock(
            return_value=_AsyncContextManager(
                None, raise_on_enter=httpx.TimeoutException("timeout")
            )
        )
        client._client = mock_http

        with pytest.raises(httpx.TimeoutException):
            async for _ in client.send_message_stream("http://localhost:5000", "hi"):
                pass

    async def test_connect_error_propagates(self):
        """Connection error during streaming raises httpx.ConnectError."""
        client = A2AClientAdapter()

        mock_http = AsyncMock()
        mock_http.stream = MagicMock(
            return_value=_AsyncContextManager(None, raise_on_enter=httpx.ConnectError("refused"))
        )
        client._client = mock_http

        with pytest.raises(httpx.ConnectError):
            async for _ in client.send_message_stream("http://localhost:5000", "hi"):
                pass


# ---------------------------------------------------------------------------
# Payload construction tests
# ---------------------------------------------------------------------------


class TestBuildSendPayload:
    """Tests for _build_send_payload static method."""

    def test_basic_payload(self):
        payload = A2AClientAdapter._build_send_payload("hello")
        assert payload["jsonrpc"] == "2.0"
        assert payload["method"] == "message/send"
        assert payload["params"]["message"]["role"] == "user"
        assert payload["params"]["message"]["parts"] == [
            {"kind": "text", "text": "hello"},
        ]

    def test_payload_with_context_and_task(self):
        payload = A2AClientAdapter._build_send_payload(
            "hello",
            context_id="ctx-1",
            task_id="task-1",
        )
        assert payload["params"]["message"]["contextId"] == "ctx-1"
        assert payload["params"]["message"]["taskId"] == "task-1"

    def test_payload_without_optional_ids(self):
        payload = A2AClientAdapter._build_send_payload("hello")
        assert "contextId" not in payload["params"]["message"]
        assert "taskId" not in payload["params"]["message"]


# ---------------------------------------------------------------------------
# Close tests
# ---------------------------------------------------------------------------


class TestClose:
    """Tests for client close()."""

    async def test_close_when_client_exists(self):
        client = A2AClientAdapter()
        mock_http = AsyncMock()
        client._client = mock_http
        await client.close()
        mock_http.aclose.assert_called_once()
        assert client._client is None

    async def test_close_when_no_client(self):
        client = A2AClientAdapter()
        await client.close()  # Should not raise
