"""Unit tests for LLM port interfaces."""
import pytest

from squadops.ports.llm.provider import LLMPort


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
