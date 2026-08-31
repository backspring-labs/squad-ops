"""Shared machinery for the LLM port conformance suite (Atlas Provider Adapter SIP, SIP-0106, P3).

Not a test module — imported by ``test_llm_port_conformance.py``.

**What this is.** One behavioral suite that every ``LLMPort`` adapter must pass.
With a single live provider it *characterizes* the current contract; it becomes a
conformance suite the moment a second adapter is registered. The 1.5 stabilization
plan asked for exactly this distinction and was explicit about the trap:

    it must declare semantic capabilities ... as required/optional/extension per
    provider — **not** enshrine Ollama transport behavior as the contract.

So the assertions live in the shared suite and speak only the *port's* vocabulary.
Everything provider-shaped — routes, payload keys, streaming framing — is confined
to an :class:`AdapterCase`'s dialect handler. Adding an adapter is one registry
entry, never a new test.

**Why the wire is mocked at the transport, not at the adapter.** The neighbouring
Ollama tests patch ``_get_client``, which is fine for testing *that* adapter and
useless for a shared suite: it presumes a private method every adapter must happen
to have. ``httpx.MockTransport`` intercepts one layer lower, so the adapter's real
URL construction, payload shaping, response parsing, and error mapping all execute.
That is the code conformance is actually about.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from unittest.mock import patch

import httpx

from adapters.llm.atlas import AtlasAdapter
from adapters.llm.ollama import OllamaAdapter
from adapters.llm.vllm import VLLMAdapter
from squadops.ports.llm.provider import LLMPort

# A dialect handler answers a request the way its provider's server would.
DialectHandler = Callable[[httpx.Request], httpx.Response]


@dataclass(frozen=True)
class AdapterCase:
    """One provider under conformance test.

    ``build`` returns a fresh adapter; ``ok`` answers requests the way a healthy
    server of that dialect would; ``nameless_model`` answers a listing request
    with an entry carrying no usable name. Registering a second provider means
    adding one of these — no shared assertion changes.
    """

    name: str
    build: Callable[[], LLMPort]
    ok: DialectHandler
    nameless_model: DialectHandler

    # Expectations for this provider's `ok` handler. On the case rather than in
    # parallel name-keyed dicts: one entry fully describes a provider, so adding
    # Atlas is one object and no shared assertion learns a new name.
    default_model: str
    override_model: str
    models: list[str]
    content: str
    prompt_tokens: int
    completion_tokens: int
    # Exact rate when the provider reports timings; None when the adapter derives
    # it from wall-clock, which is machine-dependent and range-checked instead.
    tokens_per_second: float | None
    # A model the registry declares a reasoning dial for (#927). The reasoning
    # assertion needs one: an adapter that maps by the model's dial sends nothing
    # for a dial-less model, which is the contract, not a defect.
    reasoning_model: str
    #: #410: the text this provider's ``ok`` handler returns in its reasoning channel,
    #: whatever the dialect calls that field. None for a dialect that has no such
    #: channel — the port must then report None, not "".
    reasoning_text: str | None

    def __str__(self) -> str:  # pytest id
        return self.name


class Wire:
    """The live backend for a test, swappable mid-test.

    Indirection rather than re-patching, because adapters cache their client:
    once ``_get_client`` has built one, entering a second ``patch`` block does
    nothing and a "now the backend fails" assertion silently keeps talking to the
    healthy transport. Mutation testing caught exactly that — a cache-preservation
    test that passed against an adapter which emptied its cache on failure.

    One transport for the whole test, dispatching to whatever handler is current,
    is immune to that regardless of how an adapter manages connections.
    """

    def __init__(self, handler: DialectHandler) -> None:
        self._handler = handler

    def set(self, handler: DialectHandler) -> None:
        """Swap the backend behavior. Takes effect on the next request."""
        self._handler = handler

    def __call__(self, request: httpx.Request) -> httpx.Response:
        return self._handler(request)


@contextmanager
def wire(handler: DialectHandler) -> Iterator[Wire]:
    """Route every ``httpx.AsyncClient`` built inside the block through ``handler``.

    Patching the class rather than the adapter keeps this provider-agnostic: any
    httpx-based adapter is intercepted without the suite knowing how it stores or
    creates its client. Yields the :class:`Wire` so a test can change backend
    behavior part-way through.
    """
    live = Wire(handler)
    real = httpx.AsyncClient

    def factory(*args, **kwargs):
        kwargs["transport"] = httpx.MockTransport(live)
        return real(*args, **kwargs)

    with patch("httpx.AsyncClient", factory):
        yield live


def raises(exc: Exception) -> DialectHandler:
    """A dialect handler whose transport fails — connect errors, timeouts."""

    def handler(request: httpx.Request) -> httpx.Response:
        raise exc

    return handler


def status(code: int, body: dict | None = None) -> DialectHandler:
    """A dialect handler that answers every route with one status."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(code, json=body if body is not None else {})

    return handler


