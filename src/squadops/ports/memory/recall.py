"""The recall port (SIP-0110 §0.8; #1964 shipped it inert, #2096 the policy behind it).

Recall is a port operation, not an executor feature (§6 item 3): the authoring seams are its
consumers, not its owners. The policy behind it owns eligibility, snapshot selection, ordering and
disclosure, so duty and ambient callers reuse it rather than reimplement its trust rules.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from squadops.memory.exposures import Exposure
from squadops.memory.lessons import Recalled
from squadops.memory.recall import RecallQuery


class FailurePatternRecallPort(ABC):
    @abstractmethod
    async def recall(self, query: RecallQuery) -> Recalled:
        """The lessons ``query``'s unit snapshot supplies its task, or the disposition saying why
        none. Never raises: a recall that cannot be answered is ``recall_failed``, an answer."""

    @abstractmethod
    async def disclose(self, exposure: Exposure) -> None:
        """Record what a consuming task was supplied, or why nothing (§0.8 step 7). Never raises:
        an exposure that cannot be stored is logged, and the task runs."""
