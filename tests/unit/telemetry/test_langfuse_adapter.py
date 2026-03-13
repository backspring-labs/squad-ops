"""Unit tests for LangFuseAdapter (SIP-0061).

Tests buffer mechanics, overflow, sampling, redaction, close/flush,
thread-safety, and payload shapes — all without a running LangFuse instance.

Uses a fake langfuse module injection so the SDK is not required.
"""

from __future__ import annotations

import sys
import time
import types
from unittest.mock import MagicMock

import pytest

from squadops.config.schema import LangFuseConfig
from squadops.telemetry.models import (
    CorrelationContext,
    GenerationRecord,
    PromptLayer,
    PromptLayerMetadata,
    StructuredEvent,
)


def _make_config(**overrides) -> LangFuseConfig:
    """Build a LangFuseConfig with test defaults."""
    defaults = {
        "enabled": True,
        "host": "http://localhost:3000",
        "public_key": "pk-test",
        "secret_key": "sk-test",
        "buffer_max_size": 10,
        "flush_interval_seconds": 60,
        "shutdown_flush_timeout_seconds": 2,
        "sample_rate_percent": 100,
        "redaction_mode": "standard",
    }
    defaults.update(overrides)
    return LangFuseConfig(**defaults)


def _make_ctx(**overrides) -> CorrelationContext:
    defaults = {"cycle_id": "cycle-1", "pulse_id": "pulse-1", "task_id": "task-1"}
    defaults.update(overrides)
    return CorrelationContext(**defaults)


def _make_record(**overrides) -> GenerationRecord:
    defaults = {
        "generation_id": "gen-001",
        "model": "test-model",
        "prompt_text": "hello",
        "response_text": "world",
    }
    defaults.update(overrides)
    return GenerationRecord(**defaults)


def _make_layers() -> PromptLayerMetadata:
    return PromptLayerMetadata(
        prompt_layer_set_id="PLS-test",
        layers=(PromptLayer(layer_type="system", layer_id="sys-1"),),
    )


def _inject_fake_langfuse():
    """Inject a fake langfuse module into sys.modules so adapter can import it."""
    fake = types.ModuleType("langfuse")
    mock_client = MagicMock()
    mock_client.auth_check.return_value = True
    fake.Langfuse = MagicMock(return_value=mock_client)  # type: ignore[attr-defined]
    return fake, mock_client


def _create_adapter(config=None):
    """Create a LangFuseAdapter with injected fake SDK."""
    fake_mod, mock_client = _inject_fake_langfuse()
    old = sys.modules.get("langfuse")
    sys.modules["langfuse"] = fake_mod
    # Force re-import of adapter module so it picks up fake langfuse
    sys.modules.pop("adapters.telemetry.langfuse.adapter", None)
    try:
        from adapters.telemetry.langfuse.adapter import LangFuseAdapter

        return LangFuseAdapter(config or _make_config()), mock_client, old
    except Exception:
        # Restore on failure
        if old is None:
            sys.modules.pop("langfuse", None)
        else:
            sys.modules["langfuse"] = old
        sys.modules.pop("adapters.telemetry.langfuse.adapter", None)
        raise


def _cleanup_adapter(adapter, old_langfuse):
    """Clean shutdown of adapter and restore sys.modules."""
    adapter._shutdown.set()
    adapter._flush_requested.set()
    adapter._flush_thread.join(timeout=2)
    if old_langfuse is None:
        sys.modules.pop("langfuse", None)
    else:
        sys.modules["langfuse"] = old_langfuse
    sys.modules.pop("adapters.telemetry.langfuse.adapter", None)


@pytest.fixture
def adapter():
    """Create a LangFuseAdapter with fake SDK injection."""
    a, mock_client, old = _create_adapter()
    yield a
    _cleanup_adapter(a, old)


