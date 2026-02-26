"""OpenTelemetry telemetry adapter.

Production-ready adapter using OpenTelemetry SDK.
Part of SIP-0.8.7 Infrastructure Ports Migration.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from squadops.ports.telemetry.events import EventPort
from squadops.ports.telemetry.metrics import MetricsPort
from squadops.telemetry.models import Span, StructuredEvent

if TYPE_CHECKING:
    from opentelemetry.sdk.metrics.export import MetricExporter
    from opentelemetry.sdk.trace.export import SpanExporter


class OTelAdapter(MetricsPort, EventPort):
    """OpenTelemetry adapter with injectable exporters for testing.

    Production-ready telemetry adapter using OpenTelemetry SDK.
    Uses BatchSpanProcessor for non-blocking trace export.

    All methods swallow exceptions internally to maintain non-raising contract.
    """

    def __init__(
        self,
        span_exporter: SpanExporter | None = None,
        metric_exporter: MetricExporter | None = None,
        service_name: str = "squadops",
    ):
        """Initialize OTel adapter.

        Args:
            span_exporter: Custom span exporter (default: OTLPSpanExporter from env)
            metric_exporter: Custom metric exporter (default: OTLPMetricExporter from env)
            service_name: Service name for telemetry

        Injection allows unit tests to pass BrokenExporter to verify error handling.
        """
        self._service_name = service_name
        self._span_exporter = span_exporter
        self._metric_exporter = metric_exporter
        self._tracer: Any = None
        self._meter: Any = None
        self._counters: dict[str, Any] = {}
        self._gauges: dict[str, Any] = {}
        self._histograms: dict[str, Any] = {}
        self._active_spans: dict[str, Any] = {}
        self._initialized = False

    def _ensure_initialized(self) -> bool:
        """Lazily initialize OpenTelemetry SDK. Returns True if ready."""
        if self._initialized:
            return True

        try:
            from opentelemetry import metrics, trace
            from opentelemetry.sdk.metrics import MeterProvider
            from opentelemetry.sdk.metrics.export import (
                ConsoleMetricExporter,
                PeriodicExportingMetricReader,
            )
            from opentelemetry.sdk.resources import Resource
            from opentelemetry.sdk.trace import TracerProvider
            from opentelemetry.sdk.trace.export import (
                BatchSpanProcessor,
                ConsoleSpanExporter,
            )

            resource = Resource.create({"service.name": self._service_name})

            # Set up tracing
            span_exporter = self._span_exporter or ConsoleSpanExporter()
            tracer_provider = TracerProvider(resource=resource)
            tracer_provider.add_span_processor(BatchSpanProcessor(span_exporter))
            trace.set_tracer_provider(tracer_provider)
            self._tracer = trace.get_tracer(self._service_name)

            # Set up metrics
            metric_exporter = self._metric_exporter or ConsoleMetricExporter()
            reader = PeriodicExportingMetricReader(metric_exporter, export_interval_millis=5000)
            meter_provider = MeterProvider(resource=resource, metric_readers=[reader])
            metrics.set_meter_provider(meter_provider)
            self._meter = metrics.get_meter(self._service_name)

            self._initialized = True
            return True
        except Exception:
            # Swallow initialization errors - non-blocking contract
            return False

    def counter(
        self,
        name: str,
        value: float = 1,
        labels: dict[str, str] | None = None,
    ) -> None:
        """Increment a counter metric."""
        try:
            if not self._ensure_initialized():
                return
            if name not in self._counters:
                self._counters[name] = self._meter.create_counter(name)
            self._counters[name].add(value, labels or {})
        except Exception:
            # Swallow all errors - non-blocking contract
            pass

    def gauge(
        self,
        name: str,
        value: float,
        labels: dict[str, str] | None = None,
    ) -> None:
        """Set a gauge metric value."""
        try:
            if not self._ensure_initialized():
                return
            if name not in self._gauges:
                self._gauges[name] = self._meter.create_up_down_counter(name)
            # OTel doesn't have a direct gauge; using up_down_counter as approximation
            self._gauges[name].add(value, labels or {})
        except Exception:
            # Swallow all errors - non-blocking contract
            pass

    def histogram(
        self,
        name: str,
        value: float,
        labels: dict[str, str] | None = None,
    ) -> None:
        """Record a histogram observation."""
        try:
            if not self._ensure_initialized():
                return
            if name not in self._histograms:
                self._histograms[name] = self._meter.create_histogram(name)
            self._histograms[name].record(value, labels or {})
        except Exception:
            # Swallow all errors - non-blocking contract
            pass

    def emit(self, event: StructuredEvent) -> None:
        """Emit a structured event as a span event."""
        try:
            if not self._ensure_initialized():
                return
            # If we have an active span context, add the event to it
            # Otherwise, just log (OTel events are typically span-scoped)
            from opentelemetry import trace

            current_span = trace.get_current_span()
            if current_span and current_span.is_recording():
                current_span.add_event(
                    name=event.name,
                    attributes={
                        "message": event.message,
                        "level": event.level,
                        **dict(event.attributes),
                    },
                )
        except Exception:
            # Swallow all errors - non-blocking contract
            pass

    def start_span(
        self,
        name: str,
        parent: Span | None = None,
        attributes: dict[str, str] | None = None,
    ) -> Span:
        """Start a new tracing span."""
        span_id = str(uuid.uuid4())
        try:
            if self._ensure_initialized() and self._tracer:
                otel_span = self._tracer.start_span(name, attributes=attributes or {})
                self._active_spans[span_id] = otel_span
        except Exception:
            # Swallow errors - still return a domain Span
            pass

        return Span(
            name=name,
            trace_id=parent.trace_id if parent else str(uuid.uuid4()),
            span_id=span_id,
            parent_span_id=parent.span_id if parent else None,
            start_time=datetime.now(UTC),
            attributes=tuple(attributes.items()) if attributes else (),
        )

    def end_span(self, span: Span) -> None:
        """End a tracing span."""
        try:
            otel_span = self._active_spans.pop(span.span_id, None)
            if otel_span:
                otel_span.end()
        except Exception:
            # Swallow all errors - non-blocking contract
            pass
