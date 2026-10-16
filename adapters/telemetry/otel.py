"""OpenTelemetry telemetry adapter.

Production-ready adapter using OpenTelemetry SDK.
Part of SIP-0.8.7 Infrastructure Ports Migration.
"""

from __future__ import annotations

import logging
import uuid
from collections.abc import Sequence
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from squadops.ports.telemetry.events import EventPort
from squadops.ports.telemetry.metrics import MetricsPort
from squadops.telemetry.models import Span, StructuredEvent

if TYPE_CHECKING:
    from opentelemetry.sdk.metrics.export import MetricExporter
    from opentelemetry.sdk.trace.export import SpanExporter

logger = logging.getLogger(__name__)


def resource_attributes(service_name: str) -> dict[str, str]:
    """The resource every span and metric carries (#1720): the service, the release it runs and
    the commit its image was built from.

    The revision is left out when the build recorded none. An absent attribute says "not
    known"; a placeholder value would read as a commit.
    """
    from squadops._version import resolve_git_sha, resolve_version

    attributes = {"service.name": service_name, "service.version": resolve_version()}
    revision = resolve_git_sha()
    if revision:
        attributes["vcs.ref.head.revision"] = revision
    return attributes


def otlp_exporters(endpoint: str) -> tuple[Any, Any]:
    """The span and metric exporters that send to the collector at ``endpoint`` over OTLP gRPC
    (#2203). An ``http://`` endpoint is sent without TLS, as the compose network's collector is."""
    from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter
    from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter

    insecure = endpoint.startswith("http://")
    return (
        OTLPSpanExporter(endpoint=endpoint, insecure=insecure),
        OTLPMetricExporter(endpoint=endpoint, insecure=insecure),
    )


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
        otlp_endpoint: str | None = None,
    ):
        """Initialize OTel adapter.

        Args:
            span_exporter: Custom span exporter (default: OTLP to ``otlp_endpoint``)
            metric_exporter: Custom metric exporter (default: OTLP to ``otlp_endpoint``)
            service_name: Service name for telemetry
            otlp_endpoint: The collector the default exporters send to (#2203). Without it, and
                without an injected exporter, the adapter writes to the console: what it always
                did, which is why nothing reached the collector.

        Injection allows unit tests to pass BrokenExporter to verify error handling.
        """
        self._service_name = service_name
        self._span_exporter = span_exporter
        self._metric_exporter = metric_exporter
        self._otlp_endpoint = otlp_endpoint
        self._tracer: Any = None
        self._meter: Any = None
        self._counters: dict[str, Any] = {}
        self._gauges: dict[str, Any] = {}
        self._histograms: dict[str, Any] = {}
        self._active_spans: dict[str, Any] = {}
        self._initialized = False
        self._init_failure_logged = False

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

            resource = Resource.create(resource_attributes(self._service_name))

            default_span, default_metric = (
                otlp_exporters(self._otlp_endpoint)
                if self._otlp_endpoint
                else (ConsoleSpanExporter(), ConsoleMetricExporter())
            )

            # Set up tracing
            span_exporter = self._span_exporter or default_span
            tracer_provider = TracerProvider(resource=resource)
            tracer_provider.add_span_processor(BatchSpanProcessor(span_exporter))
            trace.set_tracer_provider(tracer_provider)
            self._tracer = trace.get_tracer(self._service_name)

            # Set up metrics
            metric_exporter = self._metric_exporter or default_metric
            reader = PeriodicExportingMetricReader(metric_exporter, export_interval_millis=5000)
            meter_provider = MeterProvider(resource=resource, metric_readers=[reader])
            metrics.set_meter_provider(meter_provider)
            self._meter = metrics.get_meter(self._service_name)

            self._initialized = True
            return True
        except Exception as exc:
            # Swallow initialization errors - non-blocking contract. But say so, once: a missing
            # SDK read as silence twice, in the agents' image (#2203) and then the runtime's (#2371).
            if not self._init_failure_logged:
                self._init_failure_logged = True
                logger.warning(
                    "OpenTelemetry could not initialize, so no metric or span leaves this "
                    "process: %s: %s",
                    type(exc).__name__,
                    exc,
                )
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
        """Set a gauge metric value: the reading replaces the last one for its labels (#2260).

        A synchronous gauge, not an up-down counter: a counter's ``add`` summed every reading into
        the last, so a gauge set to 5 and then 3 read 8."""
        try:
            if not self._ensure_initialized():
                return
            if name not in self._gauges:
                self._gauges[name] = self._meter.create_gauge(name)
            self._gauges[name].set(value, labels or {})
        except Exception:
            # Swallow all errors - non-blocking contract
            pass

    def histogram(
        self,
        name: str,
        value: float,
        labels: dict[str, str] | None = None,
        *,
        boundaries: Sequence[float] | None = None,
    ) -> None:
        """Record a histogram observation, in the caller's buckets where it gives them (#2260).

        Without boundaries the SDK's defaults apply (0, 5, 10, 25 … 10,000), which put nearly every
        decode rate in one bucket and over half the 27B's prompts above the last."""
        try:
            if not self._ensure_initialized():
                return
            if name not in self._histograms:
                advisory = (
                    {"explicit_bucket_boundaries_advisory": list(boundaries)} if boundaries else {}
                )
                self._histograms[name] = self._meter.create_histogram(name, **advisory)
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
