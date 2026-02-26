"""Telemetry adapters.

Provides implementations of telemetry ports:
- OTelAdapter: Production-ready OpenTelemetry adapter
- ConsoleAdapter: Dev-only console logging adapter
- NullAdapter: No-op adapter for testing
- NoOpLLMObservabilityAdapter: No-op LLM observability adapter (SIP-0061)

Part of SIP-0.8.7 Infrastructure Ports Migration.
"""

from adapters.telemetry.console import ConsoleAdapter
from adapters.telemetry.factory import (
    create_event_provider,
    create_llm_observability_provider,
    create_metrics_provider,
    create_telemetry_provider,
)
from adapters.telemetry.noop_llm_observability import NoOpLLMObservabilityAdapter
from adapters.telemetry.null import NullAdapter
from adapters.telemetry.otel import OTelAdapter

__all__ = [
    "ConsoleAdapter",
    "NoOpLLMObservabilityAdapter",
    "NullAdapter",
    "OTelAdapter",
    "create_event_provider",
    "create_llm_observability_provider",
    "create_metrics_provider",
    "create_telemetry_provider",
]
