"""The recall behind ``FailurePatternRecallPort`` (SIP-0110 §0.8; #2096): the unit's pinned snapshot,
read from Cross-Cycle Memory's store, answered by the deterministic policy in
:func:`squadops.memory.lessons.recall`.

A read that raises is retried a bounded number of times, then answered as ``recall_failed``; a
stored pin this code cannot read is ``record_incompatible``. Neither is ever read as nothing
eligible, and neither stops the task: memory is beside execution (§0.3).
"""

from __future__ import annotations

import logging
from typing import Any

from squadops.memory.exposures import Exposure
from squadops.memory.lessons import RecallDisposition, Recalled, recall
from squadops.memory.recall import RecallQuery
from squadops.ports.memory.cross_cycle import CrossCycleMemoryStorePort, RecordIncompatible
from squadops.ports.memory.recall import FailurePatternRecallPort

logger = logging.getLogger(__name__)

#: Reads of a unit's snapshot before recall is answered as failed (§0.8: retries are bounded).
READ_ATTEMPTS = 2


class SnapshotRecall(FailurePatternRecallPort):
    def __init__(self, store: CrossCycleMemoryStorePort, *, attempts: int = READ_ATTEMPTS) -> None:
        self._store = store
        self._attempts = attempts

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
    store's pinned snapshots (a deploy); ``disabled`` answers every task as memory disabled (a
    composition with no store)."""
    if kind == "snapshot":
        return SnapshotRecall(kwargs["store"])
    if kind == "disabled":
        from adapters.noop.ports import NoOpFailurePatternRecall

        return NoOpFailurePatternRecall()
    raise ValueError(f"unknown failure recall {kind!r}")
