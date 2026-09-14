"""The run summary — the loop facts no store held, one durable row per run (SIP-0108 §4.1).

Written at run finalization beside ``run_verification_summaries``. The scorecard's projection
reads it and never reads logs: a fact that lived only in container logs was unreadable to a
projection that may do no I/O, and unrecoverable once a rebuild wiped the logs.

This row carries **usage** (:class:`~squadops.cycles.llm_usage.RunUsage`, accounted at
``_llm_call``), every **refunded correction round** with its reason, and the **correction
movement sequence** — each failed task's round-over-round class, including the round a chain
terminated on. The structured terminal decision joins it as a field of the same row, which is
why it has a ``summary_version``. A historical run has no row: its indicators read unaskable,
never backfilled from logs.

Pure data; the registry adapters persist it.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from squadops.cycles.llm_usage import RunUsage

#: The row's contract version. A reader names the version it read.
RUN_LOOP_SUMMARY_VERSION = 1


#: Why a round was refunded. One reason exists: the repair emitted no content (#1053).
REFUND_EMPTY_REPAIR_EMISSION = "empty_repair_emission"


@dataclass(frozen=True)
class RefundedRound:
    """One correction round handed back rather than spent (#1053).

    ``signatures`` are the #998 shapes of the empty repair emissions — ``cap_exhausted``,
    ``empty`` or ``unextractable`` — whose remedies differ.
    """

    task_id: str
    round_index: int
    reason: str
    signatures: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "round_index": self.round_index,
            "reason": self.reason,
            "signatures": list(self.signatures),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> RefundedRound:
        return cls(
            task_id=str(data["task_id"]),
            round_index=int(data["round_index"]),
            reason=str(data["reason"]),
            signatures=tuple(str(s) for s in data.get("signatures") or ()),
        )


@dataclass(frozen=True)
class MovementRecord:
    """One failed task's movement class for one correction round (``classify_movement``)."""

    task_id: str
    round_index: int
    movement: str

    def to_dict(self) -> dict[str, Any]:
        return {"task_id": self.task_id, "round_index": self.round_index, "movement": self.movement}

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> MovementRecord:
        return cls(
            task_id=str(data["task_id"]),
            round_index=int(data["round_index"]),
            movement=str(data["movement"]),
        )


@dataclass(frozen=True)
class RunLoopSummary:
    """One run's loop facts, as persisted at finalization."""

    run_id: str
    usage: RunUsage
    refunded_rounds: tuple[RefundedRound, ...] = ()
    movements: tuple[MovementRecord, ...] = ()
    summary_version: int = RUN_LOOP_SUMMARY_VERSION

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "summary_version": self.summary_version,
            "usage": self.usage.to_dict(),
            "refunded_rounds": [r.to_dict() for r in self.refunded_rounds],
            "movements": [m.to_dict() for m in self.movements],
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> RunLoopSummary:
        return cls(
            run_id=str(data["run_id"]),
            usage=RunUsage.from_dict(data.get("usage") or {}),
            refunded_rounds=tuple(
                RefundedRound.from_dict(r) for r in data.get("refunded_rounds") or ()
            ),
            movements=tuple(MovementRecord.from_dict(m) for m in data.get("movements") or ()),
            summary_version=int(data.get("summary_version") or RUN_LOOP_SUMMARY_VERSION),
        )
