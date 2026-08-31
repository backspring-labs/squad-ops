"""LLM port conformance suite (Atlas Provider Adapter SIP, SIP-0106, P3).

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

import json

import httpx
import pytest

from squadops.llm.exceptions import (
    LLMConnectionError,
    LLMModelNotFoundError,
    LLMTimeoutError,
)
from squadops.llm.models import ChatMessage, LLMRequest, ModelInfo, ReasoningLevel
from squadops.ports.llm.provider import LLMCapability
from tests.unit.llm.conformance import ADAPTER_CASES, raises, status, wire

# A wall-clock-derived rate is machine-dependent, so it is bounded rather than
# pinned. The window is wide because the defect it guards against — a duration
# unit error — lands ~1e9 out, not a few percent.
MIN_PLAUSIBLE_TPS = 0.01
MAX_PLAUSIBLE_TPS = 1_000_000.0

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

        assert response.text == case.content
        assert response.model == case.default_model

    async def test_chat_returns_assistant_role_and_content(self, case):
        with wire(case.ok):
            message = await case.build().chat(_messages())

        assert message.role == "assistant"
        assert message.content == case.content

    async def test_chat_stream_reassembles_to_the_same_content(self, case):
        """Streaming is a transport detail; callers must not be able to tell.
        An adapter that drops the first or last frame — an off-by-one in its
        chunk loop — passes a "yields something" check and fails this one."""
        chunks: list[str] = []
        with wire(case.ok):
            async for chunk in case.build().chat_stream(_messages()):
                chunks.append(chunk)

        assert len(chunks) > 1, "single chunk cannot demonstrate reassembly"
        assert "".join(chunks) == case.content

    async def test_chat_stream_with_usage_returns_whole_message_not_chunks(self, case):
        """The streaming-for-liveness path: stream the wire to hold the
        connection open on long generations, hand back one assembled message."""
        with wire(case.ok):
            message = await case.build().chat_stream_with_usage(_messages())

        assert message.role == "assistant"
        assert message.content == case.content


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

        assert message.prompt_tokens == case.prompt_tokens
        assert message.completion_tokens == case.completion_tokens
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

        if case.tokens_per_second is not None:
            assert message.tokens_per_second == case.tokens_per_second
        else:
            # No timing field in this dialect — the adapter derives the rate from
            # wall-clock, so bound it instead of pinning it.
            assert MIN_PLAUSIBLE_TPS < message.tokens_per_second < MAX_PLAUSIBLE_TPS

    async def test_generate_reports_the_same_usage_as_chat(self, case):
        """Two entry points, one accounting contract. An adapter that populates
        usage on chat and forgets it on generate produces a silently partial
        cost picture that depends on which handler ran."""
        with wire(case.ok):
            response = await case.build().generate(LLMRequest(prompt="the question"))

        assert response.prompt_tokens == case.prompt_tokens
        assert response.completion_tokens == case.completion_tokens
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

        assert refreshed == case.models
        assert adapter.list_models() == case.models

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
            assert adapter.list_models() == case.models

    async def test_list_models_returns_a_copy(self, case):
        """Handing out the internal list lets any caller corrupt every other
        caller's view by mutating it."""
        with wire(case.ok):
            adapter = case.build()
            await adapter.refresh_models()

        adapter.list_models().append("not-a-real-model")
        assert adapter.list_models() == case.models

    async def test_refresh_failure_preserves_the_last_known_list(self, case):
        """A transient backend blip must not empty the cache — a downstream
        availability preflight would read the emptied list as "no models present"
        and block a valid cycle on missing evidence."""
        with wire(case.ok) as live:
            adapter = case.build()
            await adapter.refresh_models()

            live.set(raises(httpx.ConnectError("backend down")))
            assert await adapter.refresh_models() == case.models
            assert adapter.list_models() == case.models


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
            LLMCapability.REASONING_CONTROL,
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
                assert [m.name for m in await adapter.list_available_models()] == case.models
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

    async def test_reasoning_control_declaration_matches_behavior(self, case):
        """Declared True ⇒ a level changes the request, and no level leaves it
        exactly as it was (the pre-#927 wire, byte for byte — a level that
        leaked in unasked would change every generation's posture). Declared
        False ⇒ the three requests are identical: the level is accepted and
        dropped, never turned into a rejected call."""
        adapter = case.build()
        bodies: list[bytes] = []

        def capture(request: httpx.Request) -> httpx.Response:
            bodies.append(request.content)
            return case.ok(request)

        with wire(capture):
            await adapter.chat(_messages(), model=case.reasoning_model)
            await adapter.chat(
                _messages(), model=case.reasoning_model, reasoning=ReasoningLevel.NONE
            )
            await adapter.chat(
                _messages(), model=case.reasoning_model, reasoning=ReasoningLevel.HIGH
            )
        bare, none, high = bodies
        if adapter.supports(LLMCapability.REASONING_CONTROL):
            assert none != high
            assert bare not in (none, high)
        else:
            assert bare == none == high

    async def test_reasoning_text_reaches_the_port(self, case):
        """A provider that separates its reasoning channel must surface it as
        ``reasoning_text``, whatever the dialect calls the field.

        The bug this guards (#410): Ollama returns thinking at ``message.thinking``
        and the adapter read only ``message.content``, so ~60% of generation time
        was paid for, counted in ``eval_count``, and then dropped — invisible to
        LangFuse and undiagnosable without cross-referencing token counts against
        stored output length. Atlas and vLLM use ``message.reasoning_content``.
        Asserted here rather than per-adapter so a fourth provider cannot quietly
        drop the channel.
        """
        adapter = case.build()
        with wire(case.ok):
            reply = await adapter.chat(_messages(), model=case.reasoning_model)

        assert reply.reasoning_text == case.reasoning_text, (
            f"{case.name} did not surface its reasoning channel: "
            f"got {reply.reasoning_text!r}, expected {case.reasoning_text!r}"
        )
        # The channel is separate from the answer, not folded into it.
        assert case.reasoning_text not in reply.content

    async def test_reasoning_text_reaches_the_port_when_streamed(self, case):
        """The streaming path must surface the channel too — it is the path in service.

        The bug this guards (#1194): #410 added ``reasoning_text`` and fixed
        ``chat()``, but every cycle handler calls ``chat_stream_with_usage()``,
        which read only the content delta and returned a message leaving the field
        unset. The symbol was present in the deployed image and the non-streaming
        test above passed, so nothing flagged it — while 23 of 27 generations on the
        2026-08-31 shakeouts asked the model to think and recorded
        ``reasoning_text: null``. A test on the path nothing calls proves nothing
        about the path everything calls, which is why this sits beside it rather
        than replacing it.
        """
        adapter = case.build()
        if not adapter.supports(LLMCapability.STREAMING_USAGE):
            pytest.skip("streaming_usage not declared")

        with wire(case.ok):
            message = await adapter.chat_stream_with_usage(_messages(), model=case.reasoning_model)

        assert message.reasoning_text == case.reasoning_text, (
            f"{case.name} dropped its reasoning channel on the streaming path: "
            f"got {message.reasoning_text!r}, expected {case.reasoning_text!r}"
        )
        # Assembled from every delta, not just the last one the stream carried.
        assert case.reasoning_text not in message.content

    async def test_streaming_usage_declaration_matches_behavior(self, case):
        """Declared True means real counts, not the port's chat() fallback —
        which returns a valid message carrying no streaming usage at all."""
        adapter = case.build()
        if not adapter.supports(LLMCapability.STREAMING_USAGE):
            pytest.skip("streaming_usage not declared")

        with wire(case.ok):
            message = await adapter.chat_stream_with_usage(_messages())

        assert message.completion_tokens == case.completion_tokens


