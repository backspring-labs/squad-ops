"""The construction seam for generation records (#1171)."""

from __future__ import annotations

import pytest

from squadops.llm.models import ChatMessage
from squadops.telemetry.models import MAX_OBSERVABILITY_TEXT_LENGTH, build_generation_record

pytestmark = [pytest.mark.domain_telemetry]


class _Usage:
    """The shape every adapter's response carries (LLMResponse, ChatMessage)."""

    prompt_tokens = 9244
    completion_tokens = 3401
    total_tokens = 12645
    tokens_per_second = 28.8


def test_token_usage_reaches_the_record():
    """The #1171 defect exactly: a caller with usage in hand whose record arrives at
    LangFuse costed at zero, because the four fields were never read off it."""
    record = build_generation_record(
        model="qwen3.8:27b",
        prompt_text="p",
        response_text="r",
        latency_ms=301_000.0,
        usage=_Usage(),
    )
    assert record.prompt_tokens == 9244
    assert record.completion_tokens == 3401
    assert record.total_tokens == 12645
    assert record.tokens_per_second == 28.8


def test_absent_usage_reports_none_rather_than_zero():
    """A caller with no usage to report must produce None, not 0 — the console chat
    path has no response object, and a zero would be indistinguishable from a
    generation that genuinely produced nothing."""
    record = build_generation_record(model="m", prompt_text="p", response_text="r")
    assert record.prompt_tokens is None
    assert record.completion_tokens is None
    assert record.total_tokens is None
    assert record.tokens_per_second is None


def test_partial_usage_takes_what_is_there():
    """Ollama reports no reasoning_tokens and vLLM no native rate: an object missing
    an attribute must yield None for that field, not raise."""

    class _Partial:
        completion_tokens = 512

    record = build_generation_record(
        model="m", prompt_text="p", response_text="r", usage=_Partial()
    )
    assert record.completion_tokens == 512
    assert record.prompt_tokens is None
    assert record.tokens_per_second is None


def test_text_is_capped_at_the_seam():
    """The cap lives here so no call site has to remember it — two of the five did not."""
    record = build_generation_record(
        model="m",
        prompt_text="p" * (MAX_OBSERVABILITY_TEXT_LENGTH + 5_000),
        response_text="r" * (MAX_OBSERVABILITY_TEXT_LENGTH + 5_000),
    )
    assert len(record.prompt_text) == MAX_OBSERVABILITY_TEXT_LENGTH
    assert len(record.response_text) == MAX_OBSERVABILITY_TEXT_LENGTH


def test_each_record_gets_its_own_id():
    a = build_generation_record(model="m", prompt_text="p", response_text="r")
    b = build_generation_record(model="m", prompt_text="p", response_text="r")
    assert a.generation_id != b.generation_id


class TestReasoningTextIsCarried:
    """#410: the thinking text must survive from adapter to record.

    Ollama returns it at ``message.thinking``, Atlas and vLLM at
    ``message.reasoning_content``; all three were read past and dropped, so the
    generation time that bought it appeared in no telemetry at all.
    """

    def test_reasoning_text_is_read_off_usage_like_the_token_fields(self):
        """A caller already passing the response object gets it without a second arg."""
        usage = ChatMessage(
            role="assistant", content="hello", completion_tokens=37, reasoning_text="I thought this"
        )
        record = build_generation_record(
            model="qwen3.8:27b", prompt_text="p", response_text="hello", usage=usage
        )
        assert record.reasoning_text == "I thought this"
        assert record.completion_tokens == 37

    def test_explicit_argument_beats_usage(self):
        usage = ChatMessage(role="assistant", content="hi", reasoning_text="from usage")
        record = build_generation_record(
            model="m", prompt_text="p", response_text="hi", usage=usage, reasoning_text="explicit"
        )
        assert record.reasoning_text == "explicit"

    def test_absent_stays_none_and_empty_stays_empty(self):
        """None (no channel) and "" (channel present, empty) mean different things:
        'did not think' versus 'thought and said nothing'. Zero-filling either
        would erase that, the way #1171 zero-filled token counts."""
        assert (
            build_generation_record(model="m", prompt_text="p", response_text="r").reasoning_text
            is None
        )
        assert (
            build_generation_record(
                model="m", prompt_text="p", response_text="r", reasoning_text=""
            ).reasoning_text
            == ""
        )

    def test_reasoning_text_is_capped_like_the_other_text_fields(self):
        """An unbounded thinking channel would be the largest field on the record;
        qwen3 routinely emits tens of thousands of characters."""
        huge = "x" * (MAX_OBSERVABILITY_TEXT_LENGTH + 5000)
        record = build_generation_record(
            model="m", prompt_text="p", response_text="r", reasoning_text=huge
        )
        assert len(record.reasoning_text) == MAX_OBSERVABILITY_TEXT_LENGTH
