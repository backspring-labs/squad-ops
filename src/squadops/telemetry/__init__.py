"""Telemetry domain layer.

Provides domain models for telemetry operations:
- MetricType: Enum for counter, gauge, histogram
- Span: Distributed tracing span
- StructuredEvent: Structured log/event

Part of SIP-0.8.7 Infrastructure Ports Migration.
"""

from squadops.telemetry.exceptions import TelemetryError
from squadops.telemetry.models import MetricType, Span, StructuredEvent

__all__ = [
    "MetricType",
    "Span",
    "StructuredEvent",
    "TelemetryError",
]