class TestBufferOverflow:
    """Buffer overflow: drop oldest, increment counter."""

    def test_buffer_overflow_drops_oldest(self, adapter):
        ctx = _make_ctx()
        for _ in range(10):
            adapter.start_cycle_trace(ctx)
        assert adapter._buffer.qsize() == 10

        adapter.start_cycle_trace(ctx)
        assert adapter._buffer.qsize() == 10
        with adapter._lock:
            assert adapter._dropped_events == 1

    def test_overflow_warning_rate_limited(self, adapter, caplog):
        import logging

        ctx = _make_ctx()
        for _ in range(10):
            adapter.start_cycle_trace(ctx)

        with caplog.at_level(logging.WARNING):
            for _ in range(5):
                adapter.start_cycle_trace(ctx)

        with adapter._lock:
            assert adapter._dropped_events == 5

        overflow_warnings = [r for r in caplog.records if "buffer_overflow" in r.message]
        assert len(overflow_warnings) == 1

    def test_health_includes_dropped_events_counter(self, adapter):
        import asyncio

        ctx = _make_ctx()
        for _ in range(12):
            adapter.start_cycle_trace(ctx)

        result = asyncio.get_event_loop().run_until_complete(adapter.health())
        assert result["details"]["dropped_events"] == 2

    def test_health_includes_buffer_size(self, adapter):
        import asyncio

        ctx = _make_ctx()
        for _ in range(5):
            adapter.start_cycle_trace(ctx)

        result = asyncio.get_event_loop().run_until_complete(adapter.health())
        assert result["details"]["buffer_size"] == 5


class TestCloseAndFlush:
    """close() bounded flush, flush() non-blocking."""

    def test_close_completes_within_timeout(self, adapter):
        start = time.monotonic()
        adapter.close()
        elapsed = time.monotonic() - start
        assert elapsed < adapter._config.shutdown_flush_timeout_seconds + 1.0

    def test_flush_is_nonblocking(self, adapter):
        ctx = _make_ctx()
        for _ in range(10):
            adapter.start_cycle_trace(ctx)

        start = time.monotonic()
        adapter.flush()
        elapsed = time.monotonic() - start
        assert elapsed < 0.05


class TestSampling:
    """Sampling applies ONLY to record_generation."""

    def test_zero_sample_rate_drops_all_generations(self):
        a, _, old = _create_adapter(_make_config(sample_rate_percent=0))
        try:
            ctx = _make_ctx()
            a.record_generation(ctx, _make_record(), _make_layers())
            assert a._buffer.qsize() == 0
        finally:
            _cleanup_adapter(a, old)

    def test_hundred_sample_rate_keeps_all_generations(self, adapter):
        ctx = _make_ctx()
        adapter.record_generation(ctx, _make_record(), _make_layers())
        assert adapter._buffer.qsize() == 1

    def test_spans_always_emit_regardless_of_sample_rate(self):
        a, _, old = _create_adapter(_make_config(sample_rate_percent=0))
        try:
            ctx = _make_ctx()
            a.start_cycle_trace(ctx)
            a.start_pulse_span(ctx)
            a.record_event(ctx, StructuredEvent(name="test", message="hi"))
            assert a._buffer.qsize() == 3
        finally:
            _cleanup_adapter(a, old)


class TestRedaction:
    """Redaction applied before enqueue."""

    def test_generation_text_is_redacted_before_buffer(self, adapter):
        ctx = _make_ctx()
        record = _make_record(
            prompt_text="Use Bearer abc123456789012345678901 token",
            response_text="key is sk-secret1234567890123456",
        )
        adapter.record_generation(ctx, record, _make_layers())

        entry = adapter._buffer.get_nowait()
        redacted_record = entry.payload[0]
        assert "abc123456789012345678901" not in redacted_record.prompt_text
        assert "sk-secret1234567890123456" not in redacted_record.response_text

    def test_event_message_is_redacted_before_buffer(self, adapter):
        ctx = _make_ctx()
        event = StructuredEvent(name="test", message="password=mysecretpass in config")
        adapter.record_event(ctx, event)

        entry = adapter._buffer.get_nowait()
        assert "mysecretpass" not in entry.payload.message


