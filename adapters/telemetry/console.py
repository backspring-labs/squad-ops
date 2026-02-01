"""Console telemetry adapter.

DEV-ONLY adapter that logs to stdout. Not for production use.
Part of SIP-0.8.7 Infrastructure Ports Migration.
"""
import sys
import uuid
from datetime import datetime, timezone
from typing import TextIO

from squadops.ports.telemetry.events import EventPort
from squadops.ports.telemetry.metrics import MetricsPort
from squadops.telemetry.models import Span, StructuredEvent


class ConsoleAdapter(MetricsPort, EventPort):
    """Console adapter for local development.

    DEV MODE ONLY - stdout writes can block (pipes, CI, logging handlers).
    Not recommended for production. Best-effort blocking risk accepted.

    All methods swallow exceptions internally to maintain non-raising contract.
    """

    def __init__(self, output: TextIO | None = None):
        """Initialize console adapter.

        Args:
            output: Output stream (default: sys.stdout).
                    Injection allows unit tests to pass BrokenWriter to verify error handling.
        """
        self._output = output or sys.stdout

    def _safe_write(self, message: str) -> None:
        """Write to output, swallowing any errors."""
        try:
            self._output.write(message + "\n")
            self._output.flush()
        except Exception:
            # Swallow all errors - non-blocking contract
            pass

    def counter(
        self,
        name: str,
        value: float = 1,
        labels: dict[str, str] | None = None,
    ) -> None:
        """Log counter metric to console."""
        labels_str = f" {labels}" if labels else ""
        self._safe_write(f"[METRIC:COUNTER] {name}={value}{labels_str}")

    def gauge(
        self,
        name: str,
        value: float,
        labels: dict[str, str] | None = None,
    ) -> None:
        """Log gauge metric to console."""
        labels_str = f" {labels}" if labels else ""
        self._safe_write(f"[METRIC:GAUGE] {name}={value}{labels_str}")

    def histogram(
        self,
        name: str,
        value: float,
        labels: dict[str, str] | None = None,
    ) -> None:
        """Log histogram metric to console."""
        labels_str = f" {labels}" if labels else ""
        self._safe_write(f"[METRIC:HISTOGRAM] {name}={value}{labels_str}")

    def emit(self, event: StructuredEvent) -> None:
        """Log structured event to console."""
        attrs_str = f" {dict(event.attributes)}" if event.attributes else ""
        self._safe_write(f"[EVENT:{event.level.upper()}] {event.name}: {event.message}{attrs_str}")

    def start_span(
        self,
        name: str,
        parent: Span | None = None,
        attributes: dict[str, str] | None = None,
    ) -> Span:
        """Start a span and log to console."""
        span = Span(
            name=name,
            trace_id=parent.trace_id if parent else str(uuid.uuid4()),
            span_id=str(uuid.uuid4()),
            parent_span_id=parent.span_id if parent else None,
            start_time=datetime.now(timezone.utc),
            attributes=tuple(attributes.items()) if attributes else (),
        )
        attrs_str = f" {attributes}" if attributes else ""
        self._safe_write(f"[SPAN:START] {name} trace={span.trace_id[:8]}{attrs_str}")
        return span

    def end_span(self, span: Span) -> None:
        """End a span and log to console."""
        self._safe_write(f"[SPAN:END] {span.name} trace={span.trace_id[:8]}")
