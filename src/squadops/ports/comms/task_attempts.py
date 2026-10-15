"""What a dispatched task's deliveries leave behind, across agent restarts (#1977).

SIP-Agent-Comms-Delivery-Guarantees §5.1, §5.3 and §5.3a, as amended 2026-10-14. The broker keeps
no count of a classic queue's redeliveries: a raising handler's requeue and a dying agent's
requeue both carry no ``x-death`` (measured, #1977). So the agent keeps the count itself:
- an **attempt**, counted *before* the handler runs, so a delivery that kills the agent is still
  counted (the #1626 crash loop);
- a **completion mark**, written only *after* the reply was published, so a redelivery of work
  that finished but was never acked is answered as a duplicate, never run again.

Only completion is recorded, never "seen": a crash mid-task leaves no mark, so the task runs
again, within its attempts.

**Both are kept per send, not per task (§5.3c, #2333).** The runtime sends a task again under its
own id for a fresh execution (a retry, or a re-run after a failed patch retest), and that send is
new work. The key is ``squadops.comms.task_delivery.delivery_key``: the task id and the send's own
id, which a broker redelivery shares and a new send doesn't.
"""

from __future__ import annotations

from abc import ABC, abstractmethod


class TaskAttemptsPort(ABC):
    """One send's delivery record, keyed by its ``delivery_key``."""

    @abstractmethod
    async def completed(self, key: str) -> bool:
        """Whether a delivery of this send already ran to its published reply."""

    @abstractmethod
    async def begin_attempt(self, key: str) -> int:
        """Count this delivery's attempt, before the handler runs. Returns the count, this one
        included: 1 for a send's first delivery."""

    @abstractmethod
    async def mark_completed(self, key: str) -> None:
        """Record that this send's reply was published."""
