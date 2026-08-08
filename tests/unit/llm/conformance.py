"""Shared machinery for the LLM port conformance suite (SIP-Atlas-Provider-Adapter P3).

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

from adapters.llm.ollama import OllamaAdapter
from squadops.ports.llm.provider import LLMPort

# A dialect handler answers a request the way its provider's server would.
DialectHandler = Callable[[httpx.Request], httpx.Response]


@dataclass(frozen=True)
class AdapterCase:
    """One provider under conformance test.

    ``build`` returns a fresh adapter; ``ok`` answers requests the way a healthy
    server of that dialect would. Registering a second provider means adding one
    of these — no shared assertion changes.
    """

    name: str
    build: Callable[[], LLMPort]
    ok: DialectHandler

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
                    "message": {"role": "assistant", "content": OLLAMA_CONTENT},
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
    ),
]

# Expected tokens/sec for a case's `ok` handler. Keyed by adapter name because the
# rate is computed from provider-supplied timings, which are dialect-shaped.
EXPECTED_TOKENS_PER_SECOND = {"ollama": 6.0}
EXPECTED_COMPLETION_TOKENS = {"ollama": _EVAL_COUNT}
EXPECTED_PROMPT_TOKENS = {"ollama": _PROMPT_EVAL_COUNT}
EXPECTED_MODELS = {"ollama": OLLAMA_MODELS}
EXPECTED_CONTENT = {"ollama": OLLAMA_CONTENT}
