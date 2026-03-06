"""Unit tests for LLM domain models."""

import pytest

from squadops.llm.models import ChatMessage, LLMRequest, LLMResponse


class TestLLMRequest:
    """Tests for LLMRequest dataclass."""

    def test_request_is_frozen(self):
        request = LLMRequest(prompt="Hello")
        with pytest.raises(AttributeError):
            request.prompt = "Modified"  # type: ignore


class TestLLMResponse:
    """Tests for LLMResponse dataclass."""

    def test_response_is_frozen(self):
        response = LLMResponse(text="Hello", model="llama3.2")
        with pytest.raises(AttributeError):
            response.text = "Modified"  # type: ignore


class TestChatMessage:
    """Tests for ChatMessage dataclass."""

    def test_chat_message_roles(self):
        for role in ["system", "user", "assistant"]:
            msg = ChatMessage(role=role, content="test")
            assert msg.role == role

    def test_chat_message_is_frozen(self):
        msg = ChatMessage(role="user", content="Hello")
        with pytest.raises(AttributeError):
            msg.content = "Modified"  # type: ignore
