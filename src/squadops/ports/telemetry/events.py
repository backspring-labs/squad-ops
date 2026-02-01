"""Events port interface.

Abstract base class for structured event and tracing adapters.
Part of SIP-0.8.7 Infrastructure Ports Migration.
"""
from abc import ABC, abstractmethod
from contextlib import contextmanager
from typing import Iterator

from squadops.telemetry.models import Span, StructuredEvent


class EventPort(ABC):
    """Port interface for structured events and distributed tracing.

    Adapters must implement emit, start_span, and end_span methods.
    The span() context manager is provided as a convenience wrapper.
    All implementations must be non-blocking (enqueue/buffer, do not block caller).
    """

    @abstractmethod
    def emit(self, event: StructuredEvent) -> None:
        """Emit a structured event.

        Args:
            event: The structured event to emit
        """
        ...

    @abstractmethod
    def start_span(
        self,
        name: str,
        parent: Span | None = None,
        attributes: dict[str, str] | None = None,
    ) -> Span:
        """Start a new tracing span.

        Args:
            name: Span name
            parent: Optional parent span for nested tracing
            attributes: Optional attributes to attach to the span

        Returns:
            The created Span object
        """
        ...

    @abstractmethod
    def end_span(self, span: Span) -> None:
        """End a tracing span.

        Args:
            span: The span to end
        """
        ...

    @contextmanager
    def span(
        self,
        name: str,
        attributes: dict[str, str] | None = None,
    ) -> Iterator[Span]:
        """Context manager wrapping start_span/end_span.

        Convenience wrapper that ensures spans are properly closed.
        Adapters do NOT implement this - it's provided by the base class.

        Args:
            name: Span name
            attributes: Optional attributes to attach to the span

        Yields:
            The created Span object
        """
        s = self.start_span(name, attributes=attributes)
        try:
            yield s
        finally:
            self.end_span(s)
