"""No-op cycle event bus adapter — valid degraded production adapter.

Running with NoOp means no canonical event publication guarantees are
present. This is an acceptable operational mode, not a configuration
mistake, but operators should be aware of it.

Follows the NoOpLLMObservabilityAdapter pattern.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from squadops.ports.events.cycle_event_bus import CycleEventBusPort

if TYPE_CHECKING:
    from squadops.events.models import CycleEvent
    from squadops.events.subscriber import EventSubscriber


class NoOpCycleEventBus(CycleEventBusPort):
    """No-op event bus — all methods are silent no-ops.

    ``emit()`` returns ``None``. Callers MUST NOT depend on the return value.
    """

    def subscribe(self, subscriber: EventSubscriber) -> None:
        pass

    def emit(
        self,
        event_type: str,
        *,
        entity_type: str,
        entity_id: str,
        context: dict | None = None,
        payload: dict | None = None,
    ) -> CycleEvent | None:
        return None
