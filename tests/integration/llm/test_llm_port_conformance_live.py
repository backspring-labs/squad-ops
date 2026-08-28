"""Live-tier LLM port conformance (Atlas Provider Adapter SIP, SIP-0106, P3).

The unit tier (``tests/unit/llm/test_llm_port_conformance.py``) proves an adapter
parses a *fixture* correctly. This tier points the same contract at a **real
server** and is the harness P4/P5 run against Atlas — unchanged, by pointing the
env vars somewhere else:

    SQUADOPS_CONFORMANCE_PROVIDER=ollama \\
    SQUADOPS_CONFORMANCE_BASE_URL=http://localhost:11434 \\
    SQUADOPS_CONFORMANCE_MODEL=qwen2.5:3b-instruct \\
    pytest tests/integration/llm -v

Skipped entirely when those are unset, so it never blocks a normal run.

**Assertions here are property-shaped, not value-shaped.** A live server's model
list, token counts, and latencies are not knowable in advance, so this tier
checks the invariants that must hold for *any* conforming provider. That is
precisely what makes the file reusable against Atlas rather than a second Ollama
test.

**Nothing here mutates the box.** ``pull_model``/``delete_model`` are declared by
Ollama and deliberately not exercised: a conformance run must never delete an
operator's weights or spend minutes pulling gigabytes. Their honesty is covered
at the unit tier, where it costs nothing.
"""

from __future__ import annotations

import os

import pytest

from squadops.llm.exceptions import LLMConnectionError, LLMModelNotFoundError
from squadops.llm.models import ChatMessage, LLMRequest, ModelInfo
from squadops.ports.llm.provider import LLMCapability

pytestmark = pytest.mark.integration

PROVIDER = os.getenv("SQUADOPS_CONFORMANCE_PROVIDER", "")
BASE_URL = os.getenv("SQUADOPS_CONFORMANCE_BASE_URL", "")
MODEL = os.getenv("SQUADOPS_CONFORMANCE_MODEL", "")

requires_live_provider = pytest.mark.skipif(
    not (PROVIDER and BASE_URL and MODEL),
    reason=(
        "live conformance needs SQUADOPS_CONFORMANCE_PROVIDER, _BASE_URL and _MODEL; "
        "see this module's docstring"
    ),
)

# Keep generations short: this is a contract check, not a benchmark. On a
# bandwidth-bound box an unbounded completion turns a test run into a coffee break.
MAX_TOKENS = 16
TIMEOUT_SECONDS = 120.0

# A rate this far outside plausibility is a unit error, not a fast machine. The
# ns/s conversion bug this guards against lands ~1e9 out, so the window can be
# generous and still catch it.
MIN_PLAUSIBLE_TPS = 0.01
MAX_PLAUSIBLE_TPS = 100_000.0


@pytest.fixture
def adapter():
    """Build the adapter under test from the environment, via the factory.

    Going through ``create_llm_provider`` rather than importing a concrete class
    is the point: this file names no vendor, so P4 registers Atlas in the factory
    and this tier runs against it with no edit here.

    **Function-scoped deliberately.** Adapters cache an ``httpx.AsyncClient``, and
    a client is bound to the event loop that created it. With
    ``asyncio_default_fixture_loop_scope=function`` (pyproject), a module-scoped
    adapter hands every test after the first a client whose loop is closed —
    ``RuntimeError: Event loop is closed``. Worse, ``refresh_models`` swallows it
    in its blanket ``except`` and returns an empty cache, so the failure
    *presents* as "the backend listed no models." A fresh adapter per test costs
    one connection and removes the whole class.
    """
    from adapters.llm.factory import create_llm_provider

    return create_llm_provider(
        provider=PROVIDER,
        base_url=BASE_URL,
        default_model=MODEL,
        timeout_seconds=TIMEOUT_SECONDS,
    )


def _messages() -> list[ChatMessage]:
    return [
        ChatMessage(role="system", content="Answer with a single word."),
        ChatMessage(role="user", content="Say hello."),
    ]


@requires_live_provider
class TestLiveGeneration:
    async def test_generate_returns_text(self, adapter):
        response = await adapter.generate(
            LLMRequest(prompt="Say hello.", max_tokens=MAX_TOKENS, temperature=0.0)
        )
        assert response.text.strip(), "a live generation returned no text"
        assert response.model

    async def test_chat_returns_assistant_content(self, adapter):
        message = await adapter.chat(_messages(), max_tokens=MAX_TOKENS, temperature=0.0)
        assert message.role == "assistant"
        assert message.content.strip()

    async def test_chat_stream_yields_incremental_content(self, adapter):
        """Real streaming, real framing. The unit tier proves an adapter parses a
        canned stream; only a live server proves it parses *this* server's."""
        chunks = [
            chunk
            async for chunk in adapter.chat_stream(
                _messages(), max_tokens=MAX_TOKENS, temperature=0.0
            )
        ]
        assert chunks, "live stream yielded nothing"
        assert "".join(chunks).strip()

    async def test_chat_stream_with_usage_assembles_content(self, adapter):
        message = await adapter.chat_stream_with_usage(
            _messages(), max_tokens=MAX_TOKENS, temperature=0.0
        )
        assert message.role == "assistant"
        assert message.content.strip()


