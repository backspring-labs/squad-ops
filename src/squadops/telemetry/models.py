"""Telemetry domain models.

Frozen dataclasses for structured events, spans, metric types,
and LLM observability correlation (SIP-0061).
Part of SIP-0.8.7 Infrastructure Ports Migration.
"""
from __future__ import annotations

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


# ---------------------------------------------------------------------------
# SIP-0061: LLM Observability domain models
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CorrelationContext:
    """Immutable correlation context threaded through Cycle -> Pulse -> Task -> LLM call.

    Fields are nullable to support context at different hierarchy levels:
    - Cycle level: only cycle_id is required
    - Pulse level: cycle_id + pulse_id
    - Task level: cycle_id + pulse_id + task_id + lineage fields
    """

    cycle_id: str
    pulse_id: str | None = None
    task_id: str | None = None
    correlation_id: str | None = None
    causation_id: str | None = None
    trace_id: str | None = None
    span_id: str | None = None
    agent_id: str | None = None
    agent_role: str | None = None
    message_id: str | None = None

    @classmethod
    def for_cycle(cls, cycle_id: str, agent_id: str | None = None) -> CorrelationContext:
        """Factory for cycle-level context. Only cycle_id is set."""
        return cls(cycle_id=cycle_id, agent_id=agent_id)

    @classmethod
    def for_pulse(
        cls, cycle_id: str, pulse_id: str, agent_id: str | None = None
    ) -> CorrelationContext:
        """Factory for pulse-level context. Sets cycle + pulse."""
        return cls(cycle_id=cycle_id, pulse_id=pulse_id, agent_id=agent_id)

    @classmethod
    def from_envelope(
        cls, envelope: Any, agent_id: str, agent_role: str | None = None
    ) -> CorrelationContext:
        """Factory that populates all lineage from a TaskEnvelope."""
        return cls(
            cycle_id=getattr(envelope, "cycle_id", "") or "",
            pulse_id=getattr(envelope, "pulse_id", None),
            task_id=getattr(envelope, "task_id", None),
            correlation_id=getattr(envelope, "correlation_id", None),
            causation_id=getattr(envelope, "causation_id", None),
            trace_id=getattr(envelope, "trace_id", None),
            span_id=getattr(envelope, "span_id", None),
            agent_id=agent_id,
            agent_role=agent_role,
            message_id=getattr(envelope, "message_id", None),
        )


@dataclass(frozen=True)
class PromptLayer:
    """Single prompt layer metadata."""

    layer_type: str
    layer_id: str
    layer_version: str | None = None
    layer_hash: str | None = None


@dataclass(frozen=True)
class PromptLayerMetadata:
    """Prompt layer set metadata attached to every Generation."""

    prompt_layer_set_id: str
    layers: tuple[PromptLayer, ...]


@dataclass(frozen=True)
class GenerationRecord:
    """Record of a single LLM generation (model call).

    generation_id is REQUIRED — created by the caller via build_generation_record().
    Adapters MUST NOT generate or backfill generation_id.
    """

    generation_id: str  # UUID4, REQUIRED, caller-supplied
    model: str
    prompt_text: str
    response_text: str
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    total_tokens: int | None = None
    latency_ms: float | None = None
