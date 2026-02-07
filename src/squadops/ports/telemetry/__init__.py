"""Telemetry port interfaces.

Provides abstract base classes for telemetry adapters:
- MetricsPort: Counter, gauge, histogram metrics
- EventPort: Structured events and distributed tracing
- LLMObservabilityPort: LLM-specific observability (SIP-0061)

Part of SIP-0.8.7 Infrastructure Ports Migration.
"""
from squadops.ports.telemetry.events import EventPort
from squadops.ports.telemetry.llm_observability import LLMObservabilityPort
from squadops.ports.telemetry.metrics import MetricsPort

__all__ = [
    "EventPort",
    "LLMObservabilityPort",
    "MetricsPort",
]
