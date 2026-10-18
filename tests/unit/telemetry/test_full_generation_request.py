"""A generation's full rendered request, readable by its id (#1756).

The prompt LangFuse displays is cut at ``MAX_OBSERVABILITY_TEXT_LENGTH``; a longer one is kept
whole, redacted and compressed, in the generation's metadata.
"""

from __future__ import annotations

import pytest

from squadops.telemetry.full_text import (
    FULL_PROMPT_KEY,
    FullTextUnreadable,
    decode_full_text,
    encode_full_text,
)
from squadops.telemetry.models import MAX_OBSERVABILITY_TEXT_LENGTH, build_generation_record
from tests.unit.telemetry.test_langfuse_adapter import (
    _cleanup_adapter,
    _create_adapter,
    _make_ctx,
    _make_layers,
)

SECRET = "Bearer abc123456789012345678901"
LONG = (
    "The API runs at http://localhost:8000/api.\n"
    + ("A requirement the model must read, line by line.\n" * 600)
    + f"Authorization: {SECRET}\n"
    + "The routes are declared with @app.get('/runs') and @app.post('/runs').\n"
)


@pytest.fixture
def langfuse():
    adapter, _client, old = _create_adapter()
    yield adapter
    _cleanup_adapter(adapter, old)


def _sent(adapter, prompt: str) -> dict:
    """What the adapter hands LangFuse for a generation built the way every call site builds one."""
    from unittest.mock import MagicMock

    ctx = _make_ctx()
    parent = MagicMock()
    adapter._span_state[f"task:{adapter._resolve_trace_key(ctx)}:{ctx.task_id}"] = parent
    record = build_generation_record(model="m", prompt_text=prompt, response_text="ok")
    adapter.record_generation(ctx, record, _make_layers())
    adapter._handle_generation(adapter._buffer.get_nowait())
    return parent.generation.call_args.kwargs


def test_a_prompt_longer_than_the_cap_reads_back_whole_and_redacted(langfuse):
    """The issue's test. Entered at ``build_generation_record``, which every call site uses, and
    read at the payload handed to LangFuse. Bug caught: the request cut at the cap with no other
    copy (#1723, deploy B's repair); the full copy stored unredacted; or the redaction eating the
    text between a URL's port and a later decorator, so the copy isn't what the model saw."""
    sent = _sent(langfuse, LONG)

    full = decode_full_text(sent["metadata"][FULL_PROMPT_KEY])

    assert len(LONG) > MAX_OBSERVABILITY_TEXT_LENGTH
    assert full == LONG.replace(SECRET, "[REDACTED]")  # the secret, and nothing else
    assert len(sent["input"]) == MAX_OBSERVABILITY_TEXT_LENGTH


def test_a_prompt_within_the_cap_is_stored_once(langfuse):
    """Bug caught: every short prompt stored twice, doubling LangFuse's rows for nothing."""
    sent = _sent(langfuse, "a short prompt")

    assert FULL_PROMPT_KEY not in sent["metadata"] and sent["input"] == "a short prompt"


@pytest.mark.parametrize(
    "damage",
    [{"sha256": "0" * 64}, {"chars": 1}, {"data": "not base64!"}, {"encoding": "zstd"}],
    ids=["another-hash", "another-length", "not-base64", "another-encoding"],
)
def test_a_damaged_copy_is_refused_not_printed(damage):
    """Bug caught: a truncated or corrupted copy read out as the request the model saw."""
    with pytest.raises(FullTextUnreadable):
        decode_full_text({**encode_full_text(LONG), **damage})
