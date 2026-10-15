"""What a dispatched task's deliveries leave behind, across agent restarts (#1977).

SIP-Agent-Comms-Delivery-Guarantees §5.1, §5.3 and §5.3a, as amended 2026-10-15. The broker keeps
no count of a classic queue's redeliveries: a raising handler's requeue and a dying agent's
requeue both carry no ``x-death`` (measured, #1977). So the agent keeps the count itself:
- an **attempt**, counted *before* the handler runs, so a delivery that kills the agent is still
  counted (the #1626 crash loop);
- a **completion mark**, written only *after* the reply was published, so a redelivery of work
  that finished but was never acked is answered as a duplicate, never run again.

Only completion is recorded, never "seen": a crash mid-task leaves no mark, so the task runs
again, within its attempts.
"""

from __future__ import annotations

from abc import ABC, abstractmethod


class TaskAttemptsPort(ABC):
    """One task's delivery record, keyed by its task id."""

    @abstractmethod
    async def completed(self, task_id: str) -> bool:
        """Whether a delivery of ``task_id`` already ran to its published reply."""

    @abstractmethod
    async def begin_attempt(self, task_id: str) -> int:
        """Count this delivery's attempt, before the handler runs. Returns the count, this one
        included: 1 for a task's first delivery."""

    @abstractmethod
    async def mark_completed(self, task_id: str) -> None:
        """Record that ``task_id``'s reply was published."""
