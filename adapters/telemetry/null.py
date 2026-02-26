"""Null telemetry adapter.

No-op implementation for testing. Does nothing, never raises.
Part of SIP-0.8.7 Infrastructure Ports Migration.
"""

from squadops.ports.telemetry.events import EventPort
from squadops.ports.telemetry.metrics import MetricsPort
from squadops.telemetry.models import Span, StructuredEvent


class NullAdapter(MetricsPort, EventPort):
    """No-op telemetry adapter for testing.

    All methods are no-ops that never raise exceptions.
    Use this adapter in tests to avoid telemetry side effects.
    """

    def counter(
        self,
        name: str,
        value: float = 1,
        labels: dict[str, str] | None = None,
    ) -> None:
        """No-op counter."""
        pass

    def gauge(
        self,
        name: str,
        value: float,
        labels: dict[str, str] | None = None,
    ) -> None:
        """No-op gauge."""
        pass

    def histogram(
        self,
        name: str,
        value: float,
        labels: dict[str, str] | None = None,
    ) -> None:
        """No-op histogram."""
        pass

    def emit(self, event: StructuredEvent) -> None:
        """No-op event emission."""
        pass

    def start_span(
        self,
        name: str,
        parent: Span | None = None,
        attributes: dict[str, str] | None = None,
    ) -> Span:
        """Return a dummy span."""
        return Span(
            name=name,
            trace_id="null-trace",
            span_id="null-span",
            parent_span_id=parent.span_id if parent else None,
            attributes=tuple(attributes.items()) if attributes else (),
        )

    def end_span(self, span: Span) -> None:
        """No-op span end."""
        pass
