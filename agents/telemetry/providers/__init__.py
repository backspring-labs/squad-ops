"""
Telemetry provider implementations for SquadOps agents.

Supports multiple telemetry backends:
- OpenTelemetry (local/Prometheus setup)
- AWS CloudWatch/X-Ray
- Azure Application Insights
- GCP Cloud Trace/Monitoring
- Null (no-op for testing/disabled)
"""

from .null_client import NullTelemetryClient
from .opentelemetry_client import OpenTelemetryClient

# Cloud providers will be added in subsequent tasks
# from .aws_client import AWSTelemetryClient
# from .azure_client import AzureTelemetryClient
# from .gcp_client import GCPTelemetryClient

__all__ = [
    'TelemetryClient',
    'NullTelemetryClient',
    'OpenTelemetryClient',
    # 'AWSTelemetryClient',
    # 'AzureTelemetryClient',
    # 'GCPTelemetryClient',
]

