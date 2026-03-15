"""Unit tests for LLM port interfaces."""

from collections.abc import AsyncIterator
from typing import Any

import pytest

from squadops.llm.models import ChatMessage, LLMRequest, LLMResponse
from squadops.ports.llm.provider import LLMPort


class _ConcreteLLM(LLMPort):
    """Minimal concrete implementation for behavioral tests."""

    def __init__(self):
        self.last_chat_kwargs: dict[str, Any] = {}

    async def generate(self, request: LLMRequest) -> LLMResponse:
        return LLMResponse(text="ok", model="test")

    async def chat(
        self,
        messages: list[ChatMessage],
        model: str | None = None,
        max_tokens: int | None = None,
        temperature: float | None = None,
        timeout_seconds: float | None = None,
    ) -> ChatMessage:
        self.last_chat_kwargs = {
            "model": model,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "timeout_seconds": timeout_seconds,
        }
        return ChatMessage(role="assistant", content="ok")

    async def chat_stream(
        self,
        messages: list[ChatMessage],
        model: str | None = None,
        max_tokens: int | None = None,
        temperature: float | None = None,
        timeout_seconds: float | None = None,
    ) -> AsyncIterator[str]:
        self.last_chat_kwargs = {
            "model": model,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "timeout_seconds": timeout_seconds,
        }
        for chunk in ["hel", "lo ", "world"]:
            yield chunk

    def list_models(self) -> list[str]:
        return []

    async def refresh_models(self) -> list[str]:
        return []

    async def health(self) -> dict[str, Any]:
        return {"healthy": True}


class TestLLMPort:
    """Tests for LLMPort interface."""

    def test_cannot_instantiate_directly(self):
        """LLMPort is abstract and cannot be instantiated."""
        with pytest.raises(TypeError):
            LLMPort()  # type: ignore

    def test_concrete_subclass_satisfies_contract(self):
        """A concrete subclass implementing all methods is usable."""
        llm = _ConcreteLLM()
        assert llm.list_models() == []
        assert llm.default_model == "unknown"

    async def test_generate_returns_llm_response(self):
        """generate() returns an LLMResponse with text and model."""
        llm = _ConcreteLLM()
        result = await llm.generate(LLMRequest(prompt="hi"))
        assert isinstance(result, LLMResponse)
        assert result.text == "ok"

    async def test_chat_returns_chat_message(self):
        """chat() returns a ChatMessage from the assistant role."""
        llm = _ConcreteLLM()
        result = await llm.chat([ChatMessage(role="user", content="hi")])
        assert result.role == "assistant"
        assert result.content == "ok"

    async def test_chat_stream_yields_text_chunks(self):
        """chat_stream() yields string chunks."""
        llm = _ConcreteLLM()
        chunks = [c async for c in llm.chat_stream([ChatMessage(role="user", content="hi")])]
        assert chunks == ["hel", "lo ", "world"]

    async def test_health_returns_dict(self):
        """health() returns a dict with healthy key."""
        llm = _ConcreteLLM()
        result = await llm.health()
        assert result == {"healthy": True}


class TestLLMPortChatParams:
    """Behavioral tests: concrete implementations accept new chat() params."""

    async def test_chat_accepts_all_optional_params(self):
        llm = _ConcreteLLM()
        messages = [ChatMessage(role="user", content="hi")]
        result = await llm.chat(
            messages,
            model="test-model",
            max_tokens=1000,
            temperature=0.5,
            timeout_seconds=120.0,
        )
        assert result.content == "ok"
        assert llm.last_chat_kwargs == {
            "model": "test-model",
            "max_tokens": 1000,
            "temperature": 0.5,
            "timeout_seconds": 120.0,
        }

    async def test_chat_defaults_to_none(self):
        llm = _ConcreteLLM()
        messages = [ChatMessage(role="user", content="hi")]
        await llm.chat(messages)
        assert llm.last_chat_kwargs == {
            "model": None,
            "max_tokens": None,
            "temperature": None,
            "timeout_seconds": None,
        }


class TestLLMRouterForwarding:
    """Verify LLMRouter forwards new chat() params to the underlying provider."""

    async def test_router_forwards_all_chat_params(self):
        from squadops.llm.router import LLMRouter

        provider = _ConcreteLLM()
        router = LLMRouter(provider)
        messages = [ChatMessage(role="user", content="hi")]

        result = await router.chat(
            messages,
            model="test-model",
            max_tokens=4000,
            temperature=0.8,
            timeout_seconds=120.0,
        )
        assert result.content == "ok"
        assert provider.last_chat_kwargs == {
            "model": "test-model",
            "max_tokens": 4000,
            "temperature": 0.8,
            "timeout_seconds": 120.0,
        }

    async def test_router_forwards_none_defaults(self):
        from squadops.llm.router import LLMRouter

        provider = _ConcreteLLM()
        router = LLMRouter(provider)
        messages = [ChatMessage(role="user", content="hi")]

        await router.chat(messages)
        assert provider.last_chat_kwargs == {
            "model": None,
            "max_tokens": None,
            "temperature": None,
            "timeout_seconds": None,
        }
