"""Telemetry domain models.

Frozen dataclasses for structured events, spans, and metric types.
Part of SIP-0.8.7 Infrastructure Ports Migration.
"""
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any


class MetricType(Enum):
    """Metric type enumeration for MetricsPort."""

    COUNTER = "counter"
    GAUGE = "gauge"
    HISTOGRAM = "histogram"


@dataclass(frozen=True)
class Span:
    """Distributed tracing span.

    Immutable representation of a trace span for EventPort.
    """

    name: str
    trace_id: str
    span_id: str
    parent_span_id: str | None = None
    start_time: datetime | None = None
    end_time: datetime | None = None
    attributes: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True)
class StructuredEvent:
    """Structured log/event for EventPort.emit().

    Immutable event representation with optional span correlation.
    """

    name: str
    message: str
    level: str = "info"  # debug, info, warning, error
    attributes: tuple[tuple[str, Any], ...] = ()
    timestamp: datetime | None = None
    span_id: str | None = None  # Optional correlation to active span