@requires_live_provider
class TestLiveUsageAccounting:
    """The numbers the Atlas A/B is decided on. A provider whose accounting is
    wrong produces a comparison that is wrong rather than merely unflattering."""

    async def test_counts_are_consistent_or_wholly_absent(self, adapter):
        message = await adapter.chat(_messages(), max_tokens=MAX_TOKENS, temperature=0.0)

        reported = [message.prompt_tokens, message.completion_tokens, message.total_tokens]
        if all(v is None for v in reported):
            pytest.skip("provider reports no usage; nothing to check for consistency")

        assert all(v is not None for v in reported), (
            f"partial usage is worse than none — a caller cannot tell which half "
            f"is real: {reported}"
        )
        assert message.completion_tokens > 0
        assert message.total_tokens == message.prompt_tokens + message.completion_tokens

    async def test_tokens_per_second_is_within_physical_plausibility(self, adapter):
        """Catches live what the unit tier catches with a fixture: a duration-unit
        error still yields a well-formed float, just one ~1e9 out."""
        message = await adapter.chat(_messages(), max_tokens=MAX_TOKENS, temperature=0.0)

        if message.tokens_per_second is None:
            pytest.skip("provider does not report a generation rate")

        assert MIN_PLAUSIBLE_TPS < message.tokens_per_second < MAX_PLAUSIBLE_TPS, (
            f"{message.tokens_per_second} t/s is outside physical plausibility — "
            f"almost certainly a duration-unit conversion error"
        )

    async def test_streaming_reports_usage_when_declared(self, adapter):
        """`streaming_usage: True` promises real counts, not the port's silent
        fallback to chat(). Declaring it and returning nothing is the #572 class."""
        if not adapter.supports(LLMCapability.STREAMING_USAGE):
            pytest.skip("streaming_usage not declared")

        message = await adapter.chat_stream_with_usage(
            _messages(), max_tokens=MAX_TOKENS, temperature=0.0
        )
        assert message.completion_tokens is not None
        assert message.completion_tokens > 0


@requires_live_provider
class TestLiveModelListing:
    async def test_listing_declaration_matches_a_real_backend(self, adapter):
        if not adapter.supports(LLMCapability.MODEL_LISTING):
            with pytest.raises(NotImplementedError):
                await adapter.list_available_models()
            return

        models = await adapter.list_available_models()
        assert models, "a reachable backend declaring model_listing listed nothing"
        assert all(isinstance(m, ModelInfo) for m in models)
        assert all(m.name.strip() for m in models), "blank model name surfaced from a live list"

    async def test_the_configured_model_is_actually_present(self, adapter):
        """The check a cycle's preflight is really asking. Passing generation
        tests while the configured model is absent from the listing means the
        two disagree — and the preflight is the one that blocks work."""
        if not adapter.supports(LLMCapability.MODEL_LISTING):
            pytest.skip("model_listing not declared")

        names = {m.name for m in await adapter.list_available_models()}
        assert MODEL in names, (
            f"configured model {MODEL!r} is not in the live listing: {sorted(names)}"
        )

    async def test_refresh_agrees_with_the_metadata_listing(self, adapter):
        """Two listing surfaces, one backend. Divergence means a caller's answer
        depends on which method it happened to call."""
        if not adapter.supports(LLMCapability.MODEL_LISTING):
            pytest.skip("model_listing not declared")

        assert set(await adapter.refresh_models()) == {
            m.name for m in await adapter.list_available_models()
        }


@requires_live_provider
class TestLiveErrorTranslation:
    """Real error bodies, not fixtures. Locus classification (#568) reads these
    types; an adapter that leaks a raw transport error against a real server
    reclassifies an outage as a work-product defect."""

    async def test_unknown_model_raises_model_not_found(self, adapter):
        with pytest.raises(LLMModelNotFoundError):
            await adapter.chat(
                _messages(),
                model="definitely-not-a-real-model:v0",
                max_tokens=MAX_TOKENS,
            )

    async def test_unreachable_backend_raises_connection_error(self):
        """A closed port on localhost — the real refused-connection path, which
        no fixture reproduces faithfully."""
        from adapters.llm.factory import create_llm_provider

        dead = create_llm_provider(
            provider=PROVIDER,
            base_url="http://127.0.0.1:9",  # discard port: nothing listens
            default_model=MODEL,
            timeout_seconds=5.0,
        )
        with pytest.raises(LLMConnectionError):
            await dead.chat(_messages(), max_tokens=MAX_TOKENS)


@requires_live_provider
class TestLiveHealth:
    async def test_health_reports_healthy_against_the_real_backend(self, adapter):
        assert (await adapter.health())["healthy"] is True

    async def test_health_reports_unhealthy_without_raising(self):
        from adapters.llm.factory import create_llm_provider

        dead = create_llm_provider(
            provider=PROVIDER,
            base_url="http://127.0.0.1:9",
            default_model=MODEL,
            timeout_seconds=5.0,
        )
        assert (await dead.health())["healthy"] is False
