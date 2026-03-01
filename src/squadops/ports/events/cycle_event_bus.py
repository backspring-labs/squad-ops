"""CycleEventBusPort — abstract interface for cycle lifecycle event publication.

Follows the CycleRegistryPort / LLMObservabilityPort ABC pattern.

Port-level contract:
  - ``emit()`` is best-effort, non-blocking publication. It is not part of the
    caller's transactional success criteria. Callers must not treat emission
    failure as an application error.
  - Callers provide semantic inputs (event_type, entity/context/payload).
    The adapter enriches transport/publication metadata (event_id, occurred_at,
    sequence, semantic_key, source_service, source_version). Application code
    must not construct envelope fields.
  - ``subscribe()`` is on the port because the in-process adapter uses it for
    local bridge registration. Subscriber registration semantics are
    adapter-defined — future external adapters may implement subscription
    differently. ``subscribe()`` is not a universal consumption contract.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from squadops.events.models import CycleEvent
    from squadops.events.subscriber import EventSubscriber


class CycleEventBusPort(ABC):
    """Port for cycle lifecycle event publication and subscriber registration."""

    @abstractmethod
    def emit(
        self,
        event_type: str,
        *,
        entity_type: str,
        entity_id: str,
        context: dict | None = None,
        payload: dict | None = None,
    ) -> CycleEvent | None:
        """Publish a lifecycle event.

        Returns a ``CycleEvent`` if the adapter constructs one, or ``None``
        for no-op adapters. Callers MUST NOT depend on the return value.
        """

    @abstractmethod
    def subscribe(self, subscriber: EventSubscriber) -> None:
        """Register a subscriber to receive events.

        Subscriber semantics are adapter-defined. The in-process adapter
        delivers events synchronously in registration order. Future adapters
        may implement subscription differently.
        """
