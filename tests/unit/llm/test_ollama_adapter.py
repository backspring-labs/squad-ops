"""Unit tests for Ollama adapter."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from adapters.llm.ollama import OllamaAdapter
from squadops.llm.exceptions import LLMConnectionError, LLMTimeoutError
from squadops.llm.models import ChatMessage, LLMRequest


class TestOllamaAdapter:
    """Tests for OllamaAdapter."""

    def test_init_defaults(self):
        adapter = OllamaAdapter()
        assert adapter._base_url == "http://localhost:11434"
        assert adapter._default_model == "llama3.2"
        assert adapter._timeout == 180.0
        assert adapter._models_cache == []

    def test_init_custom(self):
        adapter = OllamaAdapter(
            base_url="http://custom:8080",
            default_model="mistral",
            timeout_seconds=60.0,
        )
        assert adapter._base_url == "http://custom:8080"
        assert adapter._default_model == "mistral"
        assert adapter._timeout == 60.0

    def test_list_models_returns_cache(self):
        adapter = OllamaAdapter()
        adapter._models_cache = ["llama3.2", "mistral"]
        models = adapter.list_models()
        assert models == ["llama3.2", "mistral"]
        # Ensure it's a copy
        models.append("new")
        assert adapter._models_cache == ["llama3.2", "mistral"]


@pytest.mark.asyncio
class TestOllamaAdapterAsync:
    """Async tests for OllamaAdapter."""

    async def test_generate_success(self):
        adapter = OllamaAdapter()

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "response": "Hello!",
            "model": "llama3.2",
            "prompt_eval_count": 10,
            "eval_count": 5,
        }

        with patch.object(adapter, "_get_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_client.post.return_value = mock_response
            mock_get_client.return_value = mock_client

            request = LLMRequest(prompt="Say hello")
            response = await adapter.generate(request)

            assert response.text == "Hello!"
            assert response.model == "llama3.2"
            assert response.prompt_tokens == 10
            assert response.completion_tokens == 5
            assert response.total_tokens == 15

    async def test_chat_success(self):
        adapter = OllamaAdapter()

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "message": {
                "role": "assistant",
                "content": "Hello! How can I help?",
            }
        }

        with patch.object(adapter, "_get_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_client.post.return_value = mock_response
            mock_get_client.return_value = mock_client

            messages = [ChatMessage(role="user", content="Hello")]
            response = await adapter.chat(messages)

            assert response.role == "assistant"
            assert response.content == "Hello! How can I help?"

    async def test_refresh_models_success(self):
        adapter = OllamaAdapter()

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "models": [
                {"name": "llama3.2"},
                {"name": "mistral"},
            ]
        }

        with patch.object(adapter, "_get_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_response
            mock_get_client.return_value = mock_client

            models = await adapter.refresh_models()

            assert models == ["llama3.2", "mistral"]
            assert adapter._models_cache == ["llama3.2", "mistral"]

    async def test_health_success(self):
        adapter = OllamaAdapter()
        adapter._models_cache = ["llama3.2"]

        mock_response = MagicMock()
        mock_response.status_code = 200

        with patch.object(adapter, "_get_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_response
            mock_get_client.return_value = mock_client

            health = await adapter.health()

            assert health["healthy"] is True
            assert health["models_available"] == 1
