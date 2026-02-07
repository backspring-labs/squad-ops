"""Unit tests for telemetry adapters."""

from io import StringIO

from adapters.telemetry.console import ConsoleAdapter
from adapters.telemetry.null import NullAdapter
from adapters.telemetry.otel import OTelAdapter
from squadops.telemetry.models import StructuredEvent

# Test fixtures for error handling verification


class BrokenExporter:
    """Exporter that raises on every call."""

    def export(self, *args, **kwargs):
        raise RuntimeError("Simulated exporter failure")

    def shutdown(self, *args, **kwargs):
        raise RuntimeError("Simulated shutdown failure")

    def force_flush(self, *args, **kwargs):
        raise RuntimeError("Simulated flush failure")


class BrokenWriter:
    """File-like object that raises on write."""

    def write(self, *args):
        raise OSError("Simulated stdout failure")

    def flush(self):
        raise OSError("Simulated flush failure")


class TestNullAdapter:
    """Tests for NullAdapter."""

    def test_counter_does_not_raise(self):
        adapter = NullAdapter()
        adapter.counter("test", 1)  # Must not raise
        adapter.counter("test", 1, {"label": "value"})  # Must not raise

    def test_gauge_does_not_raise(self):
        adapter = NullAdapter()
        adapter.gauge("test", 42.0)  # Must not raise
        adapter.gauge("test", 42.0, {"label": "value"})  # Must not raise

    def test_histogram_does_not_raise(self):
        adapter = NullAdapter()
        adapter.histogram("test", 1.5)  # Must not raise
        adapter.histogram("test", 1.5, {"label": "value"})  # Must not raise

    def test_emit_does_not_raise(self):
        adapter = NullAdapter()
        event = StructuredEvent(name="test", message="msg")
        adapter.emit(event)  # Must not raise

    def test_start_span_returns_span(self):
        adapter = NullAdapter()
        span = adapter.start_span("test")
        assert span.name == "test"
        assert span.trace_id == "null-trace"
        assert span.span_id == "null-span"

    def test_start_span_with_attributes(self):
        adapter = NullAdapter()
        span = adapter.start_span("test", attributes={"key": "value"})
        assert span.attributes == (("key", "value"),)

    def test_end_span_does_not_raise(self):
        adapter = NullAdapter()
        span = adapter.start_span("test")
        adapter.end_span(span)  # Must not raise

    def test_span_context_manager_works(self):
        adapter = NullAdapter()
        with adapter.span("test") as span:
            assert span.name == "test"


class TestConsoleAdapter:
    """Tests for ConsoleAdapter."""

    def test_counter_writes_to_output(self):
        output = StringIO()
        adapter = ConsoleAdapter(output=output)
        adapter.counter("test_metric", 5)
        assert "[METRIC:COUNTER] test_metric=5" in output.getvalue()

    def test_gauge_writes_to_output(self):
        output = StringIO()
        adapter = ConsoleAdapter(output=output)
        adapter.gauge("test_metric", 42.5)
        assert "[METRIC:GAUGE] test_metric=42.5" in output.getvalue()

    def test_histogram_writes_to_output(self):
        output = StringIO()
        adapter = ConsoleAdapter(output=output)
        adapter.histogram("test_metric", 1.5)
        assert "[METRIC:HISTOGRAM] test_metric=1.5" in output.getvalue()

    def test_emit_writes_to_output(self):
        output = StringIO()
        adapter = ConsoleAdapter(output=output)
        event = StructuredEvent(name="test_event", message="test message", level="warning")
        adapter.emit(event)
        assert "[EVENT:WARNING] test_event: test message" in output.getvalue()

    def test_start_span_writes_to_output(self):
        output = StringIO()
        adapter = ConsoleAdapter(output=output)
        span = adapter.start_span("test_span")
        assert "[SPAN:START] test_span" in output.getvalue()
        assert span.name == "test_span"

    def test_end_span_writes_to_output(self):
        output = StringIO()
        adapter = ConsoleAdapter(output=output)
        span = adapter.start_span("test_span")
        adapter.end_span(span)
        assert "[SPAN:END] test_span" in output.getvalue()

    def test_console_adapter_does_not_raise_on_io_error(self):
        """ConsoleAdapter must swallow output stream errors."""
        adapter = ConsoleAdapter(output=BrokenWriter())
        adapter.counter("test", 1)  # Must not raise
        adapter.gauge("test", 1)  # Must not raise
        adapter.histogram("test", 1)  # Must not raise
        adapter.emit(StructuredEvent(name="test", message="msg"))  # Must not raise
        span = adapter.start_span("test")  # Must not raise
        adapter.end_span(span)  # Must not raise


