"""LLM port conformance suite (SIP-Atlas-Provider-Adapter P3).

Every registered adapter runs the same assertions. Shared machinery, the dialect
handlers, and the registry live in ``conformance.py``; see its docstring for why
the wire is mocked at the transport rather than at the adapter.

**These tests speak only the port's vocabulary.** No assertion below names a route,
a payload key, or a streaming format. When Atlas registers (P4), it either satisfies
these or it is not a conforming adapter — which is the whole point: the contract is
decided here, once, rather than rediscovered per provider.

Dimensions not yet expressible are deliberately absent rather than stubbed:
``capabilities()`` honesty and listing-vs-absence need P0/P1's port surface. They
join this file when that surface lands.
"""

from __future__ import annotations

import httpx
import pytest

from squadops.llm.exceptions import (
    LLMConnectionError,
    LLMModelNotFoundError,
    LLMTimeoutError,
)
from squadops.llm.models import ChatMessage, LLMRequest, ModelInfo
from squadops.ports.llm.provider import LLMCapability
from tests.unit.llm.conformance import (
    ADAPTER_CASES,
    EXPECTED_COMPLETION_TOKENS,
    EXPECTED_CONTENT,
    EXPECTED_MODELS,
    EXPECTED_PROMPT_TOKENS,
    EXPECTED_TOKENS_PER_SECOND,
    raises,
    status,
    wire,
)

pytestmark = pytest.mark.parametrize("case", ADAPTER_CASES, ids=str)


def _messages() -> list[ChatMessage]:
    return [
        ChatMessage(role="system", content="be terse"),
        ChatMessage(role="user", content="the question"),
    ]


class TestGeneration:
    """The port's two generation entry points return the declared shape."""

    async def test_generate_returns_text_and_echoes_resolved_model(self, case):
        """A response attributed to the wrong model makes per-model cost and
        throughput accounting silently wrong — every downstream number is keyed
        on it."""
        with wire(case.ok):
            response = await case.build().generate(LLMRequest(prompt="the question"))

        assert response.text == EXPECTED_CONTENT[case.name]
        assert response.model == "qwen2.5:7b"

    async def test_chat_returns_assistant_role_and_content(self, case):
        with wire(case.ok):
            message = await case.build().chat(_messages())

        assert message.role == "assistant"
        assert message.content == EXPECTED_CONTENT[case.name]

    async def test_chat_stream_reassembles_to_the_same_content(self, case):
        """Streaming is a transport detail; callers must not be able to tell.
        An adapter that drops the first or last frame — an off-by-one in its
        chunk loop — passes a "yields something" check and fails this one."""
        chunks: list[str] = []
        with wire(case.ok):
            async for chunk in case.build().chat_stream(_messages()):
                chunks.append(chunk)

        assert len(chunks) > 1, "single chunk cannot demonstrate reassembly"
        assert "".join(chunks) == EXPECTED_CONTENT[case.name]

    async def test_chat_stream_with_usage_returns_whole_message_not_chunks(self, case):
        """The streaming-for-liveness path: stream the wire to hold the
        connection open on long generations, hand back one assembled message."""
        with wire(case.ok):
            message = await case.build().chat_stream_with_usage(_messages())

        assert message.role == "assistant"
        assert message.content == EXPECTED_CONTENT[case.name]


class TestUsageAccounting:
    """Token accounting feeds LangFuse cost tracking and the Atlas A/B. Partial
    or zero-filled counts are worse than absent ones — they look like data."""

    @pytest.mark.parametrize("via", ["chat", "stream_with_usage"])
    async def test_counts_are_present_and_internally_consistent(self, case, via):
        with wire(case.ok):
            adapter = case.build()
            message = await (
                adapter.chat(_messages())
                if via == "chat"
                else adapter.chat_stream_with_usage(_messages())
            )

        assert message.prompt_tokens == EXPECTED_PROMPT_TOKENS[case.name]
        assert message.completion_tokens == EXPECTED_COMPLETION_TOKENS[case.name]
        assert message.total_tokens == message.prompt_tokens + message.completion_tokens

    @pytest.mark.parametrize("via", ["chat", "stream_with_usage"])
    async def test_tokens_per_second_is_a_rate_not_a_count(self, case, via):
        """Throughput is the Atlas migration's decision number. A unit error in
        the duration conversion — nanoseconds read as seconds — yields a value
        off by a factor of 1e9 while still being a plausible-looking float."""
        with wire(case.ok):
            adapter = case.build()
            message = await (
                adapter.chat(_messages())
                if via == "chat"
                else adapter.chat_stream_with_usage(_messages())
            )

        assert message.tokens_per_second == EXPECTED_TOKENS_PER_SECOND[case.name]

    async def test_generate_reports_the_same_usage_as_chat(self, case):
        """Two entry points, one accounting contract. An adapter that populates
        usage on chat and forgets it on generate produces a silently partial
        cost picture that depends on which handler ran."""
        with wire(case.ok):
            response = await case.build().generate(LLMRequest(prompt="the question"))

        assert response.prompt_tokens == EXPECTED_PROMPT_TOKENS[case.name]
        assert response.completion_tokens == EXPECTED_COMPLETION_TOKENS[case.name]
        assert response.total_tokens == response.prompt_tokens + response.completion_tokens

    async def test_usage_absent_from_the_wire_is_none_never_zero(self, case):
        """A provider that omits usage must yield None, not 0. Zero is a lie the
        cost dashboards cannot distinguish from a free call, and it silently
        drags any average toward zero."""
        with wire(status(200, {"message": {"role": "assistant", "content": "hi"}})):
            message = await case.build().chat(_messages())

        assert message.prompt_tokens is None
        assert message.completion_tokens is None
        assert message.total_tokens is None
        assert message.tokens_per_second is None


