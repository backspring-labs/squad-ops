"""vLLM LLM adapter — OpenAI-compatible HTTP surface.

Second provider adapter, per the Atlas Provider Adapter SIP (SIP-0106) P6. Independent of
:class:`~adapters.llm.ollama.OllamaAdapter` by design (§3.5a): one adapter per
provider, no shared dialect base. Sharing a class across providers would put a
"which provider am I" conditional inside it — the identity-branching #559 bans —
and any real overlap is better extracted once two implementations exist and the
overlap is demonstrated rather than assumed.

**Dialect, verified against a live OpenAI-compatible server rather than assumed:**

- ``POST /v1/chat/completions`` — messages in, ``choices[0].message.content`` out.
- ``POST /v1/completions`` is *not* used; :meth:`generate` is expressed as a
  single-user-turn chat, because the legacy completions endpoint is deprecated
  upstream and not universally served.
- Streaming is SSE: ``data: {json}`` frames, blank-line separated, terminated by
  ``data: [DONE]``. Content arrives at ``choices[0].delta.content``.
- ``GET /v1/models`` returns ``{"object": "list", "data": [{"id": ...}]}``. The
  model *name* is ``id``; there is no size or modification time in this shape, so
  :class:`ModelInfo` carries ``None`` for both rather than inventing values.
- Errors are ``{"error": {"message": ..., "type": ...}}`` with 404 for an unknown
  model.

**No native throughput field.** Unlike Ollama's ``eval_count``/``eval_duration``,
the OpenAI shape reports token counts and no timings at all. Tokens/sec is
therefore computed here from measured wall-clock, and is *inclusive* of prefill
and queueing where Ollama's native number is decode-only. The two are not
interchangeable, which is exactly why the A/B artifact records wall-clock as the
decision field and treats rate as a diagnostic (SIP §3.6.1).
"""

from __future__ import annotations

import json
import logging
import time
from collections.abc import AsyncIterator, Callable
from typing import Any

import httpx

from squadops.llm.exceptions import (
    LLMConnectionError,
    LLMModelNotFoundError,
    LLMTimeoutError,
)
from squadops.llm.model_registry import ModelSpec, ReasoningControl, get_model_spec
from squadops.llm.models import ChatMessage, LLMRequest, LLMResponse, ModelInfo, ReasoningLevel
from squadops.ports.llm.provider import LLMCapability, LLMPort

logger = logging.getLogger(__name__)

_DEFAULT_MODEL_LIST_TIMEOUT = 10.0
_SSE_DATA_PREFIX = "data: "
_SSE_DONE = "[DONE]"


def _tokens_per_second(completion_tokens: int | None, elapsed_seconds: float) -> float | None:
    """Generation rate from measured wall-clock.

    Client-side by necessity: the OpenAI response shape carries no timings. This
    number therefore includes prefill and any queueing, unlike Ollama's
    decode-only ``eval_count / eval_duration``. Returned as ``None`` rather than
    ``0.0`` when it cannot be computed — a zero rate is indistinguishable from a
    real measurement and would drag any average toward zero.
    """
    if not completion_tokens or elapsed_seconds <= 0:
        return None
    return round(completion_tokens / elapsed_seconds, 2)


# The port's level → the request fields for each reasoning dial a model can
# declare (#927). The OpenAI request shape has no reasoning field of its own;
# every model family reaches its channel differently, so the mapping is keyed on
# the dial the model spec declares, never on the model's name.
_REASONING_DIALS: dict[str, Callable[[str], dict[str, Any]]] = {
    # qwen3-family: a chat-template switch. The grades collapse to on.
    ReasoningControl.TOGGLE: lambda level: {
        "chat_template_kwargs": {"enable_thinking": level != ReasoningLevel.NONE}
    },
    # gpt-oss-family: the level verbatim. ``none`` cannot be expressed on this
    # dial — the model always reasons — so it becomes the lowest effort.
    ReasoningControl.EFFORT: lambda level: {
        "reasoning_effort": ReasoningLevel.LOW if level == ReasoningLevel.NONE else level
    },
}