# ---------------------------------------------------------------------------
# Ollama dialect
#
# Everything Ollama-specific in the suite lives here: route paths, payload keys,
# NDJSON stream framing, nanosecond durations. The shared assertions never see
# any of it.
# ---------------------------------------------------------------------------

OLLAMA_MODELS = ["qwen2.5:7b", "llama3.2"]
OLLAMA_CONTENT = "the assembled answer"

# Split so a streaming assertion proves reassembly rather than a single passthrough.
# The last part rides the terminal `done` frame, which is how Ollama actually
# behaves and is load-bearing for the test: with an empty done-frame an adapter
# that ignores its content passes anyway. Mutation testing found that hole.
OLLAMA_STREAM_PARTS = ["the ", "assembled "]
OLLAMA_STREAM_FINAL_PART = "answer"

# 12 tokens over 2s. Chosen so tokens/sec is exactly 6.0 — an adapter that divides
# by the wrong unit lands orders of magnitude away, not fractionally.
_EVAL_COUNT = 12
_EVAL_DURATION_NS = 2_000_000_000
_PROMPT_EVAL_COUNT = 5


def _ollama_usage() -> dict:
    return {
        "prompt_eval_count": _PROMPT_EVAL_COUNT,
        "eval_count": _EVAL_COUNT,
        "eval_duration": _EVAL_DURATION_NS,
    }


def ollama_ok(request: httpx.Request) -> httpx.Response:
    """Answer as a healthy Ollama server."""
    path = request.url.path

    if path == "/api/tags":
        return httpx.Response(200, json={"models": [{"name": m} for m in OLLAMA_MODELS]})

    if path in ("/api/pull", "/api/delete"):
        return httpx.Response(200, json={"status": "success"})

    if path == "/api/generate":
        return httpx.Response(
            200,
            json={
                "response": OLLAMA_CONTENT,
                "model": json.loads(request.content)["model"],
                **_ollama_usage(),
            },
        )

    if path == "/api/chat":
        streaming = json.loads(request.content).get("stream", False)
        if not streaming:
            return httpx.Response(
                200,
                json={
                    "message": {
                        "role": "assistant",
                        "content": OLLAMA_CONTENT,
                        "thinking": OLLAMA_THINKING,
                    },
                    **_ollama_usage(),
                },
            )
        # NDJSON: content frames, then a terminal `done` frame carrying both the
        # final content fragment and the usage totals.
        lines = [
            json.dumps({"message": {"role": "assistant", "content": part}, "done": False})
            for part in OLLAMA_STREAM_PARTS
        ]
        lines.append(
            json.dumps(
                {
                    "message": {"role": "assistant", "content": OLLAMA_STREAM_FINAL_PART},
                    "done": True,
                    **_ollama_usage(),
                }
            )
        )
        return httpx.Response(200, content=("\n".join(lines) + "\n").encode())

    return httpx.Response(404, json={"error": f"unexpected route {path}"})


def ollama_nameless_model(request: httpx.Request) -> httpx.Response:
    """A listing whose single entry has no usable name.

    Real servers do return junk rows; the port contract is that an unnamed model
    is dropped rather than surfaced as an empty-named one.
    """
    if request.url.path == "/api/tags":
        return httpx.Response(200, json={"models": [{"size": 42, "modified_at": "2026-01-01"}]})
    return ollama_ok(request)


# ---------------------------------------------------------------------------
# vLLM dialect — OpenAI-compatible
#
# Shaped from a live OpenAI-compatible server, not from documentation: SSE
# `data: {json}` frames terminated by `data: [DONE]`, `choices[0].delta.content`
# while streaming and `choices[0].message.content` when not, `/v1/models`
# returning entries keyed on `id`, and a 404 with an `{"error": {...}}` body for
# an unknown model.
# ---------------------------------------------------------------------------

VLLM_MODELS = ["Qwen/Qwen2.5-7B-Instruct", "meta-llama/Llama-3.2-3B-Instruct"]
VLLM_CONTENT = "the assembled answer"
#: #410: what each dialect returns in its reasoning channel, under the field name that
#: dialect uses. The port must surface all three as ``reasoning_text``.
OLLAMA_THINKING = "ollama thought this, in message.thinking"
VLLM_REASONING = "vllm thought this, in message.reasoning_content"
ATLAS_REASONING = "thinking, separately"
VLLM_STREAM_PARTS = ["the ", "assembled ", "answer"]