class TestModelListing:
    """``list_models`` is sync and cached; ``refresh_models`` performs the I/O."""

    async def test_refresh_populates_the_cache_read_by_list_models(self, case):
        with wire(case.ok):
            adapter = case.build()
            assert adapter.list_models() == [], "cache must start empty, not pre-populated"
            refreshed = await adapter.refresh_models()

        assert refreshed == EXPECTED_MODELS[case.name]
        assert adapter.list_models() == EXPECTED_MODELS[case.name]

    async def test_list_models_performs_no_network_io(self, case):
        """The port documents this as a MUST NOT and nothing tested it. A sync
        method that reaches the network blocks the event loop for every caller on
        that thread — an outage-shaped bug, not a slow one.

        Enforced by making the transport fatal *while the adapter's client is
        already live*: any request from here on raises."""
        with wire(case.ok) as live:
            adapter = case.build()
            await adapter.refresh_models()

            live.set(raises(AssertionError("list_models() performed network I/O")))
            assert adapter.list_models() == EXPECTED_MODELS[case.name]

    async def test_list_models_returns_a_copy(self, case):
        """Handing out the internal list lets any caller corrupt every other
        caller's view by mutating it."""
        with wire(case.ok):
            adapter = case.build()
            await adapter.refresh_models()

        adapter.list_models().append("not-a-real-model")
        assert adapter.list_models() == EXPECTED_MODELS[case.name]

    async def test_refresh_failure_preserves_the_last_known_list(self, case):
        """A transient backend blip must not empty the cache — a downstream
        availability preflight would read the emptied list as "no models present"
        and block a valid cycle on missing evidence."""
        with wire(case.ok) as live:
            adapter = case.build()
            await adapter.refresh_models()

            live.set(raises(httpx.ConnectError("backend down")))
            assert await adapter.refresh_models() == EXPECTED_MODELS[case.name]
            assert adapter.list_models() == EXPECTED_MODELS[case.name]


class TestErrorTranslation:
    """Failure-locus classification (#568) reads these types to decide whether a
    failure is infrastructure or a work-product defect. An adapter that leaks a
    raw transport exception silently reclassifies an outage as a squad mistake
    and burns a correction attempt on it."""

    @pytest.mark.parametrize(
        ("wire_failure", "expected"),
        [
            (raises(httpx.ConnectError("refused")), LLMConnectionError),
            (raises(httpx.ReadTimeout("too slow")), LLMTimeoutError),
            (status(404, {"error": "model not found"}), LLMModelNotFoundError),
            (status(500, {"error": "internal"}), LLMConnectionError),
        ],
        ids=["connect-refused", "timeout", "unknown-model", "server-error"],
    )
    async def test_chat_translates_transport_failures(self, case, wire_failure, expected):
        with wire(wire_failure), pytest.raises(expected):
            await case.build().chat(_messages())

    @pytest.mark.parametrize(
        ("wire_failure", "expected"),
        [
            (raises(httpx.ConnectError("refused")), LLMConnectionError),
            (raises(httpx.ReadTimeout("too slow")), LLMTimeoutError),
            (status(404, {"error": "model not found"}), LLMModelNotFoundError),
        ],
        ids=["connect-refused", "timeout", "unknown-model"],
    )
    async def test_generate_translates_transport_failures(self, case, wire_failure, expected):
        with wire(wire_failure), pytest.raises(expected):
            await case.build().generate(LLMRequest(prompt="the question"))

    @pytest.mark.parametrize(
        ("wire_failure", "expected"),
        [
            (raises(httpx.ConnectError("refused")), LLMConnectionError),
            (raises(httpx.ReadTimeout("too slow")), LLMTimeoutError),
        ],
        ids=["connect-refused", "timeout"],
    )
    async def test_streaming_translates_transport_failures(self, case, wire_failure, expected):
        """Streaming has its own error path — a failure mid-iteration must
        surface as the same typed exception, not escape as a raw httpx error
        from inside the async generator."""
        with wire(wire_failure), pytest.raises(expected):
            async for _ in case.build().chat_stream(_messages()):
                pass


