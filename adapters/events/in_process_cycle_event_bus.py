"""In-process cycle event bus adapter — v0 local publication and bridge fanout.

This is the v0 adapter for local publication. It is not the long-term durable
event continuity layer. A future persistent adapter (event store, message
broker) will replace it for durable publication guarantees.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from squadops.events.models import CycleEvent
from squadops.ports.events.cycle_event_bus import CycleEventBusPort

if TYPE_CHECKING:
    from squadops.events.subscriber import EventSubscriber

logger = logging.getLogger(__name__)


def _generate_event_id() -> str:
    """Generate a unique event ID with ``evt_`` prefix.

    Uses ULID if ``ulid-py`` is installed, falls back to UUID4.
    """
    try:
        import ulid  # type: ignore[import-untyped]

        return f"evt_{ulid.new().str}"
    except ImportError:
        return f"evt_{uuid.uuid4().hex}"


class InProcessCycleEventBus(CycleEventBusPort):
    """In-process synchronous event bus implementing CycleEventBusPort.

    Subscribers are called in registration order. Subscriber exceptions are
    logged and swallowed — they never propagate to the emitter.

    Registration-order delivery is a guarantee of this adapter, not a
    port-level contract.
    """

    def __init__(self, source_service: str, source_version: str) -> None:
        self._source_service = source_service
        self._source_version = source_version
        self._subscribers: list[EventSubscriber] = []
        self._sequence: dict[tuple[str, str], int] = {}

    def subscribe(self, subscriber: EventSubscriber) -> None:
        self._subscribers.append(subscriber)

    def emit(
        self,
        event_type: str,
        *,
        entity_type: str,
        entity_id: str,
        context: dict | None = None,
        payload: dict | None = None,
    ) -> CycleEvent:
        ctx = context or {}
        cycle_id = ctx.get("cycle_id", "")
        run_id = ctx.get("run_id", "")

        seq_key = (cycle_id, run_id)
        seq = self._sequence.get(seq_key, 0) + 1
        self._sequence[seq_key] = seq

        transition = event_type.split(".")[-1] if "." in event_type else event_type
        semantic_key = f"{cycle_id}:{entity_type}:{entity_id}:{transition}:{seq}"

        event = CycleEvent(
            event_id=_generate_event_id(),
            occurred_at=datetime.now(tz=timezone.utc),
            source_service=self._source_service,
            source_version=self._source_version,
            event_type=event_type,
            entity_type=entity_type,
            entity_id=entity_id,
            context=ctx,
            payload=payload or {},
            sequence=seq,
            semantic_key=semantic_key,
        )

        for subscriber in self._subscribers:
            try:
                subscriber.on_event(event)
            except Exception:
                logger.exception(
                    "Event subscriber %s failed on %s (swallowed)",
                    type(subscriber).__name__,
                    event_type,
                )

        return event