class TestModelInfoShape:
    """``list_available_models`` speaks the port's vocabulary, not a dialect's."""

    async def test_listing_returns_model_info_with_names_populated(self, case):
        if not case.build().supports(LLMCapability.MODEL_LISTING):
            pytest.skip("model_listing not declared")

        with wire(case.ok):
            models = await case.build().list_available_models()

        assert [m.name for m in models] == case.models
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
        assert case.build().default_model == case.default_model

    async def test_request_model_overrides_the_adapter_default(self, case):
        """Per-agent model pinning (squad profiles) rides this override. If it
        is ignored, every agent quietly runs the adapter default instead."""
        with wire(case.ok):
            response = await case.build().generate(
                LLMRequest(prompt="the question", model=case.override_model)
            )

        assert response.model == case.override_model


class TestSamplingPairReachesTheWire:
    """#901: `temperature` was reachable from a squad profile and `top_p` was not.

    For Qwen-family models those two are a documented pair, so an operator tuning a
    profile could set one, have the other rejected with a 422, and land on a third
    configuration the model was never tuned for.
    """

    async def test_top_p_reaches_the_provider_alongside_temperature(self, case):
        """A knob the profile permits but the adapter drops is the same defect one
        layer down — the operator sets it, nothing rejects it, and it does nothing."""
        seen: dict = {}

        def capture(request):
            if request.content:
                seen.update(json.loads(request.content))
            return case.ok(request)

        with wire(capture):
            await case.build().chat_stream_with_usage(_messages(), temperature=0.7, top_p=0.8)

        # Ollama nests sampling under `options`; the OpenAI shape puts it top level.
        body = seen.get("options", seen)
        assert body.get("temperature") == 0.7, f"{case.name} dropped temperature"
        assert body.get("top_p") == 0.8, f"{case.name} dropped top_p"

    async def test_an_unset_top_p_sends_nothing_rather_than_a_default(self, case):
        """Sending an invented value would replace the model's own tuned default with
        a number nobody chose — which is the failure #901 describes, arrived at from
        the other direction."""
        seen: dict = {}

        def capture(request):
            if request.content:
                seen.update(json.loads(request.content))
            return case.ok(request)

        with wire(capture):
            await case.build().chat_stream_with_usage(_messages())

        body = seen.get("options", seen)
        assert "top_p" not in body, f"{case.name} invented a top_p"

    async def test_top_p_and_reasoning_do_not_bind_to_each_other(self, case):
        """The regression this guards, found while writing the fix: every payload
        builder took `reasoning` positionally, directly after `temperature`. Inserting
        a sampling knob between them bound `reasoning` to `top_p` at every call site,
        with no type error to catch it — both are `float | None`/`str | None` in a
        chain of positional arguments. The call sites are keyword-only now; this fails
        if anyone reverts that.
        """
        seen: dict = {}

        def capture(request):
            if request.content:
                seen.update(json.loads(request.content))
            return case.ok(request)

        with wire(capture):
            await case.build().chat_stream_with_usage(
                _messages(), model=case.reasoning_model, top_p=0.8, reasoning="none"
            )

        body = seen.get("options", seen)
        assert body.get("top_p") == 0.8, f"{case.name}: top_p did not survive"
        # Whatever the dialect calls its reasoning switch, it must not be 0.8.
        assert 0.8 not in [
            seen.get(k) for k in ("think", "reasoning_effort", "chat_template_kwargs")
        ]
