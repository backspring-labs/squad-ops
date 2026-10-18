"""Unit tests for Ollama adapter."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from adapters.llm.ollama import OllamaAdapter
from squadops.llm.exceptions import LLMTimeoutError
from squadops.llm.models import ChatMessage, LLMRequest, ReasoningLevel


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

    @pytest.mark.parametrize(
        ("reasoning", "think"),
        [
            (ReasoningLevel.NONE, False),
            (ReasoningLevel.LOW, True),
            (ReasoningLevel.MEDIUM, True),
            (ReasoningLevel.HIGH, True),
        ],
    )
    async def test_chat_reasoning_maps_to_think(self, reasoning, think):
        """#927: the port's level reaches Ollama as its ``think`` flag —
        ``none`` off, every graded level on (the only dial the dialect has).
        The bug: a level accepted at the port and never sent, so the 5,727-token
        fill #924 measured keeps paying for a channel nobody reads."""
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

            await adapter.chat([ChatMessage(role="user", content="Hello")], reasoning=reasoning)

            payload = mock_client.post.call_args.kwargs["json"]
            assert payload["think"] is think

    async def test_chat_without_reasoning_sends_no_think(self):
        """No level ⇒ no ``think`` key: the payload is the pre-#927 one, so a
        model with no reasoning channel (Ollama 400s on ``think: true`` for those)
        and every unchanged caller keep working."""
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

            await adapter.chat([ChatMessage(role="user", content="Hello")], max_tokens=10)

            assert "think" not in mock_client.post.call_args.kwargs["json"]

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


class TestTheServedContextIsTheRegistrys:
    """#2427: the adapter never sent ``num_ctx``, so Ollama served its own default (4,096 tokens on
    the MacBook's 0.12.3, which logged 28 ``truncating input prompt … limit=4096``) while the
    registry, and every guard reading it, budgeted ``qwen2.5:7b`` at 32,768."""

    @staticmethod
    def _adapter_recording(sent: list[dict]) -> OllamaAdapter:
        import json

        import httpx

        def ollama(request: httpx.Request) -> httpx.Response:
            body = json.loads(request.content)
            sent.append(body)
            if request.url.path == "/api/generate":
                return httpx.Response(200, json={"response": "ok", "done": True})
            if body.get("stream"):
                done = {"message": {"role": "assistant", "content": ""}, "done": True}
                part = {"message": {"role": "assistant", "content": "ok"}, "done": False}
                return httpx.Response(200, text=f"{json.dumps(part)}\n{json.dumps(done)}\n")
            return httpx.Response(200, json={"message": {"role": "assistant", "content": "ok"}})

        adapter = OllamaAdapter()
        adapter._client = httpx.AsyncClient(
            base_url="http://ollama.test", transport=httpx.MockTransport(ollama)
        )
        return adapter

    @pytest.mark.parametrize("entry", ["generate", "chat", "chat_stream_with_usage"])
    @pytest.mark.parametrize(
        ("model", "num_ctx"),
        [("qwen2.5:7b", 32_768), ("qwen2.5:3b-instruct", 32_768), ("llama3.2", None)],
        ids=["lite", "smoke", "unregistered"],
    )
    async def test_each_request_asks_for_the_context_the_registry_budgets(
        self, entry, model, num_ctx
    ):
        """Entered at each of the adapter's model calls, the cycle handlers' streaming one among
        them (``capabilities/handlers/cycle/base.py``), with the body read as sent. Bugs caught:
        a path that still sends no ``num_ctx``, so a long prompt is cut from the front; and a
        model the registry does not know sent a context nobody budgeted."""
        sent: list[dict] = []
        adapter = self._adapter_recording(sent)
        if entry == "generate":
            await adapter.generate(LLMRequest(prompt="hi", model=model))
        else:
            await getattr(adapter, entry)([ChatMessage(role="user", content="hi")], model=model)

        assert sent[-1].get("options", {}).get("num_ctx") == num_ctx
