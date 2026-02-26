"""Unit tests for LLM domain models."""

import pytest

from squadops.llm.models import ChatMessage, LLMRequest, LLMResponse


class TestLLMRequest:
    """Tests for LLMRequest dataclass."""

    def test_minimal_request(self):
        request = LLMRequest(prompt="Hello")
        assert request.prompt == "Hello"
        assert request.model is None
        assert request.temperature == 0.7
        assert request.max_tokens == 4000
        assert request.format is None
        assert request.timeout_seconds == 180.0

    def test_full_request(self):
        request = LLMRequest(
            prompt="Hello",
            model="llama3.2",
            temperature=0.5,
            max_tokens=1000,
            format="json",
            timeout_seconds=60.0,
        )
        assert request.model == "llama3.2"
        assert request.temperature == 0.5
        assert request.max_tokens == 1000
        assert request.format == "json"
        assert request.timeout_seconds == 60.0

    def test_request_is_frozen(self):
        request = LLMRequest(prompt="Hello")
        with pytest.raises(AttributeError):
            request.prompt = "Modified"  # type: ignore


class TestLLMResponse:
    """Tests for LLMResponse dataclass."""

    def test_minimal_response(self):
        response = LLMResponse(text="Hello", model="llama3.2")
        assert response.text == "Hello"
        assert response.model == "llama3.2"
        assert response.prompt_tokens is None
        assert response.completion_tokens is None
        assert response.total_tokens is None

    def test_full_response(self):
        response = LLMResponse(
            text="Hello",
            model="llama3.2",
            prompt_tokens=10,
            completion_tokens=20,
            total_tokens=30,
        )
        assert response.prompt_tokens == 10
        assert response.completion_tokens == 20
        assert response.total_tokens == 30

    def test_response_is_frozen(self):
        response = LLMResponse(text="Hello", model="llama3.2")
        with pytest.raises(AttributeError):
            response.text = "Modified"  # type: ignore


class TestChatMessage:
    """Tests for ChatMessage dataclass."""

    def test_chat_message(self):
        msg = ChatMessage(role="user", content="Hello")
        assert msg.role == "user"
        assert msg.content == "Hello"

    def test_chat_message_roles(self):
        for role in ["system", "user", "assistant"]:
            msg = ChatMessage(role=role, content="test")
            assert msg.role == role

    def test_chat_message_is_frozen(self):
        msg = ChatMessage(role="user", content="Hello")
        with pytest.raises(AttributeError):
            msg.content = "Modified"  # type: ignore
