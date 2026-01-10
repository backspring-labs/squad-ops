"""
Telemetry Client abstraction layer for SquadOps agents.

Provides a protocol-based interface for different telemetry providers
(OpenTelemetry, AWS CloudWatch/X-Ray, Azure Application Insights, GCP Cloud Trace/Monitoring)
with platform-aware routing and graceful degradation.
"""

from .client import TelemetryClient
from .router import TelemetryRouter

__all__ = [
    'TelemetryClient',
    'TelemetryRouter',
]

