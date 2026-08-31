"""Telemetry domain models.

Frozen dataclasses for structured events, spans, metric types,
and LLM observability correlation (SIP-0061).
Part of SIP-0.8.7 Infrastructure Ports Migration.
"""

from __future__ import annotations

import uuid
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
    - Prefect scope (SIP-0087): flow_run_id at flow boundary, task_run_id at
      dispatch — so log records emitted during a task land in the right UI pane.
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
    flow_run_id: str | None = None
    task_run_id: str | None = None

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


MAX_OBSERVABILITY_TEXT_LENGTH = 10000
"""Safety cap for prompt/response text stored in LLM observability records."""


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
    tokens_per_second: float | None = None
    # SIP-0084: prompt-to-generation linkage for Langfuse
    prompt_name: str | None = None
    prompt_version: int | None = None
    # #927: the reasoning level this generation was sent with (a ReasoningLevel),
    # None when none was sent — so "how much did this call think" is readable
    # per generation rather than inferred from a token count.
    reasoning: str | None = None

    # #1172: for a capability that retries against a validator, which attempt this
    # was and what the validator said. A roll-up hides the repair loop, and the
    # repair loop is the thing worth seeing — merge_plan can burn eight attempts
    # while the record shows one task.
    attempt: int | None = None
    outcome: str | None = None
    # #410: the thinking text itself. Ollama returns it as ``message.thinking``,
    # Atlas and vLLM as ``message.reasoning_content``; every one of them was read
    # past and dropped, so the ~60% of generation time that bought it appeared in
    # no telemetry at all and the spend was undiagnosable without cross-referencing
    # eval_count against stored output length. Capped like the other text fields.
    reasoning_text: str | None = None


def _capped(text: str | None) -> str | None:
    """Cap observability text, preserving None (absent) as distinct from "" (empty)."""
    return None if text is None else text[:MAX_OBSERVABILITY_TEXT_LENGTH]


def build_generation_record(
    *,
    model: str,
    prompt_text: str,
    response_text: str,
    latency_ms: float | None = None,
    usage: Any | None = None,
    prompt_name: str | None = None,
    prompt_version: int | None = None,
    reasoning: str | None = None,
    attempt: int | None = None,
    outcome: str | None = None,
    reasoning_text: str | None = None,
) -> GenerationRecord:
    """Build a :class:`GenerationRecord` from a completed generation.

    The construction path :class:`GenerationRecord` has named in its own docstring
    since SIP-0061 and which never existed: five call sites hand-rolled the record
    instead, with field sets that drifted. The planning handlers omitted all four
    token fields, so every framing generation reached LangFuse costed at zero and
    with no decode rate — on both arms — which is #1171. A record type that says
    "created by the caller via build_generation_record()" should have one.

    ``usage`` is any object carrying the token attributes an adapter returns
    (``LLMResponse``, ``ChatMessage``): the four fields are read off it when it is
    present and left ``None`` when it is not, so a caller with no usage to report
    is expressing that rather than forgetting it. Text is capped here, at the one
    place that knows the cap.
    """
    return GenerationRecord(
        generation_id=str(uuid.uuid4()),
        model=model,
        prompt_text=prompt_text[:MAX_OBSERVABILITY_TEXT_LENGTH],
        response_text=response_text[:MAX_OBSERVABILITY_TEXT_LENGTH],
        # Falls back to ``usage`` like the token fields, so a caller already passing the
        # response object gets the thinking text without a second argument. An explicit
        # value still wins, for a caller that has it from somewhere else.
        reasoning_text=_capped(
            reasoning_text if reasoning_text is not None else getattr(usage, "reasoning_text", None)
        ),
        latency_ms=latency_ms,
        prompt_tokens=getattr(usage, "prompt_tokens", None),
        completion_tokens=getattr(usage, "completion_tokens", None),
        total_tokens=getattr(usage, "total_tokens", None),
        tokens_per_second=getattr(usage, "tokens_per_second", None),
        prompt_name=prompt_name,
        prompt_version=prompt_version,
        reasoning=reasoning,
        attempt=attempt,
        outcome=outcome,
    )
