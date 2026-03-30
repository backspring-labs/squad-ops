"""Ollama LLM adapter.

Production adapter for local Ollama LLM server.
Part of SIP-0.8.7 Infrastructure Ports Migration.
"""

from __future__ import annotations

import json
import logging
from collections.abc import AsyncIterator
from typing import Any

import httpx

from squadops.llm.exceptions import (
    LLMConnectionError,
    LLMModelNotFoundError,
    LLMTimeoutError,
)
from squadops.llm.models import ChatMessage, LLMRequest, LLMResponse
from squadops.ports.llm.provider import LLMPort

logger = logging.getLogger(__name__)


def _compute_tokens_per_second(data: dict[str, Any]) -> float | None:
    """Compute tokens/second from Ollama response timing fields.

    Ollama returns eval_count (completion tokens) and eval_duration (nanoseconds).
    """
    eval_count = data.get("eval_count")
    eval_duration = data.get("eval_duration")
    if eval_count and eval_duration and eval_duration > 0:
        return round(eval_count / (eval_duration / 1e9), 2)
    return None


class OllamaAdapter(LLMPort):
    """Ollama LLM adapter for local inference.

    Connects to a local or remote Ollama server for text generation.
    Supports both generate and chat endpoints.
    """

    def __init__(
        self,
        base_url: str = "http://localhost:11434",
        default_model: str = "llama3.2",
        timeout_seconds: float = 180.0,
    ):
        """Initialize Ollama adapter.

        Args:
            base_url: Ollama server URL
            default_model: Default model to use if not specified in request
            timeout_seconds: Default request timeout
        """
        self._base_url = base_url.rstrip("/")
        self._default_model = default_model
        self._timeout = timeout_seconds
        self._models_cache: list[str] = []
        self._client: httpx.AsyncClient | None = None

    @property
    def default_model(self) -> str:
        """Return the default model name."""
        return self._default_model

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create async HTTP client."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self._base_url,
                timeout=httpx.Timeout(self._timeout),
            )
        return self._client

    async def generate(self, request: LLMRequest) -> LLMResponse:
        """Generate text from a prompt.

        Args:
            request: The LLM request specification

        Returns:
            LLM response with generated text
        """
        client = await self._get_client()
        model = request.model or self._default_model
        timeout = request.timeout_seconds or self._timeout

        payload: dict[str, Any] = {
            "model": model,
            "prompt": request.prompt,
            "stream": False,
            "options": {
                "temperature": request.temperature,
                "num_predict": request.max_tokens,
            },
        }

        if request.format == "json":
            payload["format"] = "json"

        try:
            response = await client.post(
                "/api/generate",
                json=payload,
                timeout=timeout,
            )
            response.raise_for_status()
            data = response.json()

            tps = _compute_tokens_per_second(data)
            prompt_tok = data.get("prompt_eval_count")
            completion_tok = data.get("eval_count")
            total_tok = (
                (prompt_tok or 0) + (completion_tok or 0) if prompt_tok or completion_tok else None
            )

            logger.info(
                "LLM generate completed: model=%s, prompt_tokens=%s, "
                "completion_tokens=%s, t/s=%.1f",
                model,
                prompt_tok,
                completion_tok,
                tps or 0.0,
            )

            return LLMResponse(
                text=data.get("response", ""),
                model=data.get("model", model),
                prompt_tokens=prompt_tok,
                completion_tokens=completion_tok,
                total_tokens=total_tok,
                tokens_per_second=tps,
            )
        except httpx.TimeoutException as e:
            raise LLMTimeoutError(f"Ollama request timed out after {timeout}s") from e
        except httpx.ConnectError as e:
            raise LLMConnectionError(f"Failed to connect to Ollama at {self._base_url}") from e
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                raise LLMModelNotFoundError(f"Model '{model}' not found") from e
            raise LLMConnectionError(f"Ollama request failed: {e}") from e

    def _build_chat_payload(
        self,
        messages: list[ChatMessage],
        model: str,
        max_tokens: int | None,
        temperature: float | None,
        *,
        stream: bool = False,
    ) -> dict[str, Any]:
        """Build the Ollama /api/chat request payload."""
        payload: dict[str, Any] = {
            "model": model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "stream": stream,
        }

        options: dict[str, Any] = {}
        if max_tokens is not None:
            options["num_predict"] = max_tokens
        if temperature is not None:
            options["temperature"] = temperature
        if options:
            payload["options"] = options

        return payload

    async def chat(
        self,
        messages: list[ChatMessage],
        model: str | None = None,
        max_tokens: int | None = None,
        temperature: float | None = None,
        timeout_seconds: float | None = None,
    ) -> ChatMessage:
        """Chat with the LLM using message history.

        Args:
            messages: List of chat messages
            model: Optional model override
            max_tokens: Maximum completion tokens (maps to num_predict)
            temperature: Sampling temperature
            timeout_seconds: Request timeout override

        Returns:
            Assistant's response message
        """
        client = await self._get_client()
        resolved_model = model or self._default_model
        timeout = timeout_seconds or self._timeout
        payload = self._build_chat_payload(
            messages,
            resolved_model,
            max_tokens,
            temperature,
            stream=False,
        )

        try:
            response = await client.post(
                "/api/chat",
                json=payload,
                timeout=timeout,
            )
            response.raise_for_status()
            data = response.json()

            message_data = data.get("message", {})
            tps = _compute_tokens_per_second(data)
            prompt_tok = data.get("prompt_eval_count")
            completion_tok = data.get("eval_count")
            total_tok = (
                (prompt_tok or 0) + (completion_tok or 0) if prompt_tok or completion_tok else None
            )

            logger.info(
                "LLM chat completed: model=%s, prompt_tokens=%s, completion_tokens=%s, t/s=%.1f",
                resolved_model,
                prompt_tok,
                completion_tok,
                tps or 0.0,
            )

            return ChatMessage(
                role=message_data.get("role", "assistant"),
                content=message_data.get("content", ""),
                prompt_tokens=prompt_tok,
                completion_tokens=completion_tok,
                total_tokens=total_tok,
                tokens_per_second=tps,
            )
        except httpx.TimeoutException as e:
            raise LLMTimeoutError(f"Ollama chat timed out after {timeout}s") from e
        except httpx.ConnectError as e:
            raise LLMConnectionError(f"Failed to connect to Ollama at {self._base_url}") from e
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                raise LLMModelNotFoundError(f"Model '{resolved_model}' not found") from e
            raise LLMConnectionError(f"Ollama chat failed: {e}") from e

    async def chat_stream(
        self,
        messages: list[ChatMessage],
        model: str | None = None,
        max_tokens: int | None = None,
        temperature: float | None = None,
        timeout_seconds: float | None = None,
    ) -> AsyncIterator[str]:
        """Stream chat response as plain text chunks.

        Uses Ollama /api/chat with stream=true. Returns newline-delimited
        JSON where each line has message.content with the next text chunk.
        """
        client = await self._get_client()
        resolved_model = model or self._default_model
        timeout = timeout_seconds or self._timeout
        payload = self._build_chat_payload(
            messages,
            resolved_model,
            max_tokens,
            temperature,
            stream=True,
        )

        try:
            async with client.stream(
                "POST",
                "/api/chat",
                json=payload,
                timeout=timeout,
            ) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if not line:
                        continue
                    try:
                        chunk = json.loads(line)
                    except json.JSONDecodeError:
                        logger.debug("Skipping malformed Ollama stream line")
                        continue
                    content = chunk.get("message", {}).get("content", "")
                    if content:
                        yield content
        except httpx.TimeoutException as e:
            raise LLMTimeoutError(f"Ollama chat_stream timed out after {timeout}s") from e
        except httpx.ConnectError as e:
            raise LLMConnectionError(f"Failed to connect to Ollama at {self._base_url}") from e
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                raise LLMModelNotFoundError(f"Model '{resolved_model}' not found") from e
            raise LLMConnectionError(f"Ollama chat_stream failed: {e}") from e

    def list_models(self) -> list[str]:
        """List available models (sync, returns cached list).

        Returns:
            Cached list of model names (may be empty)
        """
        return self._models_cache.copy()

    async def refresh_models(self) -> list[str]:
        """Refresh and return available models.

        Returns:
            Updated list of available model names
        """
        client = await self._get_client()

        try:
            response = await client.get("/api/tags", timeout=10.0)
            response.raise_for_status()
            data = response.json()

            models = [m.get("name", "") for m in data.get("models", [])]
            self._models_cache = [m for m in models if m]
            return self._models_cache.copy()
        except Exception:
            # Return cached list on failure
            return self._models_cache.copy()

    async def health(self) -> dict[str, Any]:
        """Check Ollama server health.

        Returns:
            Health status dictionary
        """
        try:
            client = await self._get_client()
            response = await client.get("/api/tags", timeout=5.0)
            return {
                "healthy": response.status_code == 200,
                "base_url": self._base_url,
                "models_available": len(self._models_cache),
            }
        except Exception as e:
            return {
                "healthy": False,
                "base_url": self._base_url,
                "error": str(e),
            }

    async def pull_model(self, model_name: str) -> dict[str, Any]:
        """Pull a model from the Ollama registry.

        Args:
            model_name: Model name to pull (e.g. "qwen2.5:7b")

        Returns:
            Ollama response dict with pull status
        """
        client = await self._get_client()
        try:
            response = await client.post(
                "/api/pull",
                json={"name": model_name, "stream": False},
                timeout=600.0,
            )
            response.raise_for_status()
            return response.json()
        except httpx.TimeoutException as e:
            raise LLMTimeoutError(f"Model pull timed out for '{model_name}'") from e
        except httpx.ConnectError as e:
            raise LLMConnectionError(f"Failed to connect to Ollama at {self._base_url}") from e
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                raise LLMModelNotFoundError(f"Model '{model_name}' not found in registry") from e
            raise LLMConnectionError(f"Ollama pull failed: {e}") from e

    async def delete_model(self, model_name: str) -> dict[str, Any]:
        """Delete a locally pulled model.

        Args:
            model_name: Model name to delete

        Returns:
            Empty dict on success
        """
        client = await self._get_client()
        try:
            response = await client.request(
                "DELETE",
                "/api/delete",
                json={"name": model_name},
            )
            response.raise_for_status()
            return {}
        except httpx.ConnectError as e:
            raise LLMConnectionError(f"Failed to connect to Ollama at {self._base_url}") from e
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                raise LLMModelNotFoundError(f"Model '{model_name}' not found locally") from e
            raise LLMConnectionError(f"Ollama delete failed: {e}") from e

    async def list_pulled_models(self) -> list[dict[str, Any]]:
        """List pulled models with full metadata (size, modified_at).

        Returns:
            List of model dicts from Ollama /api/tags
        """
        client = await self._get_client()
        try:
            response = await client.get("/api/tags", timeout=10.0)
            response.raise_for_status()
            data = response.json()
            return data.get("models", [])
        except httpx.ConnectError as e:
            raise LLMConnectionError(f"Failed to connect to Ollama at {self._base_url}") from e

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None
