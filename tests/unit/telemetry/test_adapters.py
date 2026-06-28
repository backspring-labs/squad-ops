"""Unit tests for telemetry adapters."""

from contextlib import contextmanager
from io import StringIO

import pytest
from opentelemetry import metrics, trace
from opentelemetry.metrics import _internal as _otel_metrics_internal
from opentelemetry.sdk import trace as _otel_sdk_trace
from opentelemetry.sdk.metrics import _internal as _otel_sdk_metrics
from opentelemetry.sdk.trace import TracerProvider as _SDKTracerProvider
from opentelemetry.util._once import Once

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


class _NoopAtexit:
    """Stand-in for the ``atexit`` module that drops registrations.

    ``register`` returns ``None`` (not ``func``) so the SDK stores a ``None``
    ``_atexit_handler`` — making "no exit hook registered" observable.
    """

    @staticmethod
    def register(func, *args, **kwargs):
        return None

    @staticmethod
    def unregister(func):
        return None


@contextmanager
def _isolate_otel_globals():
    """Isolate the process-global OpenTelemetry providers for a test (#239).

    ``OTelAdapter._ensure_initialized`` installs PROCESS-GLOBAL tracer/meter
    providers (``otel.py``: ``trace.set_tracer_provider`` /
    ``metrics.set_meter_provider``), and each SDK provider registers an
    ``atexit`` shutdown hook in its constructor. A test that initializes the
    adapter with a :class:`BrokenExporter` therefore leaves a provider whose
    shutdown raises; that hook fires at interpreter exit and prints
    ``Simulated shutdown failure`` on *every* regression run. (Calling
    ``provider.shutdown()`` to clean up doesn't help — it raises on the broken
    exporter *before* it reaches its own ``atexit.unregister`` line.)

    So this context manager **suppresses atexit registration** for any provider
    created in the body (scoped to the two SDK modules), resets OTel's set-once
    guard so the body's ``set_*_provider`` calls take effect deterministically,
    and restores every global on exit. Nothing the body installs survives to
    interpreter exit.
    """
    saved_tracer = trace._TRACER_PROVIDER
    saved_tracer_once = trace._TRACER_PROVIDER_SET_ONCE
    saved_meter = _otel_metrics_internal._METER_PROVIDER
    saved_meter_once = _otel_metrics_internal._METER_PROVIDER_SET_ONCE

    # The SDK reaches atexit two different ways: sdk.trace via the `atexit`
    # module attribute, sdk.metrics._internal via names imported from atexit.
    saved_trace_atexit = _otel_sdk_trace.atexit
    saved_metrics_register = _otel_sdk_metrics.register
    saved_metrics_unregister = _otel_sdk_metrics.unregister

    _otel_sdk_trace.atexit = _NoopAtexit
    _otel_sdk_metrics.register = _NoopAtexit.register
    _otel_sdk_metrics.unregister = _NoopAtexit.unregister
    # Fresh set-once guards so set_*_provider in the body actually installs.
    trace._TRACER_PROVIDER_SET_ONCE = Once()
    _otel_metrics_internal._METER_PROVIDER_SET_ONCE = Once()
    try:
        yield
    finally:
        _otel_sdk_trace.atexit = saved_trace_atexit
        _otel_sdk_metrics.register = saved_metrics_register
        _otel_sdk_metrics.unregister = saved_metrics_unregister
        trace._TRACER_PROVIDER = saved_tracer
        trace._TRACER_PROVIDER_SET_ONCE = saved_tracer_once
        _otel_metrics_internal._METER_PROVIDER = saved_meter
        _otel_metrics_internal._METER_PROVIDER_SET_ONCE = saved_meter_once


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

    @pytest.fixture(autouse=True)
    def _isolate_otel_globals(self):
        """Every OTelAdapter test installs process-global providers; isolate them
        so none leaks a broken provider whose atexit hook fires at exit (#239)."""
        with _isolate_otel_globals():
            yield

    def test_otel_adapter_does_not_raise_on_exporter_failure(self):
        """OTelAdapter must swallow exceptions from broken exporter."""
        adapter = OTelAdapter(span_exporter=BrokenExporter(), metric_exporter=BrokenExporter())
        adapter.counter("test", 1)  # Must not raise
        adapter.gauge("test", 1)  # Must not raise
        adapter.histogram("test", 1)  # Must not raise
        adapter.emit(StructuredEvent(name="test", message="msg"))  # Must not raise

    def test_broken_exporter_init_registers_no_atexit_hook(self):
        """#239 regression: a BrokenExporter adapter installs a real global tracer
        provider (init sets the tracer, then fails at the metric reader — so it's
        the *tracer* provider that leaks, which is why the original traceback was
        ``TracerProvider.shutdown``). Unguarded, that provider registers an atexit
        shutdown hook that raises ``Simulated shutdown failure`` at interpreter
        exit on every run. Under isolation the real tracer init still happens, but
        no atexit hook is registered and the prior globals are restored."""
        before_tracer = trace.get_tracer_provider()
        before_meter = metrics.get_meter_provider()

        with _isolate_otel_globals():
            adapter = OTelAdapter(span_exporter=BrokenExporter(), metric_exporter=BrokenExporter())
            adapter.counter("test", 1)

            tracer_provider = trace.get_tracer_provider()
            # The adapter really did install a real SDK tracer provider — the
            # leak the issue is about (exercises the _ensure_initialized path).
            assert isinstance(tracer_provider, _SDKTracerProvider)
            # ... but with NO atexit hook (the crux of #239): nothing fires at
            # interpreter exit.
            assert tracer_provider._atexit_handler is None

        # Globals restored to the pre-test providers.
        assert trace.get_tracer_provider() is before_tracer
        assert metrics.get_meter_provider() is before_meter

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

from adapters.telemetry.noop_llm_observability import NoOpLLMObservabilityAdapter  # noqa: E402
from squadops.telemetry.models import (  # noqa: E402
    CorrelationContext,
    GenerationRecord,
    PromptLayer,
    PromptLayerMetadata,
)


class TestNoOpLLMObservabilityAdapter:
    """Tests for NoOpLLMObservabilityAdapter (SIP-0061)."""

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
        result = asyncio.run(adapter.health())
        assert result["status"] == "ok"
        assert result["backend"] == "noop"
        assert result["details"] == {}

    def test_health_returns_degraded_when_configured(self):
        import asyncio

        adapter = NoOpLLMObservabilityAdapter(
            health_status="degraded", health_reason="langfuse SDK not installed"
        )
        result = asyncio.run(adapter.health())
        assert result["status"] == "degraded"
        assert result["details"]["reason"] == "langfuse SDK not installed"
