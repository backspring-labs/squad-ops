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
from squadops.llm.models import ChatMessage, LLMRequest, LLMResponse, ModelInfo, ReasoningLevel
from squadops.ports.llm.provider import LLMCapability, LLMPort

logger = logging.getLogger(__name__)

# #158: default timeout for the model-list/health probe (GET /api/tags). Separate
# from the main request timeout; tunable via the constructor for slow networks.
_DEFAULT_MODEL_LIST_TIMEOUT = 10.0


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
        model_list_timeout_seconds: float = _DEFAULT_MODEL_LIST_TIMEOUT,
    ):
        """Initialize Ollama adapter.

        Args:
            base_url: Ollama server URL
            default_model: Default model to use if not specified in request
            timeout_seconds: Default request timeout
            model_list_timeout_seconds: Timeout for the model-list/health probe
                (GET /api/tags), separate from the main request timeout (#158).
        """
        self._base_url = base_url.rstrip("/")
        self._default_model = default_model
        self._timeout = timeout_seconds
        self._model_list_timeout = model_list_timeout_seconds
        self._models_cache: list[str] = []
        self._client: httpx.AsyncClient | None = None

    @property
    def default_model(self) -> str:
        """Return the default model name."""
        return self._default_model

    def capabilities(self) -> dict[str, bool]:
        """Declare what this adapter actually does (#572's rule, see the port).

        ``thinking_tokens`` is False because Ollama reports no separate thinking
        token count — ``eval_count`` is the total, and the response carries no
        thinking count field (measured 2026-08-31 on qwen3.8:27b). It is a
        vendor limitation, not an adapter choice, and not a statement about the
        models: qwen3-family models emit ``message.thinking``, and this adapter
        does read it — into ``reasoning_text``, non-streaming since #410 and
        streaming since #1194. So the thinking channel is visible; what cannot
        be produced is a token split, and declaring True would tell a caller it
        could split them. #1195 tracks what that costs the #924 diagnostic.

        ``reasoning_control`` is True: a level maps onto the ``think`` flag
        (#927), so the channel can at least be switched off where the output is
        a transcription — the 13.9× token difference #924 measured.
        """
        return {
            LLMCapability.MODEL_LISTING: True,
            LLMCapability.MODEL_MANAGEMENT: True,
            LLMCapability.STREAMING_USAGE: True,
            LLMCapability.THINKING_TOKENS: False,
            LLMCapability.REASONING_CONTROL: True,
        }

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
                **({} if request.top_p is None else {"top_p": request.top_p}),
                "num_predict": request.max_tokens,
            },
        }

        if request.format == "json":
            payload["format"] = "json"
        if request.reasoning is not None:
            payload["think"] = request.reasoning != ReasoningLevel.NONE

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
        top_p: float | None = None,
        reasoning: str | None = None,
        *,
        stream: bool = False,
    ) -> dict[str, Any]:
        """Build the Ollama /api/chat request payload.

        ``reasoning`` maps onto Ollama's ``think`` flag — the only dial the
        dialect has, so the port's graded levels collapse to on/off here:
        ``none`` → ``think: false``, any other level → ``think: true``. ``None``
        sends no ``think`` at all and the payload is byte-identical to the
        pre-#927 one; the caller is expected not to pass a level for a model
        with no reasoning channel, since Ollama rejects ``think: true`` for those (400, "does not support
        thinking" — measured 2026-08-28 on 0.32.14).
        """
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
        # #901: the pair. Ollama takes `top_p` in `options` exactly as it takes
        # `temperature`, so this is the same arm. `top_k`/`min_p` are deliberately NOT
        # added: Ollama would accept them but the OpenAI-shaped adapters have no
        # standard field for either, so a profile setting one would be honoured on one
        # provider and silently ignored on two — the defect this fixes, reintroduced.
        if top_p is not None:
            options["top_p"] = top_p
        if options:
            payload["options"] = options
        if reasoning is not None:
            payload["think"] = reasoning != ReasoningLevel.NONE

        return payload

    async def chat(
        self,
        messages: list[ChatMessage],
        model: str | None = None,
        max_tokens: int | None = None,
        temperature: float | None = None,
        top_p: float | None = None,
        timeout_seconds: float | None = None,
        reasoning: str | None = None,
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
            top_p,
            reasoning,
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
                # #410: qwen3-family models return thinking here, separate from content.
                # It was read past and dropped, so the tokens it cost were paid for,
                # counted in eval_count, and then invisible to every consumer. `.get`
                # with no default keeps None (channel absent) distinct from "" (present
                # and empty), which is the difference between "did not think" and
                # "thought and said nothing".
                reasoning_text=message_data.get("thinking"),
            )
        except httpx.TimeoutException as e:
            raise LLMTimeoutError(f"Ollama chat timed out after {timeout}s") from e
        except httpx.ConnectError as e:
            raise LLMConnectionError(f"Failed to connect to Ollama at {self._base_url}") from e
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                raise LLMModelNotFoundError(f"Model '{resolved_model}' not found") from e
            raise LLMConnectionError(f"Ollama chat failed: {e}") from e

    async def chat_stream_with_usage(
        self,
        messages: list[ChatMessage],
        model: str | None = None,
        max_tokens: int | None = None,
        temperature: float | None = None,
        top_p: float | None = None,
        timeout_seconds: float | None = None,
        reasoning: str | None = None,
    ) -> ChatMessage:
        """Stream chat internally for connection liveness, return complete ChatMessage with usage.

        Uses streaming transport to keep the connection alive during long-running
        inference, but returns only the final assembled response. Captures token
        usage metadata from Ollama's final `done: true` chunk.
        """
        client = await self._get_client()
        resolved_model = model or self._default_model
        timeout = timeout_seconds or self._timeout
        payload = self._build_chat_payload(
            messages,
            resolved_model,
            max_tokens,
            temperature,
            top_p,
            reasoning,
            stream=True,
        )

        try:
            chunks: list[str] = []
            reasoning_chunks: list[str] = []
            saw_reasoning = False
            usage_data: dict[str, Any] = {}

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

                    # The final ``done`` chunk carries the usage metadata and may
                    # carry a last message payload too, so it is read for both rather
                    # than through a branch that duplicates the message handling.
                    if chunk.get("done"):
                        usage_data = chunk

                    message = chunk.get("message") or {}
                    content = message.get("content", "")
                    if content:
                        chunks.append(content)
                    # #1194: the thinking channel arrives as its own chunks, interleaved
                    # with the content ones. Reading only ``content`` discarded it
                    # entirely: on the 2026-08-31 shakeouts 23 of 27 generations asked
                    # the model to think, Ollama returned the text, and every one
                    # recorded ``reasoning_text: null``. #410 fixed this on ``chat()``
                    # (non-streaming); every cycle handler calls this method instead.
                    # ``is not None`` keeps "channel absent" distinct from "channel
                    # present and empty" — the distinction ``chat()`` preserves with a
                    # defaultless ``.get`` and the reason this is not ``if thinking:``.
                    thinking = message.get("thinking")
                    if thinking is not None:
                        saw_reasoning = True
                        reasoning_chunks.append(thinking)

            tps = _compute_tokens_per_second(usage_data)
            prompt_tok = usage_data.get("prompt_eval_count")
            completion_tok = usage_data.get("eval_count")
            total_tok = (
                (prompt_tok or 0) + (completion_tok or 0) if prompt_tok or completion_tok else None
            )

            logger.info(
                "LLM chat_stream_with_usage completed: model=%s, prompt_tokens=%s, "
                "completion_tokens=%s, t/s=%.1f",
                resolved_model,
                prompt_tok,
                completion_tok,
                tps or 0.0,
            )

            return ChatMessage(
                role="assistant",
                content="".join(chunks),
                prompt_tokens=prompt_tok,
                completion_tokens=completion_tok,
                total_tokens=total_tok,
                tokens_per_second=tps,
                # ``reasoning_tokens`` stays unset: Ollama reports no separate thinking
                # count (``eval_count`` is the total), which is what ``capabilities()``
                # declares with ``THINKING_TOKENS: False``. See #1195.
                reasoning_text="".join(reasoning_chunks) if saw_reasoning else None,
            )
        except httpx.TimeoutException as e:
            raise LLMTimeoutError(
                f"Ollama chat_stream_with_usage timed out after {timeout}s"
            ) from e
        except httpx.ConnectError as e:
            raise LLMConnectionError(f"Failed to connect to Ollama at {self._base_url}") from e
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                raise LLMModelNotFoundError(f"Model '{resolved_model}' not found") from e
            raise LLMConnectionError(f"Ollama chat_stream_with_usage failed: {e}") from e

    async def chat_stream(
        self,
        messages: list[ChatMessage],
        model: str | None = None,
        max_tokens: int | None = None,
        temperature: float | None = None,
        top_p: float | None = None,
        timeout_seconds: float | None = None,
        reasoning: str | None = None,
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
            top_p,
            reasoning,
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
            response = await client.get("/api/tags", timeout=self._model_list_timeout)
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
            response = await client.get("/api/tags", timeout=self._model_list_timeout)
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

    async def pull_model(self, model_name: str) -> None:
        """Pull a model from the Ollama registry.

        Returns None per the port contract: a provider response body handed back
        through the port would make every caller Ollama-shaped (#313).

        Args:
            model_name: Model name to pull (e.g. "qwen2.5:7b")
        """
        client = await self._get_client()
        try:
            response = await client.post(
                "/api/pull",
                json={"name": model_name, "stream": False},
                timeout=600.0,
            )
            response.raise_for_status()
        except httpx.TimeoutException as e:
            raise LLMTimeoutError(f"Model pull timed out for '{model_name}'") from e
        except httpx.ConnectError as e:
            raise LLMConnectionError(f"Failed to connect to Ollama at {self._base_url}") from e
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                raise LLMModelNotFoundError(f"Model '{model_name}' not found in registry") from e
            raise LLMConnectionError(f"Ollama pull failed: {e}") from e

    async def delete_model(self, model_name: str) -> None:
        """Delete a locally pulled model.

        Args:
            model_name: Model name to delete
        """
        client = await self._get_client()
        try:
            response = await client.request(
                "DELETE",
                "/api/delete",
                json={"name": model_name},
            )
            response.raise_for_status()
        except httpx.ConnectError as e:
            raise LLMConnectionError(f"Failed to connect to Ollama at {self._base_url}") from e
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                raise LLMModelNotFoundError(f"Model '{model_name}' not found locally") from e
            raise LLMConnectionError(f"Ollama delete failed: {e}") from e

    async def list_available_models(self) -> list[ModelInfo]:
        """List pulled models with metadata (#313).

        Replaces the former ``list_pulled_models``, whose raw ``/api/tags`` dicts
        were the coupling: every caller had to know Ollama's payload keys, so
        reaching for model metadata made the caller Ollama-specific by
        construction. ``ModelInfo`` is the port's vocabulary; translating to it
        is this adapter's job.
        """
        client = await self._get_client()
        try:
            response = await client.get("/api/tags", timeout=self._model_list_timeout)
            response.raise_for_status()
            data = response.json()
        except httpx.ConnectError as e:
            raise LLMConnectionError(f"Failed to connect to Ollama at {self._base_url}") from e

        return [
            ModelInfo(name=name, size_bytes=m.get("size"), modified_at=m.get("modified_at"))
            for m in data.get("models", [])
            if (name := m.get("name"))
        ]

    async def list_pulled_models(self) -> list[dict[str, Any]]:
        """DEPRECATED (#313) — use :meth:`list_available_models`.

        Kept solely for ``api/routes/cycles/cycles.py``'s model-availability
        preflight, not migrated here because that file is under active edit by
        the 1.6 line. **Delete this with that migration.** It exists so the
        removal cannot land as an AttributeError that the preflight's broad
        ``except Exception`` swallows into a silent warn-and-allow — a false
        green rather than a visible break.
        """
        return [
            {"name": m.name, "size": m.size_bytes, "modified_at": m.modified_at}
            for m in await self.list_available_models()
        ]

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None