def _reasoning_fields(spec: ModelSpec | None, reasoning: str) -> dict[str, Any]:
    """Request fields expressing ``reasoning`` on the dial ``spec`` declares.

    Empty for a model with no dial or no registry entry: a field the server does
    not understand is rejected outright by some backends, and the port states
    the level is a request, not a guarantee. (An unregistered model is #1145's
    preflight finding, not this adapter's guess.)
    """
    if spec is None:
        return {}
    dial = _REASONING_DIALS.get(spec.reasoning_control)
    return dial(reasoning) if dial else {}


def _usage_from(payload: dict[str, Any]) -> tuple[int | None, int | None, int | None]:
    """(prompt, completion, total) from an OpenAI ``usage`` object.

    All-or-nothing: a provider that omits usage yields three ``None``s, never a
    partial row. Partial usage is worse than absent — a caller cannot tell which
    half is real (SIP §3.5).
    """
    usage = payload.get("usage") or {}
    prompt = usage.get("prompt_tokens")
    completion = usage.get("completion_tokens")
    total = usage.get("total_tokens")
    if total is None and (prompt is not None or completion is not None):
        total = (prompt or 0) + (completion or 0)
    return prompt, completion, total


class VLLMAdapter(LLMPort):
    """vLLM adapter speaking the OpenAI-compatible HTTP surface.

    Class name is CapWords per the tree's convention — every adapter class is,
    and ``LangFuseAdapter`` already normalizes a product branded "Langfuse". The
    provider string is ``"vllm"``, and the project is written "vLLM" in prose.
    """

    def __init__(
        self,
        base_url: str = "http://localhost:8000",
        default_model: str = "",
        timeout_seconds: float = 180.0,
        model_list_timeout_seconds: float = _DEFAULT_MODEL_LIST_TIMEOUT,
        api_key: str | None = None,
    ):
        """Initialize the vLLM adapter.

        Args:
            base_url: server root. ``/v1`` is appended by the request paths, so
                pass ``http://host:8000``, not ``http://host:8000/v1``.
            default_model: model used when a request does not name one.
            timeout_seconds: default request timeout.
            model_list_timeout_seconds: timeout for the listing/health probe,
                separate from generation (the #158 rationale).
            api_key: optional bearer token. Self-hosted vLLM is typically open;
                resolved config must pass a ``secret://`` ref through
                ``SecretManager`` at the factory, never a literal.
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
        """Declare what this adapter does (#572's rule — see the port).

        ``model_management`` is **False**: the OpenAI surface has no pull/delete
        equivalent, and vLLM serves the weights it was launched with. Callers get
        an honest 503 rather than a method that silently does nothing.

        ``streaming_usage`` is **True**: the adapter requests
        ``stream_options.include_usage`` and consumes the terminal usage frame.
        Verified end to end against a live OpenAI-compatible server, which
        returns that frame with an empty ``choices`` list.

        This is nonetheless the flag most at risk against a *partial* OpenAI
        implementation, since a server may accept the option and send nothing.
        Such a server would report ``None`` counts here — which the conformance
        suite catches as a declared-True-but-inert capability rather than
        letting it pass as working.
        """
        return {
            LLMCapability.MODEL_LISTING: True,
            LLMCapability.MODEL_MANAGEMENT: False,
            LLMCapability.STREAMING_USAGE: True,
            LLMCapability.THINKING_TOKENS: False,
            # A level reaches the wire only on the dial the model spec declares
            # (``_REASONING_DIALS``); for a model with none it is dropped, which is
            # the port's stated contract, not a capability outage.
            LLMCapability.REASONING_CONTROL: True,
        }

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            headers = {"Authorization": f"Bearer {self._api_key}"} if self._api_key else {}
            self._client = httpx.AsyncClient(
                base_url=self._base_url,
                timeout=httpx.Timeout(self._timeout),
                headers=headers,
            )
        return self._client

    def _payload(
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
        payload: dict[str, Any] = {
            "model": model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "stream": stream,
        }
        if max_tokens is not None:
            payload["max_tokens"] = max_tokens
        if temperature is not None:
            payload["temperature"] = temperature
        # #901: the pair. `top_p` is a standard field on the OpenAI shape, so it needs
        # no dialect translation — unlike top_k/min_p, which are deliberately NOT added
        # here (see requirements note in the PR): they are not standard on this surface
        # and would be dropped or rejected depending on the server, which is the same
        # silent-half-configuration defect this fixes.
        if top_p is not None:
            payload["top_p"] = top_p
        if reasoning is not None:
            payload.update(_reasoning_fields(get_model_spec(model), reasoning))
        if stream:
            # Without this the stream carries no usage frame at all and token
            # accounting for streamed calls is simply lost.
            payload["stream_options"] = {"include_usage": True}
        return payload

    def _translate(self, exc: Exception, model: str, operation: str) -> Exception:
        """Map a transport failure onto the port's exception vocabulary.

        Load-bearing rather than cosmetic: failure-locus classification (#568)
        reads these types to decide whether a failure is infrastructure or a
        work-product defect. A raw ``httpx`` error escaping here would reclassify
        an outage as a squad mistake and burn a correction attempt on it.
        """
        if isinstance(exc, httpx.TimeoutException):
            return LLMTimeoutError(f"vLLM {operation} timed out after {self._timeout}s")
        if isinstance(exc, httpx.ConnectError):
            return LLMConnectionError(f"Failed to connect to vLLM at {self._base_url}")
        if isinstance(exc, httpx.HTTPStatusError):
            if exc.response.status_code == 404:
                return LLMModelNotFoundError(f"Model '{model}' not found")
            return LLMConnectionError(f"vLLM {operation} failed: {exc}")
        return LLMConnectionError(f"vLLM {operation} failed: {exc}")

    async def generate(self, request: LLMRequest) -> LLMResponse:
        """Generate from a bare prompt.

        Expressed as a single-user-turn chat completion: ``/v1/completions`` is
        deprecated upstream and not served by every OpenAI-compatible backend,
        while ``/v1/chat/completions`` is universal.
        """
        model = request.model or self._default_model
        message = await self._chat(
            [ChatMessage(role="user", content=request.prompt)],
            model=model,
            max_tokens=request.max_tokens,
            temperature=request.temperature,
            top_p=request.top_p,
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
        )

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
        return await self._chat(
            messages,
            model=model or self._default_model,
            max_tokens=max_tokens,
            temperature=temperature,
            top_p=top_p,
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
        top_p: float | None,
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
                json=self._payload(messages, model, max_tokens, temperature, top_p, reasoning),
                timeout=timeout,
            )
            response.raise_for_status()
            data = response.json()
        except Exception as e:
            raise self._translate(e, model, operation) from e

        elapsed = time.monotonic() - started
        choices = data.get("choices") or [{}]
        message = choices[0].get("message") or {}
        prompt_tok, completion_tok, total_tok = _usage_from(data)
        tps = _tokens_per_second(completion_tok, elapsed)

        logger.info(
            "LLM %s completed: model=%s, prompt_tokens=%s, completion_tokens=%s, t/s=%.1f",
            operation,
            model,
            prompt_tok,
            completion_tok,
            tps or 0.0,
        )

        return ChatMessage(
            role=message.get("role", "assistant"),
            content=message.get("content", "") or "",
            prompt_tokens=prompt_tok,
            completion_tokens=completion_tok,
            total_tokens=total_tok,
            tokens_per_second=tps,
            # #410: the OpenAI-compatible reasoning channel. Atlas documents it at
            # ``message.reasoning_content`` (SIP-0106 §2.0); vLLM populates the same
            # field when served with a --reasoning-parser. `.get` with no default
            # keeps None (no channel) distinct from "" (channel present, empty).
            reasoning_text=message.get("reasoning_content"),
        )

    async def _stream_frames(
        self,
        messages: list[ChatMessage],
        *,
        model: str,
        max_tokens: int | None,
        temperature: float | None,
        top_p: float | None,
        timeout: float,
        reasoning: str | None,
        operation: str,
    ) -> AsyncIterator[dict[str, Any]]:
        """Yield decoded SSE frames, skipping the terminal sentinel.

        SSE, not NDJSON: each frame is ``data: {json}``. A malformed frame is
        skipped rather than fatal — one unparseable chunk must not discard a
        generation that is otherwise complete.
        """
        client = await self._get_client()
        try:
            async with client.stream(
                "POST",
                "/v1/chat/completions",
                json=self._payload(
                    messages, model, max_tokens, temperature, top_p, reasoning, stream=True
                ),
                timeout=timeout,
            ) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if not line or not line.startswith(_SSE_DATA_PREFIX):
                        continue
                    body = line[len(_SSE_DATA_PREFIX) :].strip()
                    if body == _SSE_DONE:
                        break
                    try:
                        yield json.loads(body)
                    except json.JSONDecodeError:
                        logger.debug("Skipping malformed vLLM SSE frame")
        except Exception as e:
            raise self._translate(e, model, operation) from e

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
        """Stream assistant content as plain text chunks."""
        resolved = model or self._default_model
        async for frame in self._stream_frames(
            messages,
            model=resolved,
            max_tokens=max_tokens,
            temperature=temperature,
            top_p=top_p,
            timeout=timeout_seconds or self._timeout,
            reasoning=reasoning,
            operation="chat_stream",
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
        top_p: float | None = None,
        timeout_seconds: float | None = None,
        reasoning: str | None = None,
    ) -> ChatMessage:
        """Stream for connection liveness, return one assembled message.

        The final frame carries usage when the server honors
        ``stream_options.include_usage``. A server that does not send one leaves
        the counts ``None`` — never zero, which would read as a free call.
        """
        resolved = model or self._default_model
        started = time.monotonic()
        chunks: list[str] = []
        reasoning_chunks: list[str] = []
        saw_reasoning = False
        usage_frame: dict[str, Any] = {}

        async for frame in self._stream_frames(
            messages,
            model=resolved,
            max_tokens=max_tokens,
            temperature=temperature,
            top_p=top_p,
            timeout=timeout_seconds or self._timeout,
            reasoning=reasoning,
            operation="chat_stream_with_usage",
        ):
            if frame.get("usage"):
                usage_frame = frame
            for choice in frame.get("choices") or []:
                delta = choice.get("delta") or {}
                content = delta.get("content")
                if content:
                    chunks.append(content)
                # #1194: ``delta.reasoning_content`` is the streamed half of the
                # channel ``_chat`` already reads at ``message.reasoning_content``.
                # Skipping it here is right for ``chat_stream`` (thinking is not
                # content) but wrong for this method, whose whole job is to assemble
                # the complete message. ``is not None`` keeps an absent channel
                # distinct from a present-and-empty one.
                reasoning = delta.get("reasoning_content")
                if reasoning is not None:
                    saw_reasoning = True
                    reasoning_chunks.append(reasoning)

        elapsed = time.monotonic() - started
        prompt_tok, completion_tok, total_tok = _usage_from(usage_frame)
        tps = _tokens_per_second(completion_tok, elapsed)

        logger.info(
            "LLM chat_stream_with_usage completed: model=%s, prompt_tokens=%s, "
            "completion_tokens=%s, t/s=%.1f",
            resolved,
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
            reasoning_text="".join(reasoning_chunks) if saw_reasoning else None,
        )

    def list_models(self) -> list[str]:
        """Cached model names. Performs no I/O, per the port contract."""
        return self._models_cache.copy()

    async def refresh_models(self) -> list[str]:
        """Refresh the name cache, preserving the last known list on failure.

        Emptying the cache on a transient blip would read downstream as *no
        models present* and block work that should proceed.
        """
        try:
            self._models_cache = [m.name for m in await self.list_available_models()]
        except Exception:
            logger.debug("vLLM model refresh failed; keeping the last known list")
        return self._models_cache.copy()

    async def list_available_models(self) -> list[ModelInfo]:
        """Models the server can serve.

        ``/v1/models`` carries no size or modification time, so those stay
        ``None`` rather than being invented — a caller can tell "not reported"
        from "zero".
        """
        client = await self._get_client()
        try:
            response = await client.get("/v1/models", timeout=self._model_list_timeout)
            response.raise_for_status()
            data = response.json()
        except Exception as e:
            raise self._translate(e, self._default_model, "list_available_models") from e

        return [ModelInfo(name=name) for entry in data.get("data", []) if (name := entry.get("id"))]

    async def health(self) -> dict[str, Any]:
        """Report reachability. Never raises — a probe that raises takes down
        the caller it was meant to inform."""
        try:
            client = await self._get_client()
            response = await client.get("/v1/models", timeout=self._model_list_timeout)
            return {
                "healthy": response.status_code == 200,
                "base_url": self._base_url,
                "models_available": len(self._models_cache),
            }
        except Exception as e:
            return {"healthy": False, "base_url": self._base_url, "error": str(e)}

    async def close(self) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None
