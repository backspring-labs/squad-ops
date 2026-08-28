"""Atlas LLM adapter — the DGX Spark inference engine behind ``LLMPort``.

Second OpenAI-shaped adapter, per the Atlas Provider Adapter SIP (SIP-0106) P4 — its
own file rather than a subclass of the vLLM one (§3.5a: one adapter per provider),
because the dialect diverges where it matters and a shared base would need provider
conditionals (#559). Everything below is from the 2026-08-28 session on the Spark
(`avarok/atlas-gb10` serving `Qwen/Qwen3.8-27B-FP8`; #1158 carries the record):

- **Auth is mandatory** once the server is bound off localhost: a bearer token from
  ``--auth-tokens-file``; no or wrong token → 401. The adapter takes ``api_key`` and
  turns a 401 into an error that names the setting, not a generic connection failure.
- **Usage is richer than OpenAI's**: ``completion_tokens_details.reasoning_tokens``
  (thinking accounted separately — ``thinking_tokens: True``), ``time_to_first_token_ms``
  and the engine's own ``response_token/s``. So, unlike the vLLM adapter, tokens/sec is
  **not** derived from wall-clock; the engine's decode rate is reported as-is, with the
  wall-clock derivation only as a fallback when the field is absent.
- **Reasoning is a server-side ladder**: ``reasoning_effort`` with a real ``none``. The
  port's ``none|low|medium`` pass through; ``high`` maps to ``xhigh``, because the
  Qwen3.8 chat template accepts only ``low|medium|xhigh`` and answers ``high`` with a
  400 (measured; ``xhigh`` is the template's top tier). Thinking arrives as a separate
  ``message.reasoning_content`` / ``delta.reasoning_content`` — never inline — and the
  streaming path must not splice those deltas into the text.
- **Streaming**: SSE ``data: {json}`` frames, ``data: [DONE]``; with
  ``stream_options.include_usage`` the usage rides a frame with ``choices: []``.
- **No model management over HTTP** (405/404); weights are ``hf download``ed and fixed
  at ``serve`` (``--no-auto-swap``). ``/v1/models`` entries carry ``max_model_len``.
"""

from __future__ import annotations

import json
import logging
import time
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

_DEFAULT_MODEL_LIST_TIMEOUT = 10.0

#: The port's level → Atlas's ``reasoning_effort``. Verbatim except ``high``, which the
#: served template rejects; ``xhigh`` is its top tier (SIP-0106 §10.2 fact 6).
_REASONING_EFFORT: dict[str, str] = {
    ReasoningLevel.NONE: "none",
    ReasoningLevel.LOW: "low",
    ReasoningLevel.MEDIUM: "medium",
    ReasoningLevel.HIGH: "xhigh",
}


def _usage_from(payload: dict[str, Any]) -> tuple[int | None, int | None, int | None, int | None]:
    """(prompt, completion, total, reasoning) from Atlas's ``usage`` object.

    All-or-nothing on the three OpenAI counts (a partial row is worse than none —
    SIP-0106 §3.5); ``reasoning`` is ``None`` when the details block is absent, never
    zero-filled, so "not reported" stays distinguishable from "did not think".
    """
    usage = payload.get("usage") or {}
    prompt = usage.get("prompt_tokens")
    completion = usage.get("completion_tokens")
    total = usage.get("total_tokens")
    if total is None and (prompt is not None or completion is not None):
        total = (prompt or 0) + (completion or 0)
    reasoning = (usage.get("completion_tokens_details") or {}).get("reasoning_tokens")
    return prompt, completion, total, reasoning


def _tokens_per_second(
    payload: dict[str, Any], completion: int | None, elapsed: float
) -> float | None:
    """The engine's own decode rate when reported; wall-clock only as a fallback.

    ``response_token/s`` is Atlas's measurement of its decode phase. The fallback is
    inclusive of prefill and queueing (the vLLM adapter's number) and is marked as such
    in the log, so the two are never averaged as if they were the same quantity.
    """
    native = (payload.get("usage") or {}).get("response_token/s")
    if isinstance(native, (int, float)) and native > 0:
        return round(float(native), 2)
    if not completion or elapsed <= 0:
        return None
    return round(completion / elapsed, 2)


