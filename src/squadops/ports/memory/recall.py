"""The failure-pattern recall port (SIP-Cross-Cycle-Memory §5, §6 item 3; #1964).

Recall is a port operation, not an executor feature (§6 item 3): the plan-authoring seam is its
consumer, not its owner. 2.1's composition roots inject an inert recall that answers empty
(``adapters.noop.ports.NoOpFailurePatternRecall``), not ``NoOpMemoryPort``, which raises.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from squadops.memory.recall import RecalledPattern, RecallQuery


class FailurePatternRecallPort(ABC):
    @abstractmethod
    async def recall(self, query: RecallQuery) -> tuple[RecalledPattern, ...]:
        """The patterns this project's ``query.task_type`` should be warned about, most relevant
        first. Empty when there are none, never ``None``: an answer, not an absence."""
