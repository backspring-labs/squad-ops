"""The no-op LLM observability port — a domain null object (SIP-0061).

Implements ``LLMObservabilityPort`` with silent no-ops. It lives in the domain, not under
``adapters/``, because it binds to no infrastructure: it is the value the composition root
injects when observability is off, and the value ``AgentOrchestrator`` falls back to
("always-inject NoOp") — which used to be a domain → adapters import (#154). Separate from
``adapters/telemetry/null.py``, which implements ``MetricsPort`` + ``EventPort``.
"""

from squadops.ports.telemetry.llm_observability import LLMObservabilityPort
from squadops.telemetry.models import (
    CorrelationContext,
    GenerationRecord,
    PromptLayerMetadata,
    StructuredEvent,
)


class NoOpLLMObservabilityAdapter(LLMObservabilityPort):
    """No-op LLM observability adapter. All methods are silent no-ops.

    Accepts optional status/reason overrides so the factory can signal
    degraded health when the SDK is missing but config.enabled is True.
    """

    def __init__(
        self,
        *,
        health_status: str = "ok",
        health_reason: str | None = None,
    ) -> None:
        self._health_status = health_status
        self._health_reason = health_reason

    def start_cycle_trace(self, ctx: CorrelationContext) -> None:
        pass

    def end_cycle_trace(self, ctx: CorrelationContext) -> None:
        pass

    def start_pulse_span(self, ctx: CorrelationContext) -> None:
        pass

    def end_pulse_span(self, ctx: CorrelationContext) -> None:
        pass

    def start_task_span(self, ctx: CorrelationContext) -> None:
        pass

    def end_task_span(self, ctx: CorrelationContext) -> None:
        pass

    def record_generation(
        self,
        ctx: CorrelationContext,
        record: GenerationRecord,
        prompt_layers: PromptLayerMetadata,
    ) -> None:
        pass

    def record_event(self, ctx: CorrelationContext, event: StructuredEvent) -> None:
        pass

    def flush(self) -> None:
        pass

    def close(self) -> None:
        pass

    async def health(self) -> dict:
        details: dict = {}
        if self._health_reason:
            details["reason"] = self._health_reason
        return {"status": self._health_status, "backend": "noop", "details": details}