class AtlasAdapter(LLMPort):
    """Atlas adapter speaking its OpenAI-compatible surface on ``:8888``.

    Provider string ``"atlas"``.
    """

    def __init__(
        self,
        base_url: str = "http://host.docker.internal:8888",
        default_model: str = "",
        timeout_seconds: float = 180.0,
        model_list_timeout_seconds: float = _DEFAULT_MODEL_LIST_TIMEOUT,
        api_key: str | None = None,
    ):
        """
        Args:
            base_url: server root (``http://host:8888``); ``/v1`` is appended by the paths.
            default_model: the HuggingFace id Atlas was started with, verbatim
                (``Qwen/Qwen3.8-27B-FP8``) — it is echoed in every response.
            timeout_seconds: default generation timeout.
            model_list_timeout_seconds: timeout for listing/health, separate from generation.
            api_key: the bearer token. Mandatory on a server bound off localhost; resolved
                config carries it as a ``secret://`` ref the loader resolves before it
                reaches the factory.
        """
        self._base_url = base_url.rstrip("/")
        self._default_model = default_model
        self._timeout = timeout_seconds
        self._model_list_timeout = model_list_timeout_seconds
        self._api_key = api_key
        self._models_cache: list[str] = []
        self._client: httpx.AsyncClient | None = None

    @property
    def default_model(self) -> str:
        return self._default_model

    def capabilities(self) -> dict[str, bool]:
        """Declared from what the live server did on 2026-08-28, not from its docs."""
        return {
            LLMCapability.MODEL_LISTING: True,
            LLMCapability.MODEL_MANAGEMENT: False,  # 405/404 over HTTP; fixed at `serve`
            LLMCapability.STREAMING_USAGE: True,  # usage frame with `choices: []`
            LLMCapability.THINKING_TOKENS: True,  # `completion_tokens_details.reasoning_tokens`
            LLMCapability.REASONING_CONTROL: True,  # `reasoning_effort`, incl. `none`
        }

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            headers = {"Authorization": f"Bearer {self._api_key}"} if self._api_key else {}
            self._client = httpx.AsyncClient(
                base_url=self._base_url, timeout=httpx.Timeout(self._timeout), headers=headers
            )
        return self._client

    def _payload(
        self,
        messages: list[ChatMessage],
        model: str,
        max_tokens: int | None,
        temperature: float | None,
        reasoning: str | None = None,
        *,
        stream: bool = False,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model": model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "stream": stream,
        }
        if max_tokens is not None:
            payload["max_tokens"] = max_tokens
        if temperature is not None:
            payload["temperature"] = temperature
        if reasoning is not None:
            payload["reasoning_effort"] = _REASONING_EFFORT.get(reasoning, reasoning)
        if stream:
            payload["stream_options"] = {"include_usage": True}
        return payload

    def _translate(self, exc: Exception, model: str, operation: str) -> Exception:
        """Map a transport failure onto the port's exception vocabulary.

        Load-bearing (#568): the correction loop classifies failure locus from these.
        A 401 is named for what it is — the bearer token — because the generic
        "connection failed" it would otherwise become sends an operator to the network.
        """
        if isinstance(exc, httpx.TimeoutException):
            return LLMTimeoutError(f"Atlas {operation} timed out after {self._timeout}s")
        if isinstance(exc, httpx.ConnectError):
            return LLMConnectionError(f"Failed to connect to Atlas at {self._base_url}")
        if isinstance(exc, httpx.HTTPStatusError):
            status = exc.response.status_code
            if status == 401:
                return LLMConnectionError(
                    "Atlas rejected the bearer token (401): set SQUADOPS__LLM__API_KEY to a "
                    "token from the server's --auth-tokens-file"
                )
            if status == 404:
                return LLMModelNotFoundError(f"Model '{model}' not found on Atlas")
            detail = exc.response.text[:200]
            return LLMConnectionError(f"Atlas {operation} failed ({status}): {detail}")
        return LLMConnectionError(f"Atlas {operation} failed: {exc}")

    async def generate(self, request: LLMRequest) -> LLMResponse:
        """A bare prompt as a single-user-turn chat completion (``/v1/completions`` is
        not universal on OpenAI-shaped backends; ``/v1/chat/completions`` is)."""
        model = request.model or self._default_model
        message = await self._chat(
            [ChatMessage(role="user", content=request.prompt)],
            model=model,
            max_tokens=request.max_tokens,
            temperature=request.temperature,
            timeout_seconds=request.timeout_seconds,
            reasoning=request.reasoning,
            operation="generate",
        )
        return LLMResponse(
            text=message.content,
            model=model,
            prompt_tokens=message.prompt_tokens,
            completion_tokens=message.completion_tokens,
            total_tokens=message.total_tokens,
            tokens_per_second=message.tokens_per_second,
            reasoning_tokens=message.reasoning_tokens,
        )

    async def chat(
        self,
        messages: list[ChatMessage],
        model: str | None = None,
        max_tokens: int | None = None,
        temperature: float | None = None,
        timeout_seconds: float | None = None,
        reasoning: str | None = None,
    ) -> ChatMessage:
        return await self._chat(
            messages,
            model=model or self._default_model,
            max_tokens=max_tokens,
            temperature=temperature,
            timeout_seconds=timeout_seconds,
            reasoning=reasoning,
            operation="chat",
        )

    async def _chat(
        self,
        messages: list[ChatMessage],
        *,
        model: str,
        max_tokens: int | None,
        temperature: float | None,
        timeout_seconds: float | None,
        reasoning: str | None,
        operation: str,
    ) -> ChatMessage:
        client = await self._get_client()
        timeout = timeout_seconds or self._timeout
        started = time.monotonic()
        try:
            response = await client.post(
                "/v1/chat/completions",
                json=self._payload(messages, model, max_tokens, temperature, reasoning),
                timeout=timeout,
            )
            response.raise_for_status()
            data = response.json()
        except Exception as e:
            raise self._translate(e, model, operation) from e

        elapsed = time.monotonic() - started
        message = (data.get("choices") or [{}])[0].get("message") or {}
        prompt_tok, completion_tok, total_tok, reasoning_tok = _usage_from(data)
        tps = _tokens_per_second(data, completion_tok, elapsed)
        logger.info(
            "LLM %s completed: model=%s, prompt_tokens=%s, completion_tokens=%s, "
            "reasoning_tokens=%s, t/s=%.1f",
            operation,
            model,
            prompt_tok,
            completion_tok,
            reasoning_tok,
            tps or 0.0,
        )
        return ChatMessage(
            role=message.get("role", "assistant"),
            content=message.get("content", "") or "",
            prompt_tokens=prompt_tok,
            completion_tokens=completion_tok,
            total_tokens=total_tok,
            tokens_per_second=tps,
            reasoning_tokens=reasoning_tok,
        )

    async def _stream_frames(
        self,
        messages: list[ChatMessage],
        model: str,
        max_tokens: int | None,
        temperature: float | None,
        timeout: float,
        reasoning: str | None,
        operation: str,
    ) -> AsyncIterator[dict[str, Any]]:
        """Decoded SSE frames up to the ``[DONE]`` sentinel; a malformed frame is skipped."""
        client = await self._get_client()
        try:
            async with client.stream(
                "POST",
                "/v1/chat/completions",
                json=self._payload(
                    messages, model, max_tokens, temperature, reasoning, stream=True
                ),
                timeout=timeout,
            ) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if not line.startswith("data:"):
                        continue
                    raw = line[5:].strip()
                    if raw == "[DONE]":
                        break
                    try:
                        yield json.loads(raw)
                    except json.JSONDecodeError:
                        logger.debug("Skipping malformed Atlas SSE frame")
        except (httpx.TimeoutException, httpx.ConnectError, httpx.HTTPStatusError) as e:
            raise self._translate(e, model, operation) from e

    async def chat_stream(
        self,
        messages: list[ChatMessage],
        model: str | None = None,
        max_tokens: int | None = None,
        temperature: float | None = None,
        timeout_seconds: float | None = None,
        reasoning: str | None = None,
    ) -> AsyncIterator[str]:
        """Assistant *content* as text chunks. ``delta.reasoning_content`` frames are the
        thinking channel and are not content — they are skipped, not spliced in."""
        resolved = model or self._default_model
        async for frame in self._stream_frames(
            messages,
            resolved,
            max_tokens,
            temperature,
            timeout_seconds or self._timeout,
            reasoning,
            "chat_stream",
        ):
            for choice in frame.get("choices") or []:
                content = (choice.get("delta") or {}).get("content")
                if content:
                    yield content

    async def chat_stream_with_usage(
        self,
        messages: list[ChatMessage],
        model: str | None = None,
        max_tokens: int | None = None,
        temperature: float | None = None,
        timeout_seconds: float | None = None,
        reasoning: str | None = None,
    ) -> ChatMessage:
        """Stream for liveness, return one assembled message with the usage frame's counts."""
        resolved = model or self._default_model
        started = time.monotonic()
        chunks: list[str] = []
        usage_frame: dict[str, Any] = {}
        async for frame in self._stream_frames(
            messages,
            resolved,
            max_tokens,
            temperature,
            timeout_seconds or self._timeout,
            reasoning,
            "chat_stream_with_usage",
        ):
            for choice in frame.get("choices") or []:
                content = (choice.get("delta") or {}).get("content")
                if content:
                    chunks.append(content)
            if frame.get("usage"):
                usage_frame = frame
        elapsed = time.monotonic() - started
        prompt_tok, completion_tok, total_tok, reasoning_tok = _usage_from(usage_frame)
        tps = _tokens_per_second(usage_frame, completion_tok, elapsed)
        return ChatMessage(
            role="assistant",
            content="".join(chunks),
            prompt_tokens=prompt_tok,
            completion_tokens=completion_tok,
            total_tokens=total_tok,
            tokens_per_second=tps,
            reasoning_tokens=reasoning_tok,
        )

    def list_models(self) -> list[str]:
        """Cached names; no I/O, per the port contract."""
        return self._models_cache.copy()

    async def refresh_models(self) -> list[str]:
        """Refresh the cache, keeping the last known list on failure (an emptied cache
        reads downstream as *no models present* and blocks work)."""
        try:
            self._models_cache = [m.name for m in await self.list_available_models()]
        except Exception:
            logger.debug("Atlas model refresh failed; keeping the last known list")
        return self._models_cache.copy()

    async def list_available_models(self) -> list[ModelInfo]:
        """``/v1/models`` — ids verbatim (HF paths); no size or modification time, so
        those stay ``None``. Atlas's extra ``max_model_len`` is the served window, not a
        model fact, and is not surfaced here."""
        client = await self._get_client()
        try:
            response = await client.get("/v1/models", timeout=self._model_list_timeout)
            response.raise_for_status()
            data = response.json()
        except Exception as e:
            raise self._translate(e, self._default_model, "list_available_models") from e
        return [ModelInfo(name=name) for entry in data.get("data", []) if (name := entry.get("id"))]

    async def health(self) -> dict[str, Any]:
        """Reachability and auth in one probe; never raises."""
        try:
            client = await self._get_client()
            response = await client.get("/v1/models", timeout=self._model_list_timeout)
            report: dict[str, Any] = {
                "healthy": response.status_code == 200,
                "base_url": self._base_url,
                "models_available": len(self._models_cache),
            }
            if response.status_code == 401:
                report["error"] = "bearer token rejected (set SQUADOPS__LLM__API_KEY)"
            return report
        except Exception as e:
            return {"healthy": False, "base_url": self._base_url, "error": str(e)}

    async def close(self) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None