# The usage frame rides its own terminal chunk (stream_options.include_usage),
# separate from the content frames — a real structural difference from Ollama's
# NDJSON, where usage shares the final content frame.
_VLLM_PROMPT_TOKENS = 5
_VLLM_COMPLETION_TOKENS = 12


def _vllm_usage() -> dict:
    return {
        "prompt_tokens": _VLLM_PROMPT_TOKENS,
        "completion_tokens": _VLLM_COMPLETION_TOKENS,
        "total_tokens": _VLLM_PROMPT_TOKENS + _VLLM_COMPLETION_TOKENS,
    }


def _sse(frames: list[dict]) -> bytes:
    body = "".join(f"data: {json.dumps(f)}\n\n" for f in frames)
    return (body + "data: [DONE]\n\n").encode()


def vllm_ok(request: httpx.Request) -> httpx.Response:
    """Answer as a healthy vLLM server."""
    path = request.url.path

    if path == "/v1/models":
        return httpx.Response(
            200,
            json={"object": "list", "data": [{"id": m, "object": "model"} for m in VLLM_MODELS]},
        )

    if path == "/v1/chat/completions":
        body = json.loads(request.content)
        model = body["model"]
        if not body.get("stream"):
            return httpx.Response(
                200,
                json={
                    "id": "chatcmpl-1",
                    "model": model,
                    "choices": [
                        {
                            "index": 0,
                            "message": {
                                "role": "assistant",
                                "content": VLLM_CONTENT,
                                "reasoning_content": VLLM_REASONING,
                            },
                        }
                    ],
                    "usage": _vllm_usage(),
                },
            )
        frames = [
            {"choices": [{"index": 0, "delta": {"role": "assistant", "content": part}}]}
            for part in VLLM_STREAM_PARTS
        ]
        frames.append({"choices": [], "usage": _vllm_usage()})
        return httpx.Response(200, content=_sse(frames))

    return httpx.Response(404, json={"error": {"message": f"unexpected route {path}"}})


def vllm_nameless_model(request: httpx.Request) -> httpx.Response:
    """A listing entry with no usable id."""
    if request.url.path == "/v1/models":
        return httpx.Response(200, json={"object": "list", "data": [{"object": "model"}]})
    return vllm_ok(request)


# ---------------------------------------------------------------------------
# Atlas dialect — the shapes measured on the Spark on 2026-08-28 (SIP-0106 §10.2).
# ---------------------------------------------------------------------------

ATLAS_MODELS = ["Qwen/Qwen3.8-27B-FP8"]
ATLAS_CONTENT = "the assembled answer"
ATLAS_STREAM_PARTS = ["the ", "assembled ", "answer"]
ATLAS_TOKEN = "test-bearer-token"
_ATLAS_PROMPT_TOKENS = 20
_ATLAS_COMPLETION_TOKENS = 40
_ATLAS_REASONING_TOKENS = 12
_ATLAS_TPS = 12.78


def _atlas_usage() -> dict:
    return {
        "prompt_tokens": _ATLAS_PROMPT_TOKENS,
        "completion_tokens": _ATLAS_COMPLETION_TOKENS,
        "total_tokens": _ATLAS_PROMPT_TOKENS + _ATLAS_COMPLETION_TOKENS,
        "prompt_tokens_details": {"cached_tokens": 0, "audio_tokens": 0},
        "completion_tokens_details": {"reasoning_tokens": _ATLAS_REASONING_TOKENS},
        "time_to_first_token_ms": 153.2,
        "response_token/s": _ATLAS_TPS,
    }


