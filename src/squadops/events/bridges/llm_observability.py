"""LLMObservabilityBridge — translates CycleEvent to LLMObservabilityPort.record_event().

Converts canonical lifecycle events into CorrelationContext + StructuredEvent
pairs and forwards them to the LLM observability port. This bridges the
canonical event bus with the existing LangFuse telemetry pipeline.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from squadops.telemetry.models import CorrelationContext, StructuredEvent

if TYPE_CHECKING:
    from squadops.events.models import CycleEvent
    from squadops.ports.telemetry.llm_observability import LLMObservabilityPort

logger = logging.getLogger(__name__)


class LLMObservabilityBridge:
    """Subscriber that forwards CycleEvents to LLMObservabilityPort.record_event().

    Translates each CycleEvent into:
      - A ``CorrelationContext`` from the event's context dict (cycle_id, trace_id)
      - A ``StructuredEvent`` with event_type as name, entity info as message,
        and payload as attributes
    """

    def __init__(self, llm_observability: LLMObservabilityPort) -> None:
        self._llm_observability = llm_observability

    def on_event(self, event: CycleEvent) -> None:
        ctx = CorrelationContext(
            cycle_id=event.context.get("cycle_id", ""),
            trace_id=event.context.get("trace_id"),
        )

        attrs: list[tuple[str, Any]] = [
            ("entity_type", event.entity_type),
            ("entity_id", event.entity_id),
            ("event_id", event.event_id),
            ("sequence", event.sequence),
        ]
        for key, value in event.payload.items():
            attrs.append((key, value))

        structured_event = StructuredEvent(
            name=event.event_type,
            message=f"{event.entity_type} {event.entity_id} {event.event_type}",
            attributes=tuple(attrs),
        )

        self._llm_observability.record_event(ctx, structured_event)
