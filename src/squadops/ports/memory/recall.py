"""The recall port (SIP-0110 §0.8; #1964 shipped it inert, #2096 the policy behind it).

Recall is a port operation, not an executor feature (§6 item 3): the authoring seams are its
consumers, not its owners. The policy behind it owns eligibility, snapshot selection, ordering and
disclosure, so duty and ambient callers reuse it rather than reimplement its trust rules.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from contextlib import AbstractAsyncContextManager

from squadops.memory.exposures import Exposure
from squadops.memory.lessons import Recalled
from squadops.memory.recall import RecallQuery, UnitKind
from squadops.memory.records import MemoryRecord, PinnedInstruction, Reference
from squadops.memory.references import BindingContext


class FailurePatternRecallPort(ABC):
    @abstractmethod
    async def recall(self, query: RecallQuery) -> Recalled:
        """The lessons ``query``'s unit snapshot supplies its task, or the disposition saying why
        none. Never raises: a recall that cannot be answered is ``recall_failed``, an answer."""

    @abstractmethod
    async def disclose(self, exposure: Exposure) -> None:
        """Record what a consuming task was supplied, or why nothing (§0.8 step 7). Never raises:
        an exposure that cannot be stored is logged, and the task runs."""

    @abstractmethod
    def dispatch_turn(self, unit_kind: UnitKind, unit_id: str) -> AbstractAsyncContextManager[None]:
        """The unit's dispatch turn (#2545), held by a dispatch from reading what it is handed to
        disclosing it, so a change to the unit's binding never lands between the two. It is the
        store's (``CrossCycleMemoryStorePort.dispatch_turn``), which a change holds too."""

    @abstractmethod
    async def task_instructions(self, project_id: str, cycle_id: str) -> list[MemoryRecord]:
        """The task instructions recorded for ``cycle_id`` (SIP-0110 Appendix A §3.7; #2178),
        every status: the composer decides which apply to a dispatch. Raises when the records
        can't be read, since a binding section that can't be read holds its task and never
        reads as none (§3.6)."""

    @abstractmethod
    async def pinned_instructions(
        self, unit_kind: UnitKind, unit_id: str, project_id: str, *, cycle_id: str | None = None
    ) -> tuple[PinnedInstruction, ...]:
        """The project instructions the unit's snapshot pinned at admission (Appendix A §3.7;
        #2179): none when it pinned none. When what it pinned can't be known (its snapshot is
        unreadable or absent, or its pin couldn't read the records), none only if
        ``project_id`` holds no project instruction (``none_could_be_pinned``); otherwise raises
        ``PinUnknown``, since they bind and an unknown pin is never read as an empty one.

        For a campaign's cycle (``cycle_id``), each pinned instruction naming an ``@current``
        reference is read as that cycle bound it at its launch (§5ad). A binding that can't be read
        raises, so the task holds."""

    @abstractmethod
    async def read_reference(self, reference: Reference, ctx: BindingContext) -> str:
        """A bound reference's content at its bound revision, through its family's resolver
        (Appendix A §3.6; #2179): what a dispatch is handed beside the instruction naming it.
        Raises ``ReferenceUnresolved`` when it can't be read there, its content no longer matches
        the digest bound, or no resolver reads its family; any other error when the resolver
        failed, which says nothing of the reference."""
