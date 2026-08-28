"""vLLM dialect specifics (Atlas Provider Adapter SIP, SIP-0106, P6).

The shared conformance suite owns the *contract* — what every adapter must do.
This file owns what is true of the **OpenAI-compatible dialect in particular**:
SSE sentinel handling and partial `usage` objects.

These deliberately do not live in the shared suite. Putting them there would
force every case to supply a `[DONE]` frame and a total-less usage object, which
would enshrine vLLM's transport shape as the contract — the mirror image of the
Ollama-shaped assumptions that adding a second adapter just exposed. The 1.5 plan
named that trap in one direction; it applies in both.

Found by mutation testing: both behaviors below survived a deliberate defect
because the shared suite's fixture never exercised them.
"""

from __future__ import annotations

import json

import httpx
import pytest

from adapters.llm.vllm import VLLMAdapter, _reasoning_fields
from squadops.llm.model_registry import ModelSpec, ReasoningControl
from squadops.llm.models import ChatMessage, ReasoningLevel
from tests.unit.llm.conformance import wire

pytestmark = [pytest.mark.domain_orchestration]


def _adapter() -> VLLMAdapter:
    return VLLMAdapter(
        base_url="http://localhost:8000",
        default_model="Qwen/Qwen2.5-7B-Instruct",
        timeout_seconds=5.0,
    )


def _messages() -> list[ChatMessage]:
    return [ChatMessage(role="user", content="the question")]


def _sse(*raw_frames: str) -> bytes:
    return ("".join(f"data: {f}\n\n" for f in raw_frames)).encode()


class TestSSESentinel:
    """`data: [DONE]` terminates the stream."""

    async def test_frames_after_done_are_ignored(self):
        """A sentinel that does not stop iteration lets post-`[DONE]` output —
        a keep-alive, a trailing artifact of a proxy — append itself to the
        assistant's answer, corrupting a work product rather than failing.

        Mutation-verified: disabling the sentinel check passes without this,
        because malformed-frame skipping happens to absorb the sentinel itself.
        """
        body = _sse(
            json.dumps({"choices": [{"delta": {"content": "real"}}]}),
            "[DONE]",
            json.dumps({"choices": [{"delta": {"content": "-LEAKED"}}]}),
        )

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, content=body)

        with wire(handler):
            chunks = [c async for c in _adapter().chat_stream(_messages())]

        assert "".join(chunks) == "real"

    async def test_malformed_frame_is_skipped_not_fatal(self):
        """One unparseable frame must not discard an otherwise complete
        generation — on a slow box that is minutes of work thrown away."""
        body = _sse(
            json.dumps({"choices": [{"delta": {"content": "before "}}]}),
            "{not json at all",
            json.dumps({"choices": [{"delta": {"content": "after"}}]}),
            "[DONE]",
        )

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, content=body)

        with wire(handler):
            chunks = [c async for c in _adapter().chat_stream(_messages())]

        assert "".join(chunks) == "before after"


class TestPartialUsageObject:
    """Not every OpenAI-compatible server fills every usage field."""

    async def test_total_is_derived_when_the_server_omits_it(self):
        """Servers that report prompt and completion but no total are real. The
        port's consistency contract is `total == prompt + completion`, so the
        adapter derives it rather than surfacing None and making a caller guess
        whether usage was reported at all.

        Mutation-verified: removing the derivation passes the shared suite,
        whose fixture always sends `total_tokens`.
        """

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200,
                json={
                    "model": "Qwen/Qwen2.5-7B-Instruct",
                    "choices": [{"message": {"role": "assistant", "content": "hi"}}],
                    "usage": {"prompt_tokens": 7, "completion_tokens": 3},
                },
            )

        with wire(handler):
            message = await _adapter().chat(_messages())

        assert message.prompt_tokens == 7
        assert message.completion_tokens == 3
        assert message.total_tokens == 10

    async def test_absent_usage_object_yields_none_not_zero(self):
        """A server reporting no usage at all must not read as a free call."""

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200,
                json={
                    "model": "Qwen/Qwen2.5-7B-Instruct",
                    "choices": [{"message": {"role": "assistant", "content": "hi"}}],
                },
            )

        with wire(handler):
            message = await _adapter().chat(_messages())

        assert message.prompt_tokens is None
        assert message.completion_tokens is None
        assert message.total_tokens is None
        assert message.tokens_per_second is None