class TestOTelAdapter:
    """Tests for OTelAdapter."""

    def test_otel_adapter_does_not_raise_on_exporter_failure(self):
        """OTelAdapter must swallow exceptions from broken exporter."""
        adapter = OTelAdapter(span_exporter=BrokenExporter(), metric_exporter=BrokenExporter())
        adapter.counter("test", 1)  # Must not raise
        adapter.gauge("test", 1)  # Must not raise
        adapter.histogram("test", 1)  # Must not raise
        adapter.emit(StructuredEvent(name="test", message="msg"))  # Must not raise

    def test_start_span_returns_span(self):
        adapter = OTelAdapter()
        span = adapter.start_span("test")
        assert span.name == "test"
        assert span.trace_id is not None
        assert span.span_id is not None

    def test_start_span_with_attributes(self):
        adapter = OTelAdapter()
        span = adapter.start_span("test", attributes={"key": "value"})
        assert span.attributes == (("key", "value"),)

    def test_end_span_does_not_raise(self):
        adapter = OTelAdapter()
        span = adapter.start_span("test")
        adapter.end_span(span)  # Must not raise

    def test_span_context_manager_works(self):
        adapter = OTelAdapter()
        with adapter.span("test") as span:
            assert span.name == "test"

    def test_counter_with_labels(self):
        adapter = OTelAdapter()
        adapter.counter("test", 1, {"env": "test"})  # Must not raise

    def test_gauge_with_labels(self):
        adapter = OTelAdapter()
        adapter.gauge("test", 42, {"env": "test"})  # Must not raise

    def test_histogram_with_labels(self):
        adapter = OTelAdapter()
        adapter.histogram("test", 1.5, {"env": "test"})  # Must not raise


# ---------------------------------------------------------------------------
# SIP-0061: NoOpLLMObservabilityAdapter tests
# ---------------------------------------------------------------------------

from adapters.telemetry.noop_llm_observability import NoOpLLMObservabilityAdapter
from squadops.ports.telemetry.llm_observability import LLMObservabilityPort
from squadops.telemetry.models import (
    CorrelationContext,
    GenerationRecord,
    PromptLayer,
    PromptLayerMetadata,
)


class TestNoOpLLMObservabilityAdapter:
    """Tests for NoOpLLMObservabilityAdapter (SIP-0061)."""

    def test_satisfies_port_contract(self):
        adapter = NoOpLLMObservabilityAdapter()
        assert isinstance(adapter, LLMObservabilityPort)

    def test_all_methods_are_noop(self):
        adapter = NoOpLLMObservabilityAdapter()
        ctx = CorrelationContext(cycle_id="c1", pulse_id="p1", task_id="t1")
        record = GenerationRecord(generation_id="g1", model="m", prompt_text="p", response_text="r")
        layers = PromptLayerMetadata(
            prompt_layer_set_id="PLS-1",
            layers=(PromptLayer(layer_type="system", layer_id="sys-1"),),
        )
        event = StructuredEvent(name="test", message="msg")

        # None of these should raise
        adapter.start_cycle_trace(ctx)
        adapter.end_cycle_trace(ctx)
        adapter.start_pulse_span(ctx)
        adapter.end_pulse_span(ctx)
        adapter.start_task_span(ctx)
        adapter.end_task_span(ctx)
        adapter.record_generation(ctx, record, layers)
        adapter.record_event(ctx, event)
        adapter.flush()
        adapter.close()

    def test_health_returns_ok_by_default(self):
        import asyncio

        adapter = NoOpLLMObservabilityAdapter()
        result = asyncio.get_event_loop().run_until_complete(adapter.health())
        assert result["status"] == "ok"
        assert result["backend"] == "noop"
        assert result["details"] == {}

    def test_health_returns_degraded_when_configured(self):
        import asyncio

        adapter = NoOpLLMObservabilityAdapter(
            health_status="degraded", health_reason="langfuse SDK not installed"
        )
        result = asyncio.get_event_loop().run_until_complete(adapter.health())
        assert result["status"] == "degraded"
        assert result["details"]["reason"] == "langfuse SDK not installed"
