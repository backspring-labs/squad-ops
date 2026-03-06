"""Unit tests for Ollama adapter."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from adapters.llm.ollama import OllamaAdapter
from squadops.llm.exceptions import LLMTimeoutError
from squadops.llm.models import ChatMessage, LLMRequest


class TestOllamaAdapter:
    """Tests for OllamaAdapter."""

    def test_init_defaults(self):
        adapter = OllamaAdapter()
        assert adapter._base_url == "http://localhost:11434"
        assert adapter._default_model == "llama3.2"
        assert adapter._timeout == 180.0
        assert adapter._models_cache == []

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

    async def test_chat_with_max_tokens(self):
        """chat() forwards max_tokens as num_predict in options."""
        adapter = OllamaAdapter()

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "message": {"role": "assistant", "content": "response"},
        }

        with patch.object(adapter, "_get_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_client.post.return_value = mock_response
            mock_get_client.return_value = mock_client

            messages = [ChatMessage(role="user", content="Hello")]
            await adapter.chat(messages, max_tokens=8000)

            call_kwargs = mock_client.post.call_args
            payload = call_kwargs.kwargs["json"]
            assert payload["options"]["num_predict"] == 8000

    async def test_chat_with_temperature(self):
        """chat() forwards temperature in options."""
        adapter = OllamaAdapter()

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "message": {"role": "assistant", "content": "response"},
        }

        with patch.object(adapter, "_get_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_client.post.return_value = mock_response
            mock_get_client.return_value = mock_client

            messages = [ChatMessage(role="user", content="Hello")]
            await adapter.chat(messages, temperature=0.7)

            call_kwargs = mock_client.post.call_args
            payload = call_kwargs.kwargs["json"]
            assert payload["options"]["temperature"] == 0.7

    async def test_chat_with_timeout_seconds(self):
        """chat() uses timeout_seconds for the request timeout."""
        adapter = OllamaAdapter(timeout_seconds=60.0)

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "message": {"role": "assistant", "content": "response"},
        }

        with patch.object(adapter, "_get_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_client.post.return_value = mock_response
            mock_get_client.return_value = mock_client

            messages = [ChatMessage(role="user", content="Hello")]
            await adapter.chat(messages, timeout_seconds=300.0)

            call_kwargs = mock_client.post.call_args
            assert call_kwargs.kwargs["timeout"] == 300.0

    async def test_chat_without_options_omits_options_key(self):
        """chat() without max_tokens/temperature omits options from payload."""
        adapter = OllamaAdapter()

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "message": {"role": "assistant", "content": "response"},
        }

        with patch.object(adapter, "_get_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_client.post.return_value = mock_response
            mock_get_client.return_value = mock_client

            messages = [ChatMessage(role="user", content="Hello")]
            await adapter.chat(messages)

            call_kwargs = mock_client.post.call_args
            payload = call_kwargs.kwargs["json"]
            assert "options" not in payload

    async def test_chat_timeout_uses_default_when_not_provided(self):
        """chat() uses self._timeout when timeout_seconds is None."""
        adapter = OllamaAdapter(timeout_seconds=42.0)

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "message": {"role": "assistant", "content": "response"},
        }

        with patch.object(adapter, "_get_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_client.post.return_value = mock_response
            mock_get_client.return_value = mock_client

            messages = [ChatMessage(role="user", content="Hello")]
            await adapter.chat(messages)

            call_kwargs = mock_client.post.call_args
            assert call_kwargs.kwargs["timeout"] == 42.0

    async def test_chat_timeout_error_reports_effective_timeout(self):
        """Timeout error message reflects the effective timeout, not hardcoded."""
        import httpx

        adapter = OllamaAdapter(timeout_seconds=60.0)

        with patch.object(adapter, "_get_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_client.post.side_effect = httpx.TimeoutException("timeout")
            mock_get_client.return_value = mock_client

            messages = [ChatMessage(role="user", content="Hello")]
            with pytest.raises(LLMTimeoutError, match="300"):
                await adapter.chat(messages, timeout_seconds=300.0)

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
