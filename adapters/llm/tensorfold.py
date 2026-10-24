"""TensorFold adapter: TensorFold v0.6.6's OpenAI-shaped CUDA server on the Spark (SIP-0111 §5, #2200).

Its own file, beside vLLM's and Atlas's, with no shared dialect base (SIP-0106 §3.5a). The wire is
read from the server's source at the pinned commit (``tensorfold/server/http.py``, ``errors.py``,
``metrics.py`` and ``auth_http.py`` at ``cb2ebf05``), not assumed from the OpenAI shape:

- ``POST /v1/chat/completions``, always streamed. A stream is the role frame, the ``reasoning_content``
  and ``content`` deltas, one finish frame (``finish_reason``, and TensorFold's own ``tensorfold``
  block with ``prefill_s`` and ``decode_s``), the usage frame (``choices: []``) and ``data: [DONE]``.
- **A failure after the stream starts is an ``error`` frame, and ``[DONE]`` still follows.** So
  ``[DONE]`` alone never means success (§5.4's terminal-state check).
- A prompt past the window is OpenAI's ``context_length_exceeded``. Before the stream it is a 400
  whose ``error.code`` names it, and after it an ``error`` frame. The message is the server's own:
  "This server's maximum context length is N tokens: the rendered prompt has M tokens …".
- With keys on, ``/health`` says only ``ok``. ``/v1/models``, ``/metrics`` and ``/tokenize`` need the
  key, and answer 401 with ``code: invalid_api_key`` without it (§5.5).
- ``/metrics`` counts ``tensorfold:requests_running`` and ``tensorfold:requests_waiting``. The CUDA
  server counts no client disconnections, so a cancelled request's release is read from those two.

**What it sends is G0's request** (§5.7), so the adapter is measured by the gates that passed:
- the served id, the call's ``max_tokens`` (the registry's completion allowance where the call names
  none, as the harness had it), and a seed on every call: the call's own, or a fresh one where it
  sets none, named on the call's line (§9j). TensorFold keys an omitted seed to the prompt
  (``engine/exact_sampling.py``'s ``seed_for``), so a repeated prompt would repeat its sample;
- the frozen recipe's sampling, unless the call sets its own temperature or ``top_p``;
- reasoning at parity with Ollama's prompt (§9c): ``enable_thinking`` on or off, and with it on, the
  recipe's ``parity_effort``, never the port's level. A call that names no level sends the effort
  alone, which the server hears as thinking on (the model's own default on both engines);
- ``thinking_budget`` where one is set.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
import secrets
import time
from collections.abc import AsyncIterator
from contextlib import aclosing
from dataclasses import dataclass, field
from typing import Any

import httpx

from squadops.llm.exceptions import (
    LLMConnectionError,
    LLMContextOverflowError,
    LLMModelNotFoundError,
    LLMTimeoutError,
)
from squadops.llm.model_registry import get_model_spec
from squadops.llm.models import (
    ChatMessage,
    LLMRequest,
    LLMResponse,
    ModelInfo,
    ReasoningLevel,
    Termination,
)
from squadops.ports.llm.provider import LLMCapability, LLMPort

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ServedRecipe:
    """What a frozen recipe fixes on the wire for its served id (``infra/tensorfold/recipes``)."""

    #: The level whose rendered prompt is Ollama's to the token (§9c): the checkpoints' template
    #: writes an effort line for ``xhigh`` (its default) and ``low``, and none for ``medium``.
    parity_effort: str
    temperature: float
    top_p: float
    top_k: int
    min_p: float
    #: #2561: the weights the recipe serves, as its checkpoint's ``hf:<repo>@<revision>``. The
    #: server's ``/v1/models`` lists ids only, so this is what a deploy record names as the
    #: served id's digest: a revision pins the checkpoint's content as a pull digest does.
    weights: str


#: The served ids this adapter can speak for, each with its frozen recipe's wire settings. A test
#: holds this table to the recipes' YAML. A served id without a frozen recipe is refused: sent
#: with nothing fixed, it would think at the template's ``xhigh`` and sample at the server's
#: defaults, which no gate measured.
RECIPES: dict[str, ServedRecipe] = {
    "qwen3.8-27b-tf-nvfp4": ServedRecipe(
        parity_effort=ReasoningLevel.MEDIUM,
        temperature=1.0,
        top_p=0.95,
        top_k=20,
        min_p=0.0,
        weights="hf:nvidia/Qwen3.8-27B-NVFP4@482ca0f3832238542f8f5295dde86b5f22711d80",
    ),
}

_TERMINATIONS = {"stop": Termination.STOP, "length": Termination.LENGTH}
_OVERFLOW_CODE = "context_length_exceeded"
_OVERFLOW = re.compile(
    r"maximum context length is (\d+) tokens: the rendered prompt has (\d+) tokens"
)
_GAUGE = re.compile(r"^tensorfold:(requests_running|requests_waiting) (\d+)\s*$", re.M)
#: The server's seed domain: ``seed_for`` derives an omitted seed as 63 bits, and the samplers mask
#: what they are sent to 63.
_SEED_BITS = 63

_DEFAULT_INACTIVITY_SECONDS = 120.0
_DEFAULT_RELEASE_SECONDS = 30.0
_RELEASE_POLL_SECONDS = 0.5
_PROBE_TIMEOUT_SECONDS = 10.0


class Residency:
    """What the server is doing, read only from authenticated sources (§5.5). Only ``IDLE`` is
    safe to launch on: the others are never quiet."""

    IDLE = "idle"
    BUSY = "busy"
    UNAUTHORIZED = "unauthorized"
    UNREACHABLE = "unreachable"
    UNKNOWN = "unknown"


class TensorFoldUnauthorizedError(LLMConnectionError):
    """The server refused the key (401): an error that names the key setting (§5.5)."""


class TensorFoldUnreachableError(LLMConnectionError):
    """Nothing answered at the server's address."""


