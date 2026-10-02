"""The convergence replay's corpus: the stored failing rounds a replay can start from (#1764).

A **round** is one correction round whose decision was ``patch``: the task that failed, the checks
that failed it, the diagnosis the repair was handed (``failure_analysis.md``,
``correction_decision.md``, both typed JSON), the failed task's own emitted files, and the last
checkpoint written before the round began.

**Where the rounds come from.** SIP-0108's run summary records every round failure
(``run_loop_summaries.summary.round_failures``: the failed task, its round index, the failed
checks, the locus). The vault holds each round's diagnosis under the round's own task ids. The two
are matched by **time order within the run**: the k-th recorded failure is the k-th correction
round. Before #1697 a refunded round re-took its index, so an index alone cannot join them; a run
whose failure count differs from its correction-round count is **refused, not guessed**, and the
refusal is counted.

Pure where it can be: the matching and the selection read plain values, and the I/O (the registry
rows, the vault's metadata files) is gathered by the caller.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any

#: A correction round's diagnosis task ids: ``corr-<run8>-<NN>[-s<NN>]-<task_type>``.
_CORR = re.compile(
    r"^corr-(?P<run>run_[0-9a-f]{8})-(?P<attempt>\d{2})(?:-s(?P<seq>\d{2}))?-(?P<task>.+)$"
)
ANALYSIS = "data.analyze_failure"
DECISION = "governance.correction_decision"


@dataclass(frozen=True)
class ArtifactMeta:
    """One stored artifact, as its ``metadata.json`` describes it."""

    artifact_id: str
    filename: str
    task_id: str
    producing_task_type: str
    created_at: datetime
    path: str

    @classmethod
    def from_metadata(cls, meta: Mapping[str, Any], path: str) -> ArtifactMeta:
        inner = meta.get("metadata") or {}
        return cls(
            artifact_id=meta["artifact_id"],
            filename=meta["filename"],
            task_id=inner.get("task_id") or "",
            producing_task_type=inner.get("producing_task_type") or "",
            created_at=datetime.fromisoformat(meta["created_at"]),
            path=path,
        )


@dataclass(frozen=True)
class RoundFailure:
    """One ``round_failures`` entry of a run summary."""

    task_id: str
    round_index: int
    failed_checks: tuple[str, ...]
    locus: str | None
    category: str | None


@dataclass(frozen=True)
class CorrectionRound:
    """One correction round's diagnosis, as the vault holds it."""

    attempt: int
    seq: int | None
    analysis: ArtifactMeta
    decision: ArtifactMeta


@dataclass(frozen=True)
class Round:
    """A replayable round: a failure joined to the diagnosis it was handed."""

    project_id: str
    cycle_id: str
    run_id: str
    stack: str | None
    failure: RoundFailure
    correction_path: str
    analysis_id: str
    decision_id: str
    failed_artifact_ids: tuple[str, ...]
    #: The last checkpoint written before the round's analysis, or None when pruned (max_keep=5).
    checkpoint_index: int | None
    #: What the round is part of, read from the verification-set records: ``(set, role)``.
    provenance: tuple[str, str] | None = None
    notes: tuple[str, ...] = field(default_factory=tuple)

    def as_row(self) -> dict[str, Any]:
        row = asdict(self)
        row["failure"]["failed_checks"] = list(self.failure.failed_checks)
        return row


def correction_rounds(artifacts: Iterable[ArtifactMeta]) -> list[CorrectionRound]:
    """Every correction round in a run's artifacts, in the order its analysis was written.

    A round is its analysis and its decision under one task-id prefix. A prefix with only one of
    the two (a round the budget or a crash cut short) is not a round the replay can start from.
    """
    halves: dict[tuple[str, str | None], dict[str, ArtifactMeta]] = {}
    for art in artifacts:
        m = _CORR.match(art.task_id)
        if m is None or m["task"] not in (ANALYSIS, DECISION):
            continue
        key = (m["attempt"], m["seq"])
        halves.setdefault(key, {})[m["task"]] = art
    rounds = [
        CorrectionRound(
            attempt=int(attempt),
            seq=int(seq) if seq is not None else None,
            analysis=pair[ANALYSIS],
            decision=pair[DECISION],
        )
        for (attempt, seq), pair in halves.items()
        if ANALYSIS in pair and DECISION in pair
    ]
    return sorted(rounds, key=lambda r: r.analysis.created_at)


def join_failures_to_rounds(
    failures: Sequence[RoundFailure], rounds: Sequence[CorrectionRound]
) -> list[tuple[RoundFailure, CorrectionRound]] | str:
    """The k-th recorded failure is the k-th correction round; a count mismatch is a refusal.

    Returns the pairs, or the reason the run cannot be joined.
    """
    if len(failures) != len(rounds):
        return f"{len(failures)} recorded failures against {len(rounds)} correction rounds"
    return list(zip(failures, rounds, strict=True))


def failed_task_artifacts(
    artifacts: Iterable[ArtifactMeta], task_id: str, before: datetime
) -> tuple[str, ...]:
    """The failed task's own emitted files: produced under its task id before its round began."""
    return tuple(
        sorted(a.artifact_id for a in artifacts if a.task_id == task_id and a.created_at < before)
    )


def preceding_checkpoint(
    checkpoints: Iterable[tuple[int, datetime]], before: datetime
) -> int | None:
    """The index of the last checkpoint created before ``before``, or None (pruned or absent)."""
    earlier = [index for index, created_at in checkpoints if created_at < before]
    return max(earlier) if earlier else None


def failures_from_summary(summary: Mapping[str, Any]) -> list[RoundFailure]:
    return [
        RoundFailure(
            task_id=f["task_id"],
            round_index=int(f["round_index"]),
            failed_checks=tuple(f.get("failed_checks") or ()),
            locus=f.get("locus"),
            category=f.get("category"),
        )
        for f in summary.get("round_failures") or ()
    ]
