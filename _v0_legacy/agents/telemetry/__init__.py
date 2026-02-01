"""
Telemetry Client abstraction layer for SquadOps agents.

DEPRECATED: This module is deprecated as of SIP-0.8.7.
Use squadops.ports.telemetry and adapters.telemetry instead.

Provides a protocol-based interface for different telemetry providers
(OpenTelemetry, AWS CloudWatch/X-Ray, Azure Application Insights, GCP Cloud Trace/Monitoring)
with platform-aware routing and graceful degradation.
"""
import warnings

warnings.warn(
    "Importing from _v0_legacy.agents.telemetry is deprecated. "
    "Use squadops.ports.telemetry and adapters.telemetry instead. "
    "This module will be removed in version 0.9.0.",
    DeprecationWarning,
    stacklevel=2,
)

# Legacy exports (preserved for backwards compatibility)
from .client import TelemetryClient
from .router import TelemetryRouter

# Re-export new canonical symbols for migration convenience
from adapters.telemetry.factory import (
    create_event_provider,
    create_metrics_provider,
    create_telemetry_provider,
)
from squadops.telemetry.models import MetricType, Span, StructuredEvent

__all__ = [
    # Legacy (deprecated)
    'TelemetryClient',
    'TelemetryRouter',
    # New (canonical)
    'create_event_provider',
    'create_metrics_provider',
    'create_telemetry_provider',
    'MetricType',
    'Span',
    'StructuredEvent',
]

