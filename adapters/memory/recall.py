"""The recall behind ``FailurePatternRecallPort`` (SIP-0110 §0.8; #2096): the unit's pinned snapshot,
read from Cross-Cycle Memory's store, answered by the deterministic policy in
:func:`squadops.memory.lessons.recall`.

A read that raises is retried a bounded number of times, then answered as ``recall_failed``; a
stored pin this code cannot read is ``record_incompatible``. Neither is ever read as nothing
eligible, and neither stops the task: memory is beside execution (§0.3).
"""

from __future__ import annotations

import logging
from contextlib import AbstractAsyncContextManager
from typing import Any

from squadops.memory.cycle_bindings import as_bound_for, names_current
from squadops.memory.exposures import Exposure
from squadops.memory.lessons import RecallDisposition, Recalled, recall
from squadops.memory.project_instructions import PinUnknown, none_could_be_pinned
from squadops.memory.recall import RecallQuery, UnitKind
from squadops.memory.records import MemoryRecord, PinnedInstruction, RecordScope
from squadops.ports.memory.cross_cycle import CrossCycleMemoryStorePort, RecordIncompatible
from squadops.ports.memory.recall import FailurePatternRecallPort
from squadops.ports.memory.records import MemoryRecordsPort

logger = logging.getLogger(__name__)

#: Reads of a unit's snapshot before recall is answered as failed (§0.8: retries are bounded).
READ_ATTEMPTS = 2


class SnapshotRecall(FailurePatternRecallPort):
    def __init__(
        self,
        store: CrossCycleMemoryStorePort,
        *,
        records: MemoryRecordsPort | None = None,
        attempts: int = READ_ATTEMPTS,
    ) -> None:
        self._store = store
        #: The typed records (#2178): a deploy's recall is built with them
        #: (``create_failure_recall``); a unit test of the lessons alone may hold none.
        self._records = records
        self._attempts = attempts

    def dispatch_turn(self, unit_kind: UnitKind, unit_id: str) -> AbstractAsyncContextManager[None]:
        return self._store.dispatch_turn(unit_kind, unit_id)

    async def pinned_instructions(
        self, unit_kind: UnitKind, unit_id: str, project_id: str, *, cycle_id: str | None = None
    ) -> tuple[PinnedInstruction, ...]:
        try:
            snapshot = await self._snapshot_for_instructions(unit_kind, unit_id)
        except Exception as e:
            why = f"the unit's snapshot could not be read ({e})"
        else:
            if snapshot is not None and snapshot.instructions_unread is None:
                pinned = snapshot.instructions
                if unit_kind is UnitKind.CAMPAIGN and cycle_id and names_current(pinned):
                    # §5ad: the cycle's own bindings, read only where they can differ. One that
                    # can't be read raises, and the task holds rather than reading it unbound.
                    return as_bound_for(pinned, await self._store.get_cycle_binding(cycle_id))
                return pinned
            why = (
                snapshot.instructions_unread
                if snapshot is not None
                else "the unit has no pinned snapshot"
            )
        # What it pinned can't be known; a project with no project instruction pinned none
        # (#2179). Records that can't be read raise here, and the task holds.
        held = await self._records.list_project(project_id) if self._records is not None else []
        if none_could_be_pinned(held):
            return ()
        raise PinUnknown(f"the unit's project instructions can't be known: {why}")

    async def _snapshot_for_instructions(self, unit_kind: UnitKind, unit_id: str):
        """The snapshot, read as the lessons read it, with their attempts. A read that fails
        them all raises."""
        for attempt in range(1, self._attempts + 1):
            try:
                return await self._store.get_snapshot(unit_kind, unit_id)
            except Exception:
                if attempt == self._attempts:
                    raise
                logger.warning(
                    "memory_instructions_read_failed unit=%s:%s attempt=%d/%d",
                    unit_kind,
                    unit_id,
                    attempt,
                    self._attempts,
                    exc_info=True,
                )
        return None

    async def task_instructions(self, project_id: str, cycle_id: str) -> list[MemoryRecord]:
        if self._records is None:
            return []
        return [
            r
            for r in await self._records.list_project(project_id)
            if r.scope == RecordScope.TASK
            and r.current.target is not None
            and r.current.target.cycle_id == cycle_id
        ]

    async def recall(self, query: RecallQuery) -> Recalled:
        if query.unit_kind is None or not query.unit_id:
            return Recalled(None, RecallDisposition.FAILED)
        for attempt in range(1, self._attempts + 1):
            try:
                snapshot = await self._store.get_snapshot(query.unit_kind, query.unit_id)
            except RecordIncompatible:
                logger.warning(
                    "memory_recall_incompatible unit=%s:%s", query.unit_kind, query.unit_id
                )
                return Recalled(None, RecallDisposition.INCOMPATIBLE)
            except Exception:
                logger.warning(
                    "memory_recall_read_failed unit=%s:%s attempt=%d/%d",
                    query.unit_kind,
                    query.unit_id,
                    attempt,
                    self._attempts,
                    exc_info=True,
                )
                continue
            return recall(snapshot, query)
        return Recalled(None, RecallDisposition.FAILED)

    async def disclose(self, exposure: Exposure) -> None:
        try:
            await self._store.record_exposure(exposure)
        except Exception:
            logger.warning(
                "memory_exposure_not_recorded run=%s task=%s",
                exposure.run_id,
                exposure.task_id,
                exc_info=True,
            )


def create_failure_recall(kind: str, **kwargs: Any) -> FailurePatternRecallPort:
    """The recall for ``kind``. Required, never defaulted (#1568): ``snapshot`` answers from the
    store's pinned snapshots and the typed records' task instructions (a deploy: both ``store``
    and ``records`` are required); ``disabled`` answers every task as memory disabled (a
    composition with no store)."""
    if kind == "snapshot":
        return SnapshotRecall(kwargs["store"], records=kwargs["records"])
    if kind == "disabled":
        from adapters.noop.ports import NoOpFailurePatternRecall

        return NoOpFailurePatternRecall()
    raise ValueError(f"unknown failure recall {kind!r}")