def atlas_ok(request: httpx.Request) -> httpx.Response:
    """Answer as the live Atlas did: bearer-gated, reasoning in its own field, the
    engine's own decode rate in usage, and the streaming usage on an empty-choices frame."""
    if request.headers.get("Authorization") != f"Bearer {ATLAS_TOKEN}":
        return httpx.Response(401, json={"error": {"message": "unauthorized"}})
    path = request.url.path

    if path == "/v1/models":
        return httpx.Response(
            200,
            json={
                "object": "list",
                "data": [
                    {
                        "id": m,
                        "object": "model",
                        "created": 0,
                        "owned_by": "atlas",
                        "max_model_len": 32768,
                    }
                    for m in ATLAS_MODELS
                ],
            },
        )

    if path == "/v1/chat/completions":
        body = json.loads(request.content)
        model = body["model"]
        if body.get("reasoning_effort") == "high":  # the served template's answer, measured
            return httpx.Response(
                400,
                json={
                    "error": {
                        "message": "Unexpected reasoning effort high. Supported types are xhigh (default), medium, and low."
                    }
                },
            )
        if not body.get("stream"):
            return httpx.Response(
                200,
                json={
                    "id": "chatcmpl-1",
                    "model": model,
                    "system_fingerprint": "fp_atlas",
                    "choices": [
                        {
                            "index": 0,
                            "message": {
                                "role": "assistant",
                                "reasoning_content": ATLAS_REASONING,
                                "content": ATLAS_CONTENT,
                            },
                            "finish_reason": "stop",
                        }
                    ],
                    "usage": _atlas_usage(),
                },
            )
        frames: list[dict] = [{"choices": [{"index": 0, "delta": {"role": "assistant"}}]}]
        frames.append({"choices": [{"index": 0, "delta": {"reasoning_content": "thinking, "}}]})
        frames.extend(
            {"choices": [{"index": 0, "delta": {"content": part}}]} for part in ATLAS_STREAM_PARTS
        )
        frames.append({"choices": [], "usage": _atlas_usage()})
        frames.append({"choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}]})
        return httpx.Response(200, content=_sse(frames))

    return httpx.Response(404, json={"error": {"message": "not found"}})


def atlas_nameless_model(request: httpx.Request) -> httpx.Response:
    if (
        request.url.path == "/v1/models"
        and request.headers.get("Authorization") == f"Bearer {ATLAS_TOKEN}"
    ):
        return httpx.Response(200, json={"object": "list", "data": [{"object": "model"}]})
    return atlas_ok(request)


# ---------------------------------------------------------------------------
# The registry — one entry per adapter under conformance.
#
# Atlas (P4) and vLLM (P6) each land here as one AdapterCase with their own
# dialect handler. No shared assertion changes.
# ---------------------------------------------------------------------------

ADAPTER_CASES: list[AdapterCase] = [
    AdapterCase(
        name="ollama",
        build=lambda: OllamaAdapter(default_model="qwen2.5:7b", timeout_seconds=5.0),
        ok=ollama_ok,
        nameless_model=ollama_nameless_model,
        default_model="qwen2.5:7b",
        override_model="llama3.2",
        models=OLLAMA_MODELS,
        content=OLLAMA_CONTENT,
        prompt_tokens=_PROMPT_EVAL_COUNT,
        completion_tokens=_EVAL_COUNT,
        tokens_per_second=6.0,  # exact: derived from reported ns timings
        reasoning_model="qwen3.6:27b",
        reasoning_text=OLLAMA_THINKING,
    ),
    AdapterCase(
        name="vllm",
        build=lambda: VLLMAdapter(
            base_url="http://localhost:8000",
            default_model="Qwen/Qwen2.5-7B-Instruct",
            timeout_seconds=5.0,
        ),
        ok=vllm_ok,
        nameless_model=vllm_nameless_model,
        default_model="Qwen/Qwen2.5-7B-Instruct",
        override_model="meta-llama/Llama-3.2-3B-Instruct",
        models=VLLM_MODELS,
        content=VLLM_CONTENT,
        prompt_tokens=_VLLM_PROMPT_TOKENS,
        completion_tokens=_VLLM_COMPLETION_TOKENS,
        tokens_per_second=None,  # wall-clock derived; no timing field in the shape
        # The registry is keyed on the name the adapter is handed; a real vLLM
        # serves HF paths, whose entries are #1145/#1159's to add.
        reasoning_model="qwen3.6:27b",
        reasoning_text=VLLM_REASONING,
    ),
    AdapterCase(
        name="atlas",
        build=lambda: AtlasAdapter(
            base_url="http://localhost:8888",
            default_model="Qwen/Qwen3.8-27B-FP8",
            timeout_seconds=5.0,
            api_key=ATLAS_TOKEN,
        ),
        ok=atlas_ok,
        nameless_model=atlas_nameless_model,
        default_model="Qwen/Qwen3.8-27B-FP8",
        override_model="Qwen/Qwen3.8-27B-FP8",
        models=ATLAS_MODELS,
        content=ATLAS_CONTENT,
        prompt_tokens=_ATLAS_PROMPT_TOKENS,
        completion_tokens=_ATLAS_COMPLETION_TOKENS,
        tokens_per_second=_ATLAS_TPS,  # exact: the engine's own `response_token/s`
        reasoning_model="Qwen/Qwen3.8-27B-FP8",
        reasoning_text=ATLAS_REASONING,
    ),
]

# Expected tokens/sec for a case's `ok` handler. Keyed by adapter name because the
# rate is computed from provider-supplied timings, which are dialect-shaped.