class TestPayloadShapes:
    """Verify buffer entries have correct structure."""

    def test_generation_entry_has_record_and_layers(self, adapter):
        ctx = _make_ctx()
        adapter.record_generation(ctx, _make_record(), _make_layers())
        entry = adapter._buffer.get_nowait()
        record, layers = entry.payload
        assert record.generation_id == "gen-001"
        assert layers.prompt_layer_set_id == "PLS-test"

    def test_event_entry_has_structured_event(self, adapter):
        ctx = _make_ctx()
        adapter.record_event(ctx, StructuredEvent(name="task.started", message="go"))
        entry = adapter._buffer.get_nowait()
        assert entry.payload.name == "task.started"


class TestConcurrentTaskSpans:
    """Thread-safety of span state."""

    def test_concurrent_task_spans_no_corruption(self, adapter):
        import threading

        errors = []

        def worker(task_id):
            try:
                ctx = _make_ctx(task_id=task_id)
                adapter.start_task_span(ctx)
                adapter.end_task_span(ctx)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=worker, args=(f"task-{i}",)) for i in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0


class TestAdapterDoesNotGenerateId:
    """Adapter receives generation_id already set; never generates its own."""

    def test_adapter_does_not_generate_generation_id(self, adapter):
        ctx = _make_ctx()
        record = _make_record(generation_id="user-supplied-id")
        adapter.record_generation(ctx, record, _make_layers())

        entry = adapter._buffer.get_nowait()
        assert entry.payload[0].generation_id == "user-supplied-id"


class TestGenerationRecordValidation:
    """GenerationRecord requires generation_id."""

    def test_generation_record_requires_generation_id(self):
        with pytest.raises(TypeError):
            GenerationRecord(model="m", prompt_text="p", response_text="r")  # type: ignore

    def test_record_generation_accepts_prompt_layers(self, adapter):
        ctx = _make_ctx()
        record = _make_record()
        adapter.record_generation(ctx, record, _make_layers())
        entry = adapter._buffer.get_nowait()
        _, layers = entry.payload
        assert layers.prompt_layer_set_id == "PLS-test"

    def test_redaction_preserves_prompt_name_and_version(self, adapter):
        """Bug caught: redaction copy dropped prompt_name/prompt_version fields,
        so the adapter never saw them and couldn't link prompts to generations.
        """
        ctx = _make_ctx()
        record = _make_record(
            prompt_name="request.cycle_task_base",
            prompt_version=3,
        )
        adapter.record_generation(ctx, record, _make_layers())
        entry = adapter._buffer.get_nowait()
        redacted_record, _ = entry.payload
        assert redacted_record.prompt_name == "request.cycle_task_base"
        assert redacted_record.prompt_version == 3


class TestHealthStatus:
    """health() returns correct status structure."""

    def test_health_ok_when_reachable(self, adapter):
        import asyncio

        result = asyncio.get_event_loop().run_until_complete(adapter.health())
        assert result["status"] == "ok"
        assert result["backend"] == "langfuse"
        assert "buffer_size" in result["details"]
        assert "dropped_events" in result["details"]

    def test_health_down_when_unreachable(self):
        import asyncio

        fake_mod, mock_client = _inject_fake_langfuse()
        mock_client.auth_check.side_effect = ConnectionError("unreachable")
        old = sys.modules.get("langfuse")
        sys.modules["langfuse"] = fake_mod
        sys.modules.pop("adapters.telemetry.langfuse.adapter", None)
        try:
            from adapters.telemetry.langfuse.adapter import LangFuseAdapter

            a = LangFuseAdapter(_make_config())
            try:
                result = asyncio.get_event_loop().run_until_complete(a.health())
                assert result["status"] == "down"
                assert "error" in result["details"]
            finally:
                a._shutdown.set()
                a._flush_requested.set()
                a._flush_thread.join(timeout=2)
        finally:
            if old is None:
                sys.modules.pop("langfuse", None)
            else:
                sys.modules["langfuse"] = old
            sys.modules.pop("adapters.telemetry.langfuse.adapter", None)


