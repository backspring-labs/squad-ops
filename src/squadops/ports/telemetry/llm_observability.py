"""LLM Observability port interface.

Defines the abstract contract for LLM-specific observability (SIP-0061).
All methods MUST be non-blocking — implementations buffer/enqueue internally.
"""
from abc import ABC, abstractmethod

from squadops.telemetry.models import (
    CorrelationContext,
    GenerationRecord,
    PromptLayerMetadata,
    StructuredEvent,
)


class LLMObservabilityPort(ABC):
    """Port for LLM-specific observability (generation capture, prompt-layer correlation).

    All methods MUST be non-blocking. Implementations MUST buffer/enqueue
    internally and never raise exceptions to the caller.
    """

    @abstractmethod
    def start_cycle_trace(self, ctx: CorrelationContext) -> None:
        """Begin a trace for an execution cycle.

        Precondition: ctx.cycle_id MUST NOT be None.
        """

    @abstractmethod
    def end_cycle_trace(self, ctx: CorrelationContext) -> None:
        """End the active cycle trace. Caller SHOULD call flush() after this."""

    @abstractmethod
    def start_pulse_span(self, ctx: CorrelationContext) -> None:
        """Begin a span for a pulse within the active cycle trace.

        Precondition: ctx.pulse_id MUST NOT be None.
        """

    @abstractmethod
    def end_pulse_span(self, ctx: CorrelationContext) -> None:
        """End the active pulse span."""

    @abstractmethod
    def start_task_span(self, ctx: CorrelationContext) -> None:
        """Begin a span for a task within the active pulse span.

        Precondition: ctx.task_id MUST NOT be None.
        """

    @abstractmethod
    def end_task_span(self, ctx: CorrelationContext) -> None:
        """End the active task span."""

    @abstractmethod
    def record_generation(
        self,
        ctx: CorrelationContext,
        record: GenerationRecord,
        prompt_layers: PromptLayerMetadata,
    ) -> None:
        """Record an LLM generation inside the active task span.

        Precondition: ctx.task_id MUST NOT be None.
        """

    @abstractmethod
    def record_event(self, ctx: CorrelationContext, event: StructuredEvent) -> None:
        """Record a lifecycle event (task.assigned, message.sent, etc.).

        Uses the existing StructuredEvent model — no dict overload.
        CorrelationContext provides the hierarchy correlation that
        StructuredEvent.span_id alone cannot express.
        """

    @abstractmethod
    def flush(self) -> None:
        """Flush buffered telemetry. Non-blocking best-effort."""

    @abstractmethod
    def close(self) -> None:
        """Attempt a bounded flush and release resources.

        MUST NOT block indefinitely. Implementations SHOULD enforce
        a max time budget for the final flush attempt.
        """

    @abstractmethod
    async def health(self) -> dict:
        """Health check for the observability backend.

        Returns:
            {"status": "ok" | "degraded" | "down",
             "backend": str,
             "details": { ... adapter-specific diagnostics ... }}
        """
