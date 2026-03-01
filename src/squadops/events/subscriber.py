"""EventSubscriber protocol for cycle lifecycle event consumption.

Structural typing (Protocol) — no inheritance required. Placed in the
domain layer alongside the event models, not in ports/.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from squadops.events.models import CycleEvent


@runtime_checkable
class EventSubscriber(Protocol):
    """Protocol for receiving cycle lifecycle events.

    ``on_event()`` is synchronous in v0. Subscribers must be lightweight
    and non-blocking in practice — long-running I/O or expensive
    reconciliation inside a subscriber will stall the calling
    request/executor path.
    """

    def on_event(self, event: CycleEvent) -> None: ...