class TestCapabilityHonesty:
    """The load-bearing dimension: declarations must match reality.

    Without this, ``capabilities()`` is aspirational — a flag nobody verified,
    which is strictly worse than no flag at all because callers build on it
    (#572, the defect this pattern was copied from).
    """

    async def test_declared_capabilities_are_exactly_the_known_names(self, case):
        """An adapter inventing or misspelling a key makes `supports()` answer
        False for a feature it actually has — a silent capability outage."""
        declared = set(case.build().capabilities())
        assert declared == {
            LLMCapability.MODEL_LISTING,
            LLMCapability.MODEL_MANAGEMENT,
            LLMCapability.STREAMING_USAGE,
            LLMCapability.THINKING_TOKENS,
        }

    async def test_supports_is_false_for_an_undeclared_capability(self, case):
        assert case.build().supports("no_such_capability") is False

    async def test_model_listing_declaration_matches_behavior(self, case):
        """Declared True ⇒ it works. Declared False ⇒ it raises rather than
        returning [], because an empty list reads downstream as *no models
        present* and would block work that should proceed."""
        adapter = case.build()
        with wire(case.ok):
            if adapter.supports(LLMCapability.MODEL_LISTING):
                assert [m.name for m in await adapter.list_available_models()] == EXPECTED_MODELS[
                    case.name
                ]
            else:
                with pytest.raises(NotImplementedError):
                    await adapter.list_available_models()

    async def test_model_management_declaration_matches_behavior(self, case):
        adapter = case.build()
        with wire(case.ok):
            if adapter.supports(LLMCapability.MODEL_MANAGEMENT):
                assert await adapter.pull_model("qwen2.5:7b") is None
                assert await adapter.delete_model("qwen2.5:7b") is None
            else:
                with pytest.raises(NotImplementedError):
                    await adapter.pull_model("qwen2.5:7b")
                with pytest.raises(NotImplementedError):
                    await adapter.delete_model("qwen2.5:7b")

    async def test_streaming_usage_declaration_matches_behavior(self, case):
        """Declared True means real counts, not the port's chat() fallback —
        which returns a valid message carrying no streaming usage at all."""
        adapter = case.build()
        if not adapter.supports(LLMCapability.STREAMING_USAGE):
            pytest.skip("streaming_usage not declared")

        with wire(case.ok):
            message = await adapter.chat_stream_with_usage(_messages())

        assert message.completion_tokens == EXPECTED_COMPLETION_TOKENS[case.name]


class TestModelInfoShape:
    """``list_available_models`` speaks the port's vocabulary, not a dialect's."""

    async def test_listing_returns_model_info_with_names_populated(self, case):
        if not case.build().supports(LLMCapability.MODEL_LISTING):
            pytest.skip("model_listing not declared")

        with wire(case.ok):
            models = await case.build().list_available_models()

        assert [m.name for m in models] == EXPECTED_MODELS[case.name]
        assert all(isinstance(m, ModelInfo) for m in models)

    async def test_unnamed_entries_are_dropped_not_surfaced_as_blanks(self, case):
        """A nameless model is unusable — surfacing it as `name=""` puts an
        un-selectable row in the operator's model list and, worse, lets an
        availability check match the empty string."""
        if not case.build().supports(LLMCapability.MODEL_LISTING):
            pytest.skip("model_listing not declared")

        with wire(case.ok) as live:
            adapter = case.build()
            live.set(case.nameless_model)
            models = await adapter.list_available_models()

        assert models == []


class TestHealth:
    """Health drives operational probes; it reports, it never raises."""

    async def test_health_reports_healthy_against_a_live_backend(self, case):
        with wire(case.ok):
            result = await case.build().health()

        assert result["healthy"] is True

    async def test_health_reports_unhealthy_instead_of_raising(self, case):
        """A probe that raises takes down the caller it was meant to inform."""
        with wire(raises(httpx.ConnectError("refused"))):
            result = await case.build().health()

        assert result["healthy"] is False


class TestPortSurface:
    """Contract properties every adapter carries."""

    async def test_default_model_is_the_configured_one(self, case):
        """Handlers resolve their model as `agent_model or port.default_model`,
        so a placeholder here silently becomes the model that actually runs."""
        assert case.build().default_model == "qwen2.5:7b"

    async def test_request_model_overrides_the_adapter_default(self, case):
        """Per-agent model pinning (squad profiles) rides this override. If it
        is ignored, every agent quietly runs the adapter default instead."""
        with wire(case.ok):
            response = await case.build().generate(
                LLMRequest(prompt="the question", model="llama3.2")
            )

        assert response.model == "llama3.2"