class TensorFoldStreamError(LLMConnectionError):
    """A stream that did not end as a success: an ``error`` frame, a frame that is not JSON, or a
    stream cut before its finish frame, usage and ``[DONE]`` (§5.4). Never a partial success:
    ``partial`` holds what arrived, as evidence only."""

    def __init__(self, message: str, partial: dict[str, str]):
        super().__init__(message)
        self.partial = partial


def _overflow(message: str) -> LLMContextOverflowError:
    found = _OVERFLOW.search(message)
    window, prompt = (int(found.group(1)), int(found.group(2))) if found else (None, None)
    return LLMContextOverflowError(message, served_window=window, prompt_tokens=prompt)


@dataclass
class _Reply:
    """One streamed reply, read frame by frame and checked at its end."""

    model: str
    content: list[str] = field(default_factory=list)
    reasoning: list[str] = field(default_factory=list)
    saw_reasoning: bool = False
    finish_reason: str | None = None
    timings: dict[str, Any] = field(default_factory=dict)
    usage: dict[str, Any] | None = None

    def partial(self) -> dict[str, str]:
        return {"content": "".join(self.content), "reasoning": "".join(self.reasoning)}

    def fail(self, message: str) -> TensorFoldStreamError:
        return TensorFoldStreamError(
            f"TensorFold stream for '{self.model}': {message}", self.partial()
        )

    def read(self, frame: dict[str, Any]) -> list[str]:
        """Take one frame; return the content it adds. An ``error`` frame raises."""
        if "error" in frame:
            error = (
                frame["error"] if isinstance(frame["error"], dict) else {"message": frame["error"]}
            )
            message = str(error.get("message", error))
            if error.get("code") == _OVERFLOW_CODE:
                raise _overflow(message)
            raise self.fail(f"the server reported {error.get('type', 'an error')}: {message}")
        if frame.get("usage") is not None:
            if self.finish_reason is None:
                raise self.fail("the usage frame arrived before the finish frame")
            self.usage = frame["usage"]
        added: list[str] = []
        for choice in frame.get("choices") or []:
            delta = choice.get("delta") or {}
            if delta.get("content"):
                added.append(delta["content"])
            thought = delta.get("reasoning_content")
            if thought is not None:
                self.saw_reasoning = True
                self.reasoning.append(thought)
            if choice.get("finish_reason"):
                self.finish_reason = choice["finish_reason"]
                self.timings = frame.get("tensorfold") or {}
        self.content += added
        return added

    def finished(self) -> None:
        """At ``[DONE]``: the finish frame and its usage must both have arrived."""
        if self.finish_reason is None:
            raise self.fail("[DONE] arrived with no finish frame")
        if self.usage is None:
            raise self.fail("[DONE] arrived with no usage frame")

    def message(self, elapsed: float) -> ChatMessage:
        usage = self.usage or {}
        completion = usage.get("completion_tokens")
        details = usage.get("completion_tokens_details") or {}
        decode = self.timings.get("decode_s")
        # Decode-only, as Ollama's eval rate is: TensorFold times its own decode. Wall-clock (which
        # includes prefill) only where it does not.
        span = decode if isinstance(decode, int | float) and decode > 0 else elapsed
        prefill = self.timings.get("prefill_s")
        return ChatMessage(
            role="assistant",
            content="".join(self.content),
            prompt_tokens=usage.get("prompt_tokens"),
            # Inclusive of the reasoning tokens, which are a subset of it: never subtracted (Q6).
            completion_tokens=completion,
            total_tokens=usage.get("total_tokens"),
            tokens_per_second=round(completion / span, 2) if completion and span > 0 else None,
            reasoning_tokens=details.get("reasoning_tokens"),
            reasoning_text="".join(self.reasoning) if self.saw_reasoning else None,
            prompt_eval_seconds=prefill if isinstance(prefill, int | float) else None,
            termination=_TERMINATIONS.get(self.finish_reason or ""),
        )


