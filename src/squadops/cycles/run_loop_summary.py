"""The run summary — the loop facts no store held, one durable row per run (SIP-0108 §4.1).

Written at run finalization beside ``run_verification_summaries``. The scorecard's projection
reads it and never reads logs: a fact that lived only in container logs was unreadable to a
projection that may do no I/O, and unrecoverable once a rebuild wiped the logs.

This row carries **usage** (:class:`~squadops.cycles.llm_usage.RunUsage`, accounted at
``_llm_call``), every **refunded correction round** with its reason, and the **correction
movement sequence** — each failed task's round-over-round class, including the round a chain
terminated on — the **structured terminal decision**: the kind of the run's final
transition, with the termination reason, failure classification, task and refusing validators
it was decided on, as values rather than the prose of ``failure_reason`` — each **round's failure**
as the round saw it (the category and locus attribution composes, SIP-0108 §4.2), and each
**absent emission**: a task attempt or a repair round whose response yielded no file. A historical
run has no row: its indicators read unaskable, never backfilled from logs. A row written before
a field was recorded reads that field as ``None``, never as an empty list.

Pure data; the registry adapters persist it.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from squadops.cycles.failure_attribution import TerminalKind
from squadops.cycles.llm_usage import RunUsage

#: The row's contract version. A reader names the version it read.
RUN_LOOP_SUMMARY_VERSION = 1


#: Why a round was refunded: the repair emitted no content (#1053).
REFUND_EMPTY_REPAIR_EMISSION = "empty_repair_emission"
#: ...or the analyzer confirmed a producer's dispute of the check (SIP-0096 §17a change 4):
#: the round found a check defect, not a work defect, and the chain ends before its repair.
REFUND_CONFIRMED_DISPUTE = "confirmed_dispute"


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
class RoundFailure:
    """One correction round's failure, as the round's evidence classified it (SIP-0108 §4.2).

    ``category`` is ``derive_failure_category``'s and ``locus`` is ``classify_failure_locus``'s —
    the deterministic classification of the evidence, not the routing decision a correction
    may override. ``failed_checks`` are the blocking failed rows' check ids.
    """

    task_id: str
    round_index: int
    category: str
    locus: str
    emission_signature: str | None = None
    failed_checks: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "round_index": self.round_index,
            "category": self.category,
            "locus": self.locus,
            "emission_signature": self.emission_signature,
            "failed_checks": list(self.failed_checks),
        }

    @classmethod
    def from_evidence(
        cls, task_id: str, round_index: int, failure_evidence: Mapping[str, Any]
    ) -> RoundFailure:
        """The round's failure read off the evidence the round was diagnosed from."""
        from squadops.cycles.emission_integrity import EMISSION_FAILURE_KEY
        from squadops.cycles.failure_evidence import (
            classify_failure_locus,
            derive_failure_category,
        )
        from squadops.cycles.verification_normalize import row_is_blocking_failure

        evidence = dict(failure_evidence)
        marker = evidence.get(EMISSION_FAILURE_KEY)
        signature = marker.get("signature") if isinstance(marker, Mapping) else None
        rows = (evidence.get("validation_result") or {}).get("checks") or []
        return cls(
            task_id=task_id,
            round_index=round_index,
            category=str(evidence.get("failure_category") or derive_failure_category(evidence)),
            locus=str(classify_failure_locus(evidence)),
            emission_signature=_optional_str(signature),
            failed_checks=tuple(
                sorted(
                    {
                        str(r.get("check"))
                        for r in rows
                        if isinstance(r, Mapping) and r.get("check") and row_is_blocking_failure(r)
                    }
                )
            ),
        )

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> RoundFailure:
        return cls(
            task_id=str(data["task_id"]),
            round_index=int(data["round_index"]),
            category=str(data["category"]),
            locus=str(data["locus"]),
            emission_signature=_optional_str(data.get("emission_signature")),
            failed_checks=tuple(str(c) for c in data.get("failed_checks") or ()),
        )


