"""Unit tests for LLM port interfaces."""
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

    def test_has_generate_method(self):
        assert hasattr(LLMPort, "generate")

    def test_has_chat_method(self):
        assert hasattr(LLMPort, "chat")

    def test_has_list_models_method(self):
        assert hasattr(LLMPort, "list_models")

    def test_has_refresh_models_method(self):
        assert hasattr(LLMPort, "refresh_models")

    def test_has_health_method(self):
        assert hasattr(LLMPort, "health")

    def test_default_model_property(self):
        """default_model returns 'unknown' by default."""
        llm = _ConcreteLLM()
        assert llm.default_model == "unknown"


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
