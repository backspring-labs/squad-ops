"""Tests for chat_stream() on LLMPort, Ollama adapter, and LLMRouter (SIP-0085 Phase 1)."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from squadops.llm.models import ChatMessage
from squadops.ports.llm.provider import LLMPort

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class _StreamingLLM(LLMPort):
    """Concrete LLMPort that yields configurable chunks."""

    def __init__(self, chunks: list[str] | None = None):
        self._chunks = ["hello", " ", "world"] if chunks is None else chunks

    async def generate(self, request: Any) -> Any:
        raise NotImplementedError

    async def chat(self, messages: Any, **kwargs: Any) -> ChatMessage:
        return ChatMessage(role="assistant", content="ok")

    async def chat_stream(
        self,
        messages: list[ChatMessage],
        model: str | None = None,
        max_tokens: int | None = None,
        temperature: float | None = None,
        timeout_seconds: float | None = None,
    ) -> AsyncIterator[str]:
        for chunk in self._chunks:
            yield chunk

    def list_models(self) -> list[str]:
        return []

    async def refresh_models(self) -> list[str]:
        return []

    async def health(self) -> dict[str, Any]:
        return {"healthy": True}


# ---------------------------------------------------------------------------
# Port contract tests
# ---------------------------------------------------------------------------


class TestChatStreamPort:
    """chat_stream() contract on LLMPort ABC."""

    async def test_yields_chunks_in_order(self):
        llm = _StreamingLLM(["a", "b", "c"])
        messages = [ChatMessage(role="user", content="hi")]
        chunks = [c async for c in llm.chat_stream(messages)]
        assert chunks == ["a", "b", "c"]

    async def test_empty_chunks_list_yields_nothing(self):
        llm = _StreamingLLM(chunks=[])
        messages = [ChatMessage(role="user", content="hi")]
        chunks = [c async for c in llm.chat_stream(messages)]
        assert chunks == []

    async def test_single_large_chunk(self):
        big = "x" * 10_000
        llm = _StreamingLLM([big])
        messages = [ChatMessage(role="user", content="hi")]
        chunks = [c async for c in llm.chat_stream(messages)]
        assert chunks == [big]


# ---------------------------------------------------------------------------
# Ollama adapter tests
# ---------------------------------------------------------------------------


class TestOllamaChatStream:
    """chat_stream() on OllamaAdapter."""

    async def test_streams_content_chunks(self):
        """Ollama streaming returns message.content from each NDJSON line."""
        from adapters.llm.ollama import OllamaAdapter

        adapter = OllamaAdapter(base_url="http://fake:11434")

        lines = [
            json.dumps({"message": {"content": "hello"}}),
            json.dumps({"message": {"content": " world"}}),
            json.dumps({"message": {"content": ""}}),  # empty — should be skipped
            json.dumps({"done": True, "message": {"content": ""}}),
        ]

        mock_response = AsyncMock()
        mock_response.raise_for_status = MagicMock()

        async def fake_aiter_lines():
            for line in lines:
                yield line

        mock_response.aiter_lines = fake_aiter_lines

        mock_client = AsyncMock()
        mock_client.stream = MagicMock(return_value=_AsyncContextManager(mock_response))
        adapter._client = mock_client

        messages = [ChatMessage(role="user", content="hi")]
        chunks = [c async for c in adapter.chat_stream(messages)]
        assert chunks == ["hello", " world"]

    async def test_stream_timeout_raises(self):
        """Timeout during streaming raises LLMTimeoutError."""
        from adapters.llm.ollama import OllamaAdapter
        from squadops.llm.exceptions import LLMTimeoutError

        adapter = OllamaAdapter(base_url="http://fake:11434")

        mock_client = AsyncMock()
        mock_client.stream = MagicMock(
            return_value=_AsyncContextManager(
                None, raise_on_enter=httpx.TimeoutException("timeout")
            )
        )
        adapter._client = mock_client

        messages = [ChatMessage(role="user", content="hi")]
        with pytest.raises(LLMTimeoutError, match="timed out"):
            async for _ in adapter.chat_stream(messages):
                pass

    async def test_stream_connect_error_raises(self):
        """Connection failure during streaming raises LLMConnectionError."""
        from adapters.llm.ollama import OllamaAdapter
        from squadops.llm.exceptions import LLMConnectionError

        adapter = OllamaAdapter(base_url="http://fake:11434")

        mock_client = AsyncMock()
        mock_client.stream = MagicMock(
            return_value=_AsyncContextManager(None, raise_on_enter=httpx.ConnectError("refused"))
        )
        adapter._client = mock_client

        messages = [ChatMessage(role="user", content="hi")]
        with pytest.raises(LLMConnectionError, match="Failed to connect"):
            async for _ in adapter.chat_stream(messages):
                pass

    async def test_stream_404_raises_model_not_found(self):
        """404 during streaming raises LLMModelNotFoundError."""
        from adapters.llm.ollama import OllamaAdapter
        from squadops.llm.exceptions import LLMModelNotFoundError

        adapter = OllamaAdapter(base_url="http://fake:11434")

        mock_response = AsyncMock()
        mock_request = MagicMock()
        mock_http_response = MagicMock(status_code=404)
        mock_response.raise_for_status = MagicMock(
            side_effect=httpx.HTTPStatusError(
                "Not Found", request=mock_request, response=mock_http_response
            )
        )

        mock_client = AsyncMock()
        mock_client.stream = MagicMock(return_value=_AsyncContextManager(mock_response))
        adapter._client = mock_client

        messages = [ChatMessage(role="user", content="hi")]
        with pytest.raises(LLMModelNotFoundError, match="not found"):
            async for _ in adapter.chat_stream(messages):
                pass

    async def test_stream_500_raises_connection_error(self):
        """Non-404 HTTP error during streaming raises LLMConnectionError."""
        from adapters.llm.ollama import OllamaAdapter
        from squadops.llm.exceptions import LLMConnectionError

        adapter = OllamaAdapter(base_url="http://fake:11434")

        mock_response = AsyncMock()
        mock_request = MagicMock()
        mock_http_response = MagicMock(status_code=500)
        mock_response.raise_for_status = MagicMock(
            side_effect=httpx.HTTPStatusError(
                "Server Error", request=mock_request, response=mock_http_response
            )
        )

        mock_client = AsyncMock()
        mock_client.stream = MagicMock(return_value=_AsyncContextManager(mock_response))
        adapter._client = mock_client

        messages = [ChatMessage(role="user", content="hi")]
        with pytest.raises(LLMConnectionError, match="chat_stream failed"):
            async for _ in adapter.chat_stream(messages):
                pass

    async def test_build_chat_payload_shared(self):
        """_build_chat_payload is used by both chat() and chat_stream()."""
        from adapters.llm.ollama import OllamaAdapter

        adapter = OllamaAdapter(base_url="http://fake:11434")
        messages = [ChatMessage(role="user", content="test")]

        payload_sync = adapter._build_chat_payload(
            messages,
            "test-model",
            100,
            0.5,
            stream=False,
        )
        payload_stream = adapter._build_chat_payload(
            messages,
            "test-model",
            100,
            0.5,
            stream=True,
        )

        assert payload_sync["stream"] is False
        assert payload_stream["stream"] is True
        assert payload_sync["model"] == payload_stream["model"] == "test-model"
        assert (
            payload_sync["options"]
            == payload_stream["options"]
            == {
                "num_predict": 100,
                "temperature": 0.5,
            }
        )


# ---------------------------------------------------------------------------
# Router forwarding tests
# ---------------------------------------------------------------------------


class TestRouterChatStreamForwarding:
    """LLMRouter.chat_stream() forwards to provider."""

    async def test_router_forwards_stream_chunks(self):
        from squadops.llm.router import LLMRouter

        provider = _StreamingLLM(["a", "b", "c"])
        router = LLMRouter(provider)
        messages = [ChatMessage(role="user", content="hi")]
        chunks = [c async for c in router.chat_stream(messages)]
        assert chunks == ["a", "b", "c"]

    async def test_router_forwards_stream_params(self):
        from squadops.llm.router import LLMRouter

        captured: dict[str, Any] = {}

        class _CapturingLLM(_StreamingLLM):
            async def chat_stream(
                self,
                messages: list[ChatMessage],
                **kwargs: Any,
            ) -> AsyncIterator[str]:
                captured.update(kwargs)
                yield "ok"

        provider = _CapturingLLM()
        router = LLMRouter(provider)
        messages = [ChatMessage(role="user", content="hi")]
        chunks = [
            c
            async for c in router.chat_stream(
                messages,
                model="m",
                max_tokens=10,
                temperature=0.1,
                timeout_seconds=5.0,
            )
        ]
        assert chunks == ["ok"]
        assert captured == {
            "model": "m",
            "max_tokens": 10,
            "temperature": 0.1,
            "timeout_seconds": 5.0,
        }


# ---------------------------------------------------------------------------
# NoOp stub test
# ---------------------------------------------------------------------------


class TestNoOpChatStream:
    """NoOpLLMPort.chat_stream() raises NotImplementedError."""

    async def test_noop_raises(self):
        from adapters.noop.ports import NoOpLLMPort

        port = NoOpLLMPort()
        messages = [ChatMessage(role="user", content="hi")]
        with pytest.raises(NotImplementedError, match="no LLM provider configured"):
            async for _ in port.chat_stream(messages):
                pass


# ---------------------------------------------------------------------------
# Test helpers
# ---------------------------------------------------------------------------


class _AsyncContextManager:
    """Fake async context manager for mocking httpx.stream()."""

    def __init__(self, response: Any, raise_on_enter: Exception | None = None):
        self._response = response
        self._raise = raise_on_enter

    async def __aenter__(self):
        if self._raise:
            raise self._raise
        return self._response

    async def __aexit__(self, *args: Any):
        pass


class TestThinkingSuppression:
    """#924 — a reasoning channel the adapter cannot read must not be billed."""

    @staticmethod
    def _payload(**kwargs):
        from adapters.llm.ollama import OllamaAdapter
        from squadops.ports.llm.provider import ChatMessage

        adapter = OllamaAdapter.__new__(OllamaAdapter)
        return adapter._build_chat_payload(
            [ChatMessage(role="user", content="x")], "m", None, None, **kwargs
        )

    def test_omitted_by_default_so_existing_calls_are_unchanged(self):
        """Bug caught: a default that silently changes every call in the system.

        Only one task was measured. Sending `think` unasked would alter manifest
        authoring, plan authoring and failure analysis on that single result.
        """
        assert "think" not in self._payload()

    def test_false_is_sent_so_the_request_is_not_inert(self):
        """Bug caught: the parameter is accepted, threaded, and never reaches the wire —
        a fix that looks applied while the model keeps spending the budget.

        Measured on qwen3.6:27b filling eight SIP-0104 scaffold slots: 5,727 completion
        tokens with reasoning, 413 without, for the same eight fill blocks. The adapter
        reads only `message.content` and declares THINKING_TOKENS: False, so the
        difference was billed and discarded unread.
        """
        assert self._payload(thinking=False)["think"] is False

    def test_true_is_sent_too_rather_than_treated_as_the_default(self):
        """`None` and `True` are different requests: one defers to the model, the other
        asks for reasoning explicitly. Collapsing them would make an explicit request
        unexpressible."""
        assert self._payload(thinking=True)["think"] is True

    async def test_the_router_forwards_it_instead_of_dropping_it(self):
        """Bug caught: the router swallows the parameter, making every caller's request
        a no-op with no way to observe it — the #918 shape (a layer that looks like a
        pass-through and is not)."""
        from squadops.llm.router import LLMRouter
        from squadops.ports.llm.provider import ChatMessage

        seen = {}

        class _Provider:
            default_model = "m"

            async def chat_stream_with_usage(self, messages, **kwargs):
                seen.update(kwargs)
                return ChatMessage(role="assistant", content="ok")

        router = LLMRouter.__new__(LLMRouter)
        router._provider = _Provider()
        await router.chat_stream_with_usage([ChatMessage(role="user", content="x")], thinking=False)

        assert seen["thinking"] is False

    async def test_a_provider_without_the_control_accepts_it_rather_than_raising(self):
        """The port states `thinking` is a request, not a guarantee. A provider with no
        equivalent must accept and ignore it — omitting it from the signature would turn
        a caller's keyword into a TypeError at runtime."""
        import inspect

        from adapters.llm.vllm import VLLMAdapter

        params = inspect.signature(VLLMAdapter.chat_stream_with_usage).parameters
        assert "thinking" in params