@dataclass(frozen=True)
class AbsentEmission:
    """One emission that yielded no file (#566's marker, #998's signatures).

    A task's own attempt carries ``attempt`` (1-based); a correction round's empty repair
    carries ``round_index`` (#1053). ``signatures`` are the #998 shapes — ``cap_exhausted``,
    ``empty`` or ``unextractable`` — empty when the producer named none.
    """

    task_id: str
    signatures: tuple[str, ...] = ()
    attempt: int | None = None
    round_index: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "signatures": list(self.signatures),
            "attempt": self.attempt,
            "round_index": self.round_index,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> AbsentEmission:
        return cls(
            task_id=str(data["task_id"]),
            signatures=tuple(str(s) for s in data.get("signatures") or ()),
            attempt=None if data.get("attempt") is None else int(data["attempt"]),
            round_index=None if data.get("round_index") is None else int(data["round_index"]),
        )


@dataclass(frozen=True)
class RunTerminalDecision:
    """How the run ended, declared where it was decided (SIP-0108 §4.1).

    The raise site that ends a run names its kind; the scorecard reads the kind and never parses
    ``failure_reason``. A run-ending exception that declares nothing reads ``other`` — an unknown
    ending is recorded as unknown, never guessed from its message.

    ``failure_classification`` is set only where the deciding failure was classified:
    ``contract_compliance`` for the compliance budget, the terminal round's analysis for a
    plan-defect termination. An exhausted correction budget leaves it ``None``, because the budget
    is checked before the exhausting failure is analysed.

    A cycle-level gate refusal is not here: the inter-workload plan gate records its refusal as a
    ``REJECTED`` gate decision and a ``rejection_record`` artifact, and the run it judged had
    already completed.
    """

    kind: TerminalKind
    termination_reason: str | None = None
    failure_classification: str | None = None
    task_id: str | None = None
    refused_validators: tuple[str, ...] = ()
    #: SIP-0096 §17a: the checks a ``contested_check`` termination names — each confirmed
    #: dispute's check, file and criterion, so the run's end says which check is the defect.
    contested_checks: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": str(self.kind),
            "termination_reason": self.termination_reason,
            "failure_classification": self.failure_classification,
            "task_id": self.task_id,
            "refused_validators": list(self.refused_validators),
            "contested_checks": list(self.contested_checks),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> RunTerminalDecision:
        """Read a decision back. A kind this reader does not know reads ``other``."""
        try:
            kind = TerminalKind(data.get("kind"))
        except ValueError:
            kind = TerminalKind.OTHER
        return cls(
            kind=kind,
            termination_reason=_optional_str(data.get("termination_reason")),
            failure_classification=_optional_str(data.get("failure_classification")),
            task_id=_optional_str(data.get("task_id")),
            refused_validators=tuple(str(v) for v in data.get("refused_validators") or ()),
            contested_checks=tuple(str(c) for c in data.get("contested_checks") or ()),
        )


def _optional_str(value: Any) -> str | None:
    return None if value is None else str(value)


@dataclass(frozen=True)
class RunLoopSummary:
    """One run's loop facts, as persisted at finalization."""

    run_id: str
    usage: RunUsage
    refunded_rounds: tuple[RefundedRound, ...] = ()
    movements: tuple[MovementRecord, ...] = ()
    #: ``None`` only on a row written before the decision was recorded.
    terminal: RunTerminalDecision | None = None
    #: ``None`` on a row written before each was recorded; ``()`` when the run had none.
    round_failures: tuple[RoundFailure, ...] | None = ()
    absent_emissions: tuple[AbsentEmission, ...] | None = ()
    summary_version: int = RUN_LOOP_SUMMARY_VERSION

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "summary_version": self.summary_version,
            "usage": self.usage.to_dict(),
            "refunded_rounds": [r.to_dict() for r in self.refunded_rounds],
            "movements": [m.to_dict() for m in self.movements],
            "terminal": self.terminal.to_dict() if self.terminal is not None else None,
            "round_failures": (
                None if self.round_failures is None else [r.to_dict() for r in self.round_failures]
            ),
            "absent_emissions": (
                None
                if self.absent_emissions is None
                else [a.to_dict() for a in self.absent_emissions]
            ),
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
            terminal=(
                RunTerminalDecision.from_dict(data["terminal"])
                if isinstance(data.get("terminal"), Mapping)
                else None
            ),
            round_failures=(
                None
                if data.get("round_failures") is None
                else tuple(RoundFailure.from_dict(r) for r in data["round_failures"])
            ),
            absent_emissions=(
                None
                if data.get("absent_emissions") is None
                else tuple(AbsentEmission.from_dict(a) for a in data["absent_emissions"])
            ),
            summary_version=int(data.get("summary_version") or RUN_LOOP_SUMMARY_VERSION),
        )