class TensorFoldAdapter(LLMPort):
    """TensorFold v0.6.6 on GB10 CUDA, selected by ``provider == "tensorfold"`` (SIP-0111 §5)."""

    def __init__(
        self,
        base_url: str,
        default_model: str,
        timeout_seconds: float = 180.0,
        api_key: str | None = None,
        *,
        inactivity_seconds: float = _DEFAULT_INACTIVITY_SECONDS,
        release_seconds: float = _DEFAULT_RELEASE_SECONDS,
    ):
        """
        Args:
            base_url: the server's root, without ``/v1``.
            default_model: the served id used when a call names no model.
            timeout_seconds: the overall deadline of a call, stream included (§5.4).
            api_key: the server's key. A missing or wrong key fails every call visibly (401),
                and health reads ``unauthorized``.
            inactivity_seconds: how long a stream may send nothing before it is a silent server.
            release_seconds: how long the next call waits for an abandoned request's release.
        """
        self._base_url = base_url.rstrip("/")
        self._default_model = default_model
        self._timeout = timeout_seconds
        self._api_key = api_key
        self._inactivity = inactivity_seconds
        self._release_seconds = release_seconds
        self._models_cache: list[str] = []
        self._client: httpx.AsyncClient | None = None
        #: Models whose served window was read and found to hold the registry's (§5.3).
        self._windows_verified: set[str] = set()
        #: Set when a request was abandoned (a deadline, a cancellation, a broken stream): the
        #: requests in flight before it was sent. The next call waits for the server to be back
        #: to that before it sends anything (§5.4). ``-1`` when that count could not be read, in
        #: which case nothing may be in flight.
        self._unreleased: int | None = None

    @property
    def default_model(self) -> str:
        return self._default_model

    @property
    def engine(self) -> str:
        return "tensorfold"

    def capabilities(self) -> dict[str, bool]:
        return {
            LLMCapability.MODEL_LISTING: True,
            # It serves the recipe it was started with: models change by S's switch, not here.
            LLMCapability.MODEL_MANAGEMENT: False,
            LLMCapability.STREAMING_USAGE: True,
            # ``usage.completion_tokens_details.reasoning_tokens``.
            LLMCapability.THINKING_TOKENS: True,
            LLMCapability.REASONING_CONTROL: True,
            LLMCapability.LOADED_MODELS: True,
            LLMCapability.SEED: True,
            LLMCapability.THINKING_BUDGET: True,
            # ``tensorfold:requests_running`` + ``requests_waiting``, authenticated (§5.5).
            LLMCapability.REQUESTS_IN_FLIGHT: True,
        }

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            headers = {"Authorization": f"Bearer {self._api_key}"} if self._api_key else {}
            self._client = httpx.AsyncClient(
                base_url=self._base_url,
                headers=headers,
                timeout=httpx.Timeout(self._inactivity, connect=_PROBE_TIMEOUT_SECONDS),
            )
        return self._client

    # ------------------------------------------------------------------ the request

    def _payload(
        self,
        messages: list[ChatMessage],
        model: str,
        max_tokens: int | None,
        temperature: float | None,
        top_p: float | None,
        reasoning: str | None,
        *,
        seed: int | None,
        thinking_budget: int | None,
    ) -> dict[str, Any]:
        recipe = RECIPES.get(model)
        if recipe is None:
            raise LLMModelNotFoundError(
                f"'{model}' has no frozen TensorFold recipe in this adapter (RECIPES): sent as it "
                "is, it would think and sample at settings no gate measured"
            )
        spec = get_model_spec(model)
        if max_tokens is None and spec is not None:
            max_tokens = spec.default_max_completion
        payload: dict[str, Any] = {
            "model": model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "stream": True,
            "stream_options": {"include_usage": True},
        }
        if max_tokens is not None:
            payload["max_tokens"] = max_tokens
        # A seed on every call (§9j): TensorFold keys an omitted one to the prompt. Drawn from the
        # OS, not ``random``, whose state anything in the process may have seeded.
        payload["seed"] = secrets.randbits(_SEED_BITS) if seed is None else seed
        payload["temperature"] = recipe.temperature if temperature is None else temperature
        payload["top_p"] = recipe.top_p if top_p is None else top_p
        payload["top_k"] = recipe.top_k
        payload["min_p"] = recipe.min_p
        if reasoning is None:
            # No level named: the model's own posture, which is thinking on both engines, at
            # Ollama's prompt. The effort alone is heard as thinking on at that effort
            # (``request_options.thinking_fields``), so no switch is sent the call did not ask for.
            payload["reasoning_effort"] = recipe.parity_effort
        else:
            thinking = reasoning != ReasoningLevel.NONE
            payload["chat_template_kwargs"] = {"enable_thinking": thinking}
            if thinking:
                payload["reasoning_effort"] = recipe.parity_effort
        if thinking_budget is not None:
            payload["thinking_budget"] = thinking_budget
        return payload

    def _refusal(self, response: httpx.Response, model: str) -> Exception:
        """A refused request, read from TensorFold's error body."""
        try:
            error = (response.json() or {}).get("error") or {}
        except ValueError:
            error = {"message": response.text[:300]}
        if not isinstance(error, dict):  # an error string, not OpenAI's object
            error = {"message": str(error)}
        message = str(error.get("message", ""))
        status = response.status_code
        if error.get("code") == _OVERFLOW_CODE:
            return _overflow(message)
        if status == 401:
            return TensorFoldUnauthorizedError(
                "TensorFold refused the API key (401): set SQUADOPS__LLM__API_KEY to the key the "
                "server was started with"
            )
        if status == 404:
            return LLMModelNotFoundError(f"TensorFold does not serve '{model}': {message}")
        if status == 503:
            return LLMConnectionError(f"TensorFold is at capacity (503): {message}")
        return LLMConnectionError(f"TensorFold refused the request ({status}): {message}")

    def _translate(self, exc: Exception, operation: str) -> Exception:
        if isinstance(exc, httpx.TimeoutException):
            return LLMTimeoutError(
                f"TensorFold {operation} sent nothing for {self._inactivity:.0f}s (a silent server)"
            )
        if isinstance(exc, httpx.ConnectError):
            return TensorFoldUnreachableError(
                f"Failed to connect to TensorFold at {self._base_url}"
            )
        return LLMConnectionError(f"TensorFold {operation} failed: {exc}")

    # ------------------------------------------------------------------ before a request

    async def _in_flight(self) -> int:
        """Requests the server is running or holding, from ``/metrics``. Raises when unreadable."""
        client = await self._get_client()
        try:
            response = await client.get("/metrics", timeout=_PROBE_TIMEOUT_SECONDS)
        except httpx.HTTPError as e:
            raise self._translate(e, "metrics") from e
        if response.status_code != 200:
            raise self._refusal(response, self._default_model)
        gauges = {name: int(value) for name, value in _GAUGE.findall(response.text)}
        if len(gauges) != 2:
            raise LLMConnectionError("TensorFold's /metrics reports no request gauges")
        return gauges["requests_running"] + gauges["requests_waiting"]

    async def _confirm_released(self) -> None:
        """Wait, bounded, for an abandoned request to be gone before anything else is sent (§5.4).
        Unconfirmed is unknown, never quiet: the call raises and the next one waits again."""
        if self._unreleased is None:
            return
        allowed = max(self._unreleased, 0)
        give_up = time.monotonic() + self._release_seconds
        seen: int | None = None
        while True:
            try:
                seen = await self._in_flight()
            except LLMConnectionError:
                seen = None
            if seen is not None and seen <= allowed:
                self._unreleased = None
                return
            if time.monotonic() >= give_up:
                raise LLMConnectionError(
                    f"TensorFold did not release an abandoned request within "
                    f"{self._release_seconds:.0f}s ({seen if seen is not None else 'unreadable'} "
                    f"in flight, {allowed} before it): the server's state is unknown"
                )
            await asyncio.sleep(_RELEASE_POLL_SECONDS)

    async def _verify_window(self, model: str) -> None:
        """Refuse to generate when the registry's window is larger than the one served (§5.3):
        the prompt-size guard would let through prompts the server refuses."""
        if model in self._windows_verified:
            return
        spec = get_model_spec(model)
        client = await self._get_client()
        try:
            response = await client.post(
                "/tokenize", json={"prompt": "x"}, timeout=_PROBE_TIMEOUT_SECONDS
            )
        except httpx.HTTPError as e:
            raise self._translate(e, "window check") from e
        if response.status_code != 200:
            raise self._refusal(response, model)
        served = response.json().get("max_model_len")
        if not isinstance(served, int):
            raise LLMConnectionError("TensorFold's /tokenize reported no max_model_len")
        if spec is not None and spec.context_window > served:
            raise LLMConnectionError(
                f"the registry gives '{model}' a {spec.context_window}-token window and TensorFold "
                f"serves {served}: a deploy defect (the recipe's --context and the registry disagree)"
            )
        self._windows_verified.add(model)

    # ------------------------------------------------------------------ the stream

    async def _frames(self, payload: dict[str, Any], reply: _Reply, deadline: float):
        """Each JSON frame of one streamed call, up to ``[DONE]``, checked as it ends. Anything but
        a complete reply marks the request unreleased, so the next call confirms it is gone."""
        await self._confirm_released()
        await self._verify_window(reply.model)
        try:
            before = await self._in_flight()
        except LLMConnectionError:
            before = -1
        client = await self._get_client()
        accepted = done = False
        try:
            async with client.stream("POST", "/v1/chat/completions", json=payload) as response:
                if response.status_code != 200:
                    # Refused before it ran: nothing on the server to release.
                    await response.aread()
                    raise self._refusal(response, reply.model)
                accepted = True
                async for line in response.aiter_lines():
                    if time.monotonic() > deadline:
                        raise LLMTimeoutError(
                            f"TensorFold's stream for '{reply.model}' passed its deadline"
                        )
                    if not line.startswith("data:"):
                        continue
                    body = line[5:].strip()
                    if body == "[DONE]":
                        reply.finished()
                        done = True
                        return
                    try:
                        frame = json.loads(body)
                    except json.JSONDecodeError:
                        raise reply.fail(f"a frame that is not JSON: {body[:120]!r}") from None
                    yield frame
            raise reply.fail("the stream ended before [DONE]")
        except httpx.HTTPError as e:
            raise self._translate(e, "chat") from e
        finally:
            if accepted and not done:
                self._unreleased = before

    async def chat_stream_with_usage(
        self,
        messages: list[ChatMessage],
        model: str | None = None,
        max_tokens: int | None = None,
        temperature: float | None = None,
        top_p: float | None = None,
        timeout_seconds: float | None = None,
        reasoning: str | None = None,
        seed: int | None = None,
        thinking_budget: int | None = None,
    ) -> ChatMessage:
        """The production path: stream for liveness, return one assembled, checked message."""
        return await self._complete(
            messages,
            model=model,
            max_tokens=max_tokens,
            temperature=temperature,
            top_p=top_p,
            timeout_seconds=timeout_seconds,
            reasoning=reasoning,
            seed=seed,
            thinking_budget=thinking_budget,
        )

    async def _complete(
        self,
        messages: list[ChatMessage],
        *,
        model: str | None,
        max_tokens: int | None,
        temperature: float | None,
        top_p: float | None,
        timeout_seconds: float | None,
        reasoning: str | None,
        seed: int | None,
        thinking_budget: int | None,
    ) -> ChatMessage:
        """One streamed call, assembled and checked: every generation method's one path."""
        resolved = model or self._default_model
        payload = self._payload(
            messages,
            resolved,
            max_tokens,
            temperature,
            top_p,
            reasoning,
            seed=seed,
            thinking_budget=thinking_budget,
        )
        limit = timeout_seconds or self._timeout
        started = time.monotonic()
        reply = _Reply(resolved)
        try:
            # Closed as soon as the loop leaves, by any exit: a frame that raises here must not
            # leave the stream open, and the server generating, until garbage collection.
            async with (
                asyncio.timeout(limit),
                aclosing(self._frames(payload, reply, started + limit)) as frames,
            ):
                async for frame in frames:
                    reply.read(frame)
        except TimeoutError as e:
            raise LLMTimeoutError(
                f"TensorFold chat for '{resolved}' passed its {limit:.0f}s deadline"
            ) from e
        message = reply.message(time.monotonic() - started)
        logger.info(
            "LLM chat_stream_with_usage completed: model=%s, prompt_tokens=%s, "
            "completion_tokens=%s, reasoning_tokens=%s, termination=%s, t/s=%.1f, seed=%s",
            resolved,
            message.prompt_tokens,
            message.completion_tokens,
            message.reasoning_tokens,
            message.termination,
            message.tokens_per_second or 0.0,
            payload["seed"],
        )
        return message

    async def chat(
        self,
        messages: list[ChatMessage],
        model: str | None = None,
        max_tokens: int | None = None,
        temperature: float | None = None,
        top_p: float | None = None,
        timeout_seconds: float | None = None,
        reasoning: str | None = None,
        seed: int | None = None,
        thinking_budget: int | None = None,
    ) -> ChatMessage:
        """Streamed underneath, as every call is: one wire path, one terminal-state check."""
        return await self._complete(
            messages,
            model=model,
            max_tokens=max_tokens,
            temperature=temperature,
            top_p=top_p,
            timeout_seconds=timeout_seconds,
            reasoning=reasoning,
            seed=seed,
            thinking_budget=thinking_budget,
        )

    async def generate(self, request: LLMRequest) -> LLMResponse:
        model = request.model or self._default_model
        message = await self._complete(
            [ChatMessage(role="user", content=request.prompt)],
            model=model,
            max_tokens=request.max_tokens,
            temperature=request.temperature,
            top_p=request.top_p,
            timeout_seconds=request.timeout_seconds,
            reasoning=request.reasoning,
            seed=request.seed,
            thinking_budget=request.thinking_budget,
        )
        return LLMResponse(
            text=message.content,
            model=model,
            prompt_tokens=message.prompt_tokens,
            completion_tokens=message.completion_tokens,
            total_tokens=message.total_tokens,
            tokens_per_second=message.tokens_per_second,
            reasoning_tokens=message.reasoning_tokens,
            reasoning_text=message.reasoning_text,
            prompt_eval_seconds=message.prompt_eval_seconds,
            termination=message.termination,
        )

    async def chat_stream(
        self,
        messages: list[ChatMessage],
        model: str | None = None,
        max_tokens: int | None = None,
        temperature: float | None = None,
        top_p: float | None = None,
        timeout_seconds: float | None = None,
        reasoning: str | None = None,
        seed: int | None = None,
        thinking_budget: int | None = None,
    ) -> AsyncIterator[str]:
        """Content as it arrives. The deadline is checked on every frame, and the inactivity
        timeout bounds a silent server; the stream raises rather than ends short."""
        resolved = model or self._default_model
        payload = self._payload(
            messages,
            resolved,
            max_tokens,
            temperature,
            top_p,
            reasoning,
            seed=seed,
            thinking_budget=thinking_budget,
        )
        reply = _Reply(resolved)
        deadline = time.monotonic() + (timeout_seconds or self._timeout)
        async with aclosing(self._frames(payload, reply, deadline)) as frames:
            async for frame in frames:
                for piece in reply.read(frame):
                    yield piece
        logger.info("LLM chat_stream completed: model=%s, seed=%s", resolved, payload["seed"])

    # ------------------------------------------------------------------ models and residency

    def list_models(self) -> list[str]:
        """Cached names; no I/O, per the port contract."""
        return self._models_cache.copy()

    async def refresh_models(self) -> list[str]:
        try:
            self._models_cache = [m.name for m in await self.list_available_models()]
        except Exception:
            logger.debug("TensorFold model refresh failed; keeping the last known list")
        return self._models_cache.copy()

    async def _model_ids(self) -> list[str]:
        client = await self._get_client()
        try:
            response = await client.get("/v1/models", timeout=_PROBE_TIMEOUT_SECONDS)
        except httpx.HTTPError as e:
            raise self._translate(e, "model listing") from e
        if response.status_code != 200:
            raise self._refusal(response, self._default_model)
        return [i for entry in response.json().get("data", []) if (i := entry.get("id"))]

    async def list_available_models(self) -> list[ModelInfo]:
        """The served id and its aliases, as ``/v1/models`` lists them, each with its frozen
        recipe's weights as the digest (#2561). An id without a recipe reports none."""
        return [
            ModelInfo(name=i, digest=r.weights if (r := RECIPES.get(i)) else None)
            for i in await self._model_ids()
        ]

    async def list_loaded_models(self) -> list[ModelInfo]:
        """One resident model, whatever aliases it answers to (§5.5): the server lists its served
        id first and its aliases after it. The drafter is part of the recipe, not a model."""
        ids = await self._model_ids()
        return [ModelInfo(name=ids[0])] if ids else []

    async def requests_in_flight(self) -> int:
        """The requests TensorFold is running or holding now, from its authenticated ``/metrics``
        (§5.5). Unreadable raises: the launch gate reads that as an unread engine, never quiet."""
        return await self._in_flight()

    async def residency(self) -> str:
        """The server's state from authenticated sources only (§5.5)."""
        try:
            ids = await self._model_ids()
            in_flight = await self._in_flight()
        except TensorFoldUnauthorizedError:
            return Residency.UNAUTHORIZED
        except TensorFoldUnreachableError:
            return Residency.UNREACHABLE
        except Exception:  # noqa: BLE001 — anything else read is unknown, never quiet
            return Residency.UNKNOWN
        if self._default_model not in ids:
            return Residency.UNKNOWN
        return Residency.IDLE if in_flight == 0 else Residency.BUSY

    async def health(self) -> dict[str, Any]:
        """Never raises. Healthy means authenticated and serving the expected model."""
        state = await self.residency()
        return {
            "healthy": state in (Residency.IDLE, Residency.BUSY),
            "state": state,
            "base_url": self._base_url,
            "model": self._default_model,
        }

    async def close(self) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None
