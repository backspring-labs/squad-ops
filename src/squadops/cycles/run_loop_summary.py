"""The run summary — the loop facts no store held, one durable row per run (SIP-0108 §4.1).

Written at run finalization beside ``run_verification_summaries``. The scorecard's projection
reads it and never reads logs: a fact that lived only in container logs was unreadable to a
projection that may do no I/O, and unrecoverable once a rebuild wiped the logs.

This row carries **usage** today (:class:`~squadops.cycles.llm_usage.RunUsage`, accounted at
``_llm_call``). The review's other loop facts — refunded rounds, the correction movement
sequence and the structured terminal decision — join it as fields of the same row, which is
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


@dataclass(frozen=True)
class RunLoopSummary:
    """One run's loop facts, as persisted at finalization."""

    run_id: str
    usage: RunUsage
    summary_version: int = RUN_LOOP_SUMMARY_VERSION

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "summary_version": self.summary_version,
            "usage": self.usage.to_dict(),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> RunLoopSummary:
        return cls(
            run_id=str(data["run_id"]),
            usage=RunUsage.from_dict(data.get("usage") or {}),
            summary_version=int(data.get("summary_version") or RUN_LOOP_SUMMARY_VERSION),
        )
