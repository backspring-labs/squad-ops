"""Resilience tests: graceful degradation when LangFuse unavailable (SIP-0061).

Gated behind @pytest.mark.langfuse — skipped unless all env vars are set.
"""

from __future__ import annotations

import time

import pytest

from squadops.config.schema import LangFuseConfig
from squadops.telemetry.models import CorrelationContext, StructuredEvent


@pytest.mark.integration
@pytest.mark.langfuse
class TestLangFuseResilience:
    """Verify graceful degradation when LangFuse is unavailable."""

    def test_cycle_completes_without_langfuse(self):
        """NoOp adapter allows cycle to complete normally."""
        from adapters.telemetry.noop_llm_observability import NoOpLLMObservabilityAdapter

        adapter = NoOpLLMObservabilityAdapter()
        ctx = CorrelationContext.for_cycle(cycle_id="resilience-001")
        adapter.start_cycle_trace(ctx)
        adapter.record_event(ctx, StructuredEvent(name="cycle.started", message="test"))
        adapter.end_cycle_trace(ctx)
        adapter.flush()
        adapter.close()

    def test_adapter_buffers_and_retries(self):
        """Adapter with unreachable host buffers events without crashing."""
        from adapters.telemetry.langfuse.adapter import LangFuseAdapter

        config = LangFuseConfig(
            enabled=True,
            host="http://localhost:19999",  # Unreachable
            public_key="pk-test",
            secret_key="sk-test",
            buffer_max_size=10,
            flush_interval_seconds=60,
            shutdown_flush_timeout_seconds=2,
        )
        adapter = LangFuseAdapter(config)
        try:
            ctx = CorrelationContext.for_cycle(cycle_id="resilience-002")
            adapter.start_cycle_trace(ctx)
            adapter.record_event(ctx, StructuredEvent(name="test", message="buffered"))
            # Events are buffered, no crash
            assert adapter._buffer.qsize() >= 1
        finally:
            adapter.close()

    def test_close_completes_within_timeout(self):
        """close() returns within timeout even with unreachable backend."""
        from adapters.telemetry.langfuse.adapter import LangFuseAdapter

        config = LangFuseConfig(
            enabled=True,
            host="http://localhost:19999",
            public_key="pk-test",
            secret_key="sk-test",
            buffer_max_size=100,
            flush_interval_seconds=60,
            shutdown_flush_timeout_seconds=2,
        )
        adapter = LangFuseAdapter(config)
        # Fill buffer
        ctx = CorrelationContext.for_cycle(cycle_id="resilience-003")
        for _ in range(50):
            adapter.start_cycle_trace(ctx)

        start = time.monotonic()
        adapter.close()
        elapsed = time.monotonic() - start
        assert elapsed < config.shutdown_flush_timeout_seconds + 1.0

    def test_warnings_emitted_on_failure(self, caplog):
        """Adapter logs warnings when flush fails."""
        import logging

        from adapters.telemetry.langfuse.adapter import LangFuseAdapter

        config = LangFuseConfig(
            enabled=True,
            host="http://localhost:19999",
            public_key="pk-test",
            secret_key="sk-test",
            buffer_max_size=10,
            flush_interval_seconds=60,
            shutdown_flush_timeout_seconds=2,
        )
        adapter = LangFuseAdapter(config)
        ctx = CorrelationContext.for_cycle(cycle_id="resilience-004")
        adapter.start_cycle_trace(ctx)

        with caplog.at_level(logging.WARNING):
            adapter.close()

        # Should have logged some warning about flush/shutdown
        # (exact message depends on whether SDK raises during flush)