class TestStreamingUsageFrame:
    """`stream_options.include_usage` is requested, and its frame is consumed."""

    async def test_include_usage_is_requested_on_streaming_calls(self):
        """The option is what makes the terminal usage frame appear at all. An
        adapter that streams without requesting it loses token accounting for
        every streamed call — silently, since the content still arrives."""
        seen: dict = {}

        def handler(request: httpx.Request) -> httpx.Response:
            seen.update(json.loads(request.content))
            return httpx.Response(200, content=_sse("[DONE]"))

        with wire(handler):
            await _adapter().chat_stream_with_usage(_messages())

        assert seen["stream"] is True
        assert seen["stream_options"] == {"include_usage": True}

    async def test_usage_rides_a_frame_carrying_no_choices(self):
        """The usage frame arrives with an empty `choices` list, unlike Ollama
        where usage shares the final content frame. An adapter that only reads
        usage from content-bearing frames loses it entirely."""
        body = _sse(
            json.dumps({"choices": [{"delta": {"content": "answer"}}]}),
            json.dumps(
                {
                    "choices": [],
                    "usage": {"prompt_tokens": 4, "completion_tokens": 6, "total_tokens": 10},
                }
            ),
            "[DONE]",
        )

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, content=body)

        with wire(handler):
            message = await _adapter().chat_stream_with_usage(_messages())

        assert message.content == "answer"
        assert message.completion_tokens == 6
        assert message.total_tokens == 10


def _spec(dial: str) -> ModelSpec:
    return ModelSpec(name="any", context_window=1, default_max_completion=1, reasoning_control=dial)


class TestReasoningDials:
    """#927: the OpenAI shape has no reasoning field; each model family has its
    own, and the adapter picks by the dial the model spec declares. The bug each
    case guards: the wrong field for the family — a ``reasoning_effort`` sent to
    a qwen3 server is ignored and the channel stays on; a
    ``chat_template_kwargs`` sent to gpt-oss does nothing."""

    @pytest.mark.parametrize(
        ("level", "enabled"),
        [
            (ReasoningLevel.NONE, False),
            (ReasoningLevel.LOW, True),
            (ReasoningLevel.HIGH, True),
        ],
    )
    def test_toggle_dial_collapses_to_enable_thinking(self, level, enabled):
        assert _reasoning_fields(_spec(ReasoningControl.TOGGLE), level) == {
            "chat_template_kwargs": {"enable_thinking": enabled}
        }

    @pytest.mark.parametrize(
        ("level", "effort"),
        [
            (ReasoningLevel.NONE, "low"),  # the dial cannot switch off; lowest effort
            (ReasoningLevel.LOW, "low"),
            (ReasoningLevel.MEDIUM, "medium"),
            (ReasoningLevel.HIGH, "high"),
        ],
    )
    def test_effort_dial_passes_the_level_through(self, level, effort):
        assert _reasoning_fields(_spec(ReasoningControl.EFFORT), level) == {
            "reasoning_effort": effort
        }

    @pytest.mark.parametrize("spec", [None, _spec(ReasoningControl.NONE)])
    def test_no_dial_sends_nothing(self, spec):
        """An unregistered model or one with no channel gets no field at all —
        some backends reject unknown fields, and the port says a level is a
        request, not a guarantee."""
        assert _reasoning_fields(spec, ReasoningLevel.HIGH) == {}

    async def test_level_reaches_the_wire_by_the_registered_dial(self):
        """Wiring half: a registered toggle model's request carries the
        chat-template switch, and the flat OpenAI fields are untouched."""
        seen: list[dict] = []

        def handler(request: httpx.Request) -> httpx.Response:
            seen.append(json.loads(request.content))
            return httpx.Response(
                200,
                json={
                    "choices": [{"message": {"role": "assistant", "content": "ok"}}],
                    "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
                },
            )

        with wire(handler):
            await _adapter().chat(_messages(), model="qwen3.6:27b", reasoning=ReasoningLevel.NONE)
        assert seen[0]["chat_template_kwargs"] == {"enable_thinking": False}
        assert "reasoning_effort" not in seen[0]
