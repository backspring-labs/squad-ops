"""Atlas dialect specifics (Atlas Provider Adapter SIP, SIP-0106, P4).

The shared conformance suite owns the contract. This file owns what is true of Atlas
in particular, each item measured on the Spark on 2026-08-28 (#1158): the bearer gate,
the reasoning ladder's `high` rejection, thinking in its own field, and the engine's
own decode rate.
"""

from __future__ import annotations

import json

import httpx
import pytest

from adapters.llm.atlas import AtlasAdapter
from squadops.llm.exceptions import LLMConnectionError, LLMTimeoutError
from squadops.llm.models import ChatMessage, ReasoningLevel
from tests.unit.llm.conformance import ATLAS_TOKEN, atlas_ok, wire

pytestmark = [pytest.mark.domain_orchestration]


def _adapter(api_key: str | None = ATLAS_TOKEN) -> AtlasAdapter:
    return AtlasAdapter(
        base_url="http://localhost:8888",
        default_model="Qwen/Qwen3.8-27B-FP8",
        timeout_seconds=5.0,
        api_key=api_key,
    )


def _messages() -> list[ChatMessage]:
    return [ChatMessage(role="user", content="the question")]


class TestBearerGate:
    async def test_a_missing_token_is_named_not_reported_as_a_network_failure(self):
        """The bug: a 401 surfacing as "failed to connect" sends the operator to the
        firewall; the setting to fix is SQUADOPS__LLM__API_KEY."""
        with wire(atlas_ok), pytest.raises(LLMConnectionError, match="SQUADOPS__LLM__API_KEY"):
            await _adapter(api_key=None).chat(_messages())

    async def test_health_reports_a_rejected_token_without_raising(self):
        with wire(atlas_ok):
            report = await _adapter(api_key="wrong").health()
        assert report["healthy"] is False
        assert "SQUADOPS__LLM__API_KEY" in report["error"]


class TestReasoningEffort:
    @pytest.mark.parametrize(
        ("level", "effort"),
        [
            (ReasoningLevel.NONE, "none"),
            (ReasoningLevel.LOW, "low"),
            (ReasoningLevel.MEDIUM, "medium"),
            (ReasoningLevel.HIGH, "xhigh"),  # the served template rejects `high`
        ],
    )
    async def test_the_level_maps_onto_the_served_ladder(self, level, effort):
        """`high` passed through blind is a 400 from the Qwen3.8 template; `xhigh` is
        its top tier. Every other level is verbatim, including a real `none`."""
        seen: list[dict] = []

        def capture(request: httpx.Request) -> httpx.Response:
            seen.append(json.loads(request.content))
            return atlas_ok(request)

        with wire(capture):
            await _adapter().chat(_messages(), reasoning=level)
        assert seen[0]["reasoning_effort"] == effort

    async def test_no_level_sends_no_effort_field(self):
        seen: list[dict] = []

        def capture(request: httpx.Request) -> httpx.Response:
            seen.append(json.loads(request.content))
            return atlas_ok(request)

        with wire(capture):
            await _adapter().chat(_messages())
        assert "reasoning_effort" not in seen[0]


class TestThinkingChannel:
    async def test_reasoning_tokens_are_reported_separately(self):
        with wire(atlas_ok):
            msg = await _adapter().chat(_messages())
        assert msg.reasoning_tokens == 12
        assert msg.completion_tokens == 40

    async def test_streamed_reasoning_deltas_are_not_spliced_into_content(self):
        """`delta.reasoning_content` is the thinking channel; it must not reach the
        fenced parser as output."""
        with wire(atlas_ok):
            chunks = [c async for c in _adapter().chat_stream(_messages())]
            assembled = await _adapter().chat_stream_with_usage(_messages())
        assert "".join(chunks) == "the assembled answer"
        assert assembled.content == "the assembled answer"
        assert assembled.reasoning_tokens == 12

    async def test_absent_reasoning_details_stay_none_not_zero(self):
        def no_details(request: httpx.Request) -> httpx.Response:
            response = atlas_ok(request)
            if request.url.path != "/v1/chat/completions":
                return response
            body = json.loads(response.content)
            body["usage"].pop("completion_tokens_details")
            return httpx.Response(200, json=body)

        with wire(no_details):
            msg = await _adapter().chat(_messages())
        assert msg.reasoning_tokens is None


class TestServerSideCut:
    """Atlas's `--request-timeout` ends a generation with a 200 and
    `finish_reason: "timeout"` (measured, #1160 shakeout). Handed on as a complete
    message, the truncated output reached the YAML parser as "malformed"; it is a
    timeout, and the loop classifies it as one."""

    def _cut(self, request: httpx.Request) -> httpx.Response:
        response = atlas_ok(request)
        if request.url.path != "/v1/chat/completions":
            return response
        body = json.loads(request.content)
        if body.get("stream"):
            frames = [
                {"choices": [{"index": 0, "delta": {"content": "half a YA"}}]},
                {"choices": [], "usage": json.loads(atlas_ok(request).content)["usage"]}
                if False
                else {
                    "choices": [],
                    "usage": {"prompt_tokens": 20, "completion_tokens": 3351, "total_tokens": 3371},
                },
                {"choices": [{"index": 0, "delta": {}, "finish_reason": "timeout"}]},
            ]
            return httpx.Response(
                200,
                content=b"".join(f"data: {json.dumps(f)}\n\n".encode() for f in frames)
                + b"data: [DONE]\n\n",
            )
        payload = json.loads(response.content)
        payload["choices"][0]["finish_reason"] = "timeout"
        payload["choices"][0]["message"]["content"] = "half a YA"
        return httpx.Response(200, json=payload)

    async def test_chat_raises_timeout_not_a_truncated_message(self):
        with wire(self._cut), pytest.raises(LLMTimeoutError, match="request-timeout"):
            await _adapter().chat(_messages())

    async def test_stream_with_usage_raises_timeout_not_a_truncated_message(self):
        with wire(self._cut), pytest.raises(LLMTimeoutError, match="request-timeout"):
            await _adapter().chat_stream_with_usage(_messages())


class TestThroughput:
    async def test_the_engines_own_rate_is_reported_verbatim(self):
        """Atlas measures its decode phase; a wall-clock derivation here would be a
        different quantity (inclusive of prefill) labelled the same."""
        with wire(atlas_ok):
            msg = await _adapter().chat(_messages())
        assert msg.tokens_per_second == 12.78

    async def test_wall_clock_fallback_only_when_the_field_is_absent(self):
        def no_rate(request: httpx.Request) -> httpx.Response:
            response = atlas_ok(request)
            if request.url.path != "/v1/chat/completions":
                return response
            body = json.loads(response.content)
            body["usage"].pop("response_token/s")
            return httpx.Response(200, json=body)

        with wire(no_rate):
            msg = await _adapter().chat(_messages())
        assert msg.tokens_per_second is not None and msg.tokens_per_second > 0