class TestPromptToGenerationLinkage:
    """SIP-0084: prompt_name/prompt_version on GenerationRecord triggers
    Langfuse prompt resolution and passes it to generation(prompt=...).
    """

    def test_generation_with_prompt_name_resolves_and_links(self):
        """Bug caught: generation() called without prompt kwarg — Langfuse UI
        never shows prompts as 'used in a generation'.
        """
        a, mock_client, old = _create_adapter()
        try:
            fake_prompt_obj = MagicMock()
            mock_client.get_prompt.return_value = fake_prompt_obj

            ctx = _make_ctx()
            # Process cycle + task start synchronously via _process_entry
            from adapters.telemetry.langfuse.adapter import _BufferEntry, _EventType

            a._process_entry(_BufferEntry(_EventType.START_CYCLE, ctx, None))
            a._process_entry(_BufferEntry(_EventType.START_TASK, ctx, None))

            record = _make_record(prompt_name="request.cycle_task_base", prompt_version=2)
            a._process_entry(
                _BufferEntry(_EventType.GENERATION, ctx, (record, _make_layers()))
            )

            mock_client.get_prompt.assert_called_once_with(
                name="request.cycle_task_base", version=2
            )
            # The generation call on the task span must include prompt=
            tk = ctx.trace_id or ctx.cycle_id
            task_span = a._span_state[f"task:{tk}:{ctx.task_id}"]
            task_span.generation.assert_called_once()
            assert task_span.generation.call_args[1]["prompt"] is fake_prompt_obj
        finally:
            _cleanup_adapter(a, old)

    def test_generation_without_prompt_name_skips_resolution(self):
        """When prompt_name is None, no get_prompt call and no prompt kwarg."""
        a, mock_client, old = _create_adapter()
        try:
            ctx = _make_ctx()
            from adapters.telemetry.langfuse.adapter import _BufferEntry, _EventType

            a._process_entry(_BufferEntry(_EventType.START_CYCLE, ctx, None))
            a._process_entry(_BufferEntry(_EventType.START_TASK, ctx, None))

            record = _make_record()  # No prompt_name
            a._process_entry(
                _BufferEntry(_EventType.GENERATION, ctx, (record, _make_layers()))
            )

            mock_client.get_prompt.assert_not_called()
            tk = ctx.trace_id or ctx.cycle_id
            task_span = a._span_state[f"task:{tk}:{ctx.task_id}"]
            task_span.generation.assert_called_once()
            assert "prompt" not in task_span.generation.call_args[1]
        finally:
            _cleanup_adapter(a, old)

    def test_prompt_resolution_failure_still_records_generation(self):
        """Bug caught: if get_prompt raises (e.g. prompt not in Langfuse),
        the generation must still be recorded without the prompt link.
        """
        a, mock_client, old = _create_adapter()
        try:
            mock_client.get_prompt.side_effect = Exception("not found")

            ctx = _make_ctx()
            from adapters.telemetry.langfuse.adapter import _BufferEntry, _EventType

            a._process_entry(_BufferEntry(_EventType.START_CYCLE, ctx, None))
            a._process_entry(_BufferEntry(_EventType.START_TASK, ctx, None))

            record = _make_record(prompt_name="nonexistent.template")
            a._process_entry(
                _BufferEntry(_EventType.GENERATION, ctx, (record, _make_layers()))
            )

            mock_client.get_prompt.assert_called_once()
            tk = ctx.trace_id or ctx.cycle_id
            task_span = a._span_state[f"task:{tk}:{ctx.task_id}"]
            task_span.generation.assert_called_once()
            assert "prompt" not in task_span.generation.call_args[1]
        finally:
            _cleanup_adapter(a, old)
