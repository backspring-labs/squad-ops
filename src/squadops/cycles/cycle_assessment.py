"""The cycle assessment — a pure projection over the durable record (SIP-0108 §4.1 (a)).

``assess(outcome, evidence, assessor=...)`` reads a cycle's ``CycleOutcome`` and a
:class:`CycleEvidence` an adapter assembled from durable stores — the registry's runs and run
summaries, the vault's artifact metadata — and returns four dimensions of indicators and an
attribution. **It performs no I/O, reads no clock and calls no agent** (§3.1); an architecture
test holds that by imports. Nothing here is stored as truth: the stores are the record, and an
assessment is recomputed on read (§4.1).

**Every indicator is three-state and cites what it read** (§3.3): *observed* with its value,
*asked_none* when its producer ran and found nothing, or *unaskable(reason)* when the record cannot
answer it for this cycle. A zero is never written for an unaskable indicator. Every observed value
carries evidence references — a run, a vault artifact, a verification summary or a run summary —
that resolve against the stores it was assembled from.

**What the record cannot answer is named, not guessed.** Each correction round's classified
failure and each emission that yielded no file are on the run summary (SIP-0108 §10d); a row
written before them reads unaskable for them. A failed check's locus at completion and a
compliance budget's refused emissions are not recorded at all. The attribution reports which of
its inputs were unrecorded, so ``unattributed`` is never mistaken for a judgement the evidence
made.
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any

from squadops.cycles.emission_integrity import EMISSION_STATUS_FAILED
from squadops.cycles.failure_attribution import (
    ATTRIBUTION_REGISTRY_VERSION,
    Attribution,
    FailureEvent,
    MovementEvent,
    TerminalEvidence,
    TerminalKind,
    attribute,
)
from squadops.cycles.failure_evidence import FailureEvidenceCategory
from squadops.cycles.gate_attribution import is_machine_decision
from squadops.cycles.llm_usage import UsageTotals
from squadops.cycles.models import GateDecisionValue, RunStatus, WorkloadType
from squadops.cycles.run_loop_summary import RunLoopSummary
from squadops.cycles.task_outcome import CorrectionTerminationReason
from squadops.cycles.verification_integrity import CycleOutcome
from squadops.tasks.task_types import TaskType

#: The contract version of this projection. A reader names the version it read (§4.1).
ASSESSMENT_VERSION = 1

#: The two SIP-0102 indicators no producer answers until its step 5 lands.
UNASKABLE_UNTIL_SIP_0102_STEP_5 = "sip_0102_step_5_not_landed"


class IndicatorState(StrEnum):
    """The three states of the verification-set record (#1445), for the assessment."""

    OBSERVED = "observed"
    ASKED_NONE = "asked_none"
    UNASKABLE = "unaskable"


class RefKind(StrEnum):
    """What an evidence reference names — each resolves against one store."""

    RUN = "registry_run"
    ARTIFACT = "vault_artifact"
    VERIFICATION_SUMMARY = "verification_summary"
    RUN_SUMMARY = "run_summary"


@dataclass(frozen=True, order=True)
class EvidenceRef:
    kind: RefKind
    id: str


@dataclass(frozen=True)
class Indicator:
    """One indicator in the three-state vocabulary, with the references it read."""

    name: str
    state: IndicatorState
    value: Any = None
    reason: str | None = None
    refs: tuple[EvidenceRef, ...] = ()

    @classmethod
    def of(cls, name: str, value: Any, refs: tuple[EvidenceRef, ...] = ()) -> Indicator:
        """``asked_none`` when the value answers nothing, else ``observed``."""
        state = IndicatorState.ASKED_NONE if _answers_nothing(value) else IndicatorState.OBSERVED
        return cls(name, state, value=value, refs=tuple(sorted(set(refs))))

    @classmethod
    def unaskable(cls, name: str, reason: str) -> Indicator:
        return cls(name, IndicatorState.UNASKABLE, reason=reason)


def _answers_nothing(value: Any) -> bool:
    if value is None or value == 0:
        return True
    if isinstance(value, Mapping):
        return all(_answers_nothing(v) for v in value.values())
    if isinstance(value, (list, tuple, set, frozenset)):
        return len(value) == 0
    return False


# ---------------------------------------------------------------------------------------------
# The evidence — assembled by an adapter from durable stores, read here and nowhere else
# ---------------------------------------------------------------------------------------------


@dataclass(frozen=True)
class GateDecisionRecord:
    gate_name: str
    decision: str
    decided_by: str
    waived_checks: tuple[str, ...] = ()


@dataclass(frozen=True)
class RunRecord:
    """A registry run row, as the projection reads it."""

    run_id: str
    run_number: int
    workload_type: str | None
    status: str
    started_at: datetime | None = None
    finished_at: datetime | None = None
    gate_decisions: tuple[GateDecisionRecord, ...] = ()


@dataclass(frozen=True)
class ArtifactRecord:
    """A vault artifact's metadata — the fields the indicators read."""

    artifact_id: str
    run_id: str
    artifact_type: str
    producing_task_type: str | None = None
    task_id: str | None = None
    emission_status: str | None = None
    #: #1436: the 1-based attempt stamped on a banked failed emission; ``None`` before 1.7.5.
    attempt: int | None = None


@dataclass(frozen=True)
class RejectionRecord:
    """A stored ``rejection_record`` (#809): the validators and proofs a gate refused on.

    ``proofs`` is ``None`` for a record written before the gate recorded them (SIP-0108 §4.2).
    """

    artifact_id: str
    run_id: str
    gate: str
    classes: Mapping[str, int] = field(default_factory=dict)
    proofs: Mapping[str, int] | None = None


@dataclass(frozen=True)
class TerminationRecord:
    """A stored ``correction_termination`` artifact (1.5 A4)."""

    artifact_id: str
    run_id: str
    reason: str
    failed_task_id: str


@dataclass(frozen=True)
class CycleEvidence:
    """Everything the projection may read beside ``CycleOutcome``, from durable stores only."""

    cycle_id: str
    runs: tuple[RunRecord, ...]
    #: The runs a verification summary is stored for — the roll-up ``CycleOutcome`` came from.
    verification_summary_runs: tuple[str, ...] = ()
    #: The run summary per run (SIP-0108 §4.1). A run absent here has no row.
    loop_summaries: Mapping[str, RunLoopSummary] = field(default_factory=dict)
    artifacts: tuple[ArtifactRecord, ...] = ()
    rejection_records: tuple[RejectionRecord, ...] = ()
    terminations: tuple[TerminationRecord, ...] = ()


@dataclass(frozen=True)
class AssessorIdentity:
    """The framework that computed an assessment — supplied by the caller, never read here."""

    framework_version: str
    git_sha: str | None


@dataclass(frozen=True)
class AttributionReading:
    """The attribution, and what it could not read.

    ``state`` is ``unaskable`` when the cycle has no terminal transition to attribute yet, or
    when the record of that transition is missing. ``unrecorded`` names inputs the attribution
    needed and the stores do not hold — its primary may read ``unattributed`` because of them.
    """

    state: IndicatorState
    attribution: Attribution | None = None
    terminal_kind: TerminalKind | None = None
    reason: str | None = None
    refs: tuple[EvidenceRef, ...] = ()
    unrecorded: tuple[str, ...] = ()


@dataclass(frozen=True)
class CycleAssessment:
    cycle_id: str
    outcome: tuple[Indicator, ...]
    quality: tuple[Indicator, ...]
    coordination: tuple[Indicator, ...]
    efficiency: tuple[Indicator, ...]
    attribution: AttributionReading
    assessment_version: int
    attribution_registry_version: int
    evidence_identity: str
    assessor: AssessorIdentity

    def indicator(self, name: str) -> Indicator:
        for group in (self.outcome, self.quality, self.coordination, self.efficiency):
            for ind in group:
                if ind.name == name:
                    return ind
        raise KeyError(name)


# ---------------------------------------------------------------------------------------------
# The projection
# ---------------------------------------------------------------------------------------------


def assess(
    outcome: CycleOutcome, evidence: CycleEvidence, *, assessor: AssessorIdentity
) -> CycleAssessment:
    """The cycle's four dimensions and attribution, read from ``outcome`` and ``evidence``."""
    return CycleAssessment(
        cycle_id=evidence.cycle_id,
        outcome=_outcome_dimension(outcome, evidence),
        quality=_quality_dimension(outcome, evidence),
        coordination=_coordination_dimension(evidence),
        efficiency=_efficiency_dimension(evidence),
        attribution=_attribution(outcome, evidence),
        assessment_version=ASSESSMENT_VERSION,
        attribution_registry_version=ATTRIBUTION_REGISTRY_VERSION,
        evidence_identity=evidence_identity(outcome, evidence),
        assessor=assessor,
    )


def _summary_refs(evidence: CycleEvidence) -> tuple[EvidenceRef, ...]:
    return tuple(
        EvidenceRef(RefKind.VERIFICATION_SUMMARY, run_id)
        for run_id in evidence.verification_summary_runs
    )


def _no_summaries(outcome: CycleOutcome, evidence: CycleEvidence) -> bool:
    return outcome.run_count == 0 or not evidence.verification_summary_runs


_NO_VERIFICATION_SUMMARY = "no_verification_summary"


def _by_reason(checks: Any) -> dict[str, list[str]]:
    grouped: dict[str, list[str]] = {}
    for check in checks:
        grouped.setdefault(check.reason, []).append(check.check_id)
    return {reason: sorted(ids) for reason, ids in sorted(grouped.items())}


def _outcome_dimension(outcome: CycleOutcome, evidence: CycleEvidence) -> tuple[Indicator, ...]:
    names = ("verdict", "criteria_coverage", "required_unverified_by_reason", "inert", "waived")
    if _no_summaries(outcome, evidence):
        return tuple(Indicator.unaskable(n, _NO_VERIFICATION_SUMMARY) for n in names)
    refs = _summary_refs(evidence)
    verified, total = outcome.criteria_coverage
    waiver_refs = tuple(
        EvidenceRef(RefKind.RUN, run.run_id)
        for run in evidence.runs
        if any(g.waived_checks for g in run.gate_decisions)
    )
    return (
        Indicator.of("verdict", str(outcome.verdict), refs),
        Indicator.of("criteria_coverage", {"verified": verified, "total": total}, refs),
        Indicator.of(
            "required_unverified_by_reason",
            _by_reason(u for u in outcome.unverified if u.required),
            refs,
        ),
        Indicator.of("inert", sorted(outcome.inert), refs),
        Indicator.of(
            "waived",
            sorted(w.check_id for w in outcome.waived),
            waiver_refs if outcome.waived else (),
        ),
    )


def _quality_dimension(outcome: CycleOutcome, evidence: CycleEvidence) -> tuple[Indicator, ...]:
    unaskable_until = (
        Indicator.unaskable("verified_executable", UNASKABLE_UNTIL_SIP_0102_STEP_5),
        Indicator.unaskable("verified_functional", UNASKABLE_UNTIL_SIP_0102_STEP_5),
    )
    if _no_summaries(outcome, evidence):
        return (
            Indicator.unaskable("failed_checks", _NO_VERIFICATION_SUMMARY),
            Indicator.unaskable("unverified_by_reason", _NO_VERIFICATION_SUMMARY),
            *unaskable_until,
        )
    refs = _summary_refs(evidence)
    return (
        Indicator.of("failed_checks", sorted(outcome.failed), refs),
        Indicator.of("unverified_by_reason", _by_reason(outcome.unverified), refs),
        *unaskable_until,
    )


def _missing_run_summaries(evidence: CycleEvidence) -> list[str]:
    return [r.run_id for r in evidence.runs if r.run_id not in evidence.loop_summaries]


def _no_run_summary_reason(missing: list[str]) -> str:
    return f"no_run_summary: {', '.join(missing)}"


def _coordination_dimension(evidence: CycleEvidence) -> tuple[Indicator, ...]:
    if not evidence.runs:
        names = (
            "correction_rounds",
            "failed_emission_artifacts",
            "failed_emissions",
            "contentless_emissions",
            "framing_rerolls",
            "plan_defect_terminations",
            "refunded_rounds",
            "correction_movements",
        )
        return tuple(Indicator.unaskable(n, "no_runs") for n in names)

    decisions = [
        a
        for a in evidence.artifacts
        if a.producing_task_type == TaskType.GOVERNANCE_CORRECTION_DECISION
    ]
    banked = [a for a in evidence.artifacts if a.emission_status == EMISSION_STATUS_FAILED]
    if any(a.attempt is None for a in banked):
        failed_emissions = Indicator.unaskable("failed_emissions", "no_attempt_stamp")
    else:
        failed_emissions = Indicator.of(
            "failed_emissions",
            len({(a.task_id, a.attempt) for a in banked}),
            tuple(EvidenceRef(RefKind.ARTIFACT, a.artifact_id) for a in banked),
        )
    framing = sorted(
        (r for r in evidence.runs if r.workload_type == WorkloadType.FRAMING),
        key=lambda r: r.run_number,
    )
    plan_defects = [
        t for t in evidence.terminations if t.reason == CorrectionTerminationReason.PLAN_DEFECT
    ]

    missing = _missing_run_summaries(evidence)
    if missing:
        refunds = Indicator.unaskable("refunded_rounds", _no_run_summary_reason(missing))
        movements = Indicator.unaskable("correction_movements", _no_run_summary_reason(missing))
    else:
        refund_runs = [
            (run_id, s)
            for run_id, s in sorted(evidence.loop_summaries.items())
            if s.refunded_rounds
        ]
        refunds = Indicator.of(
            "refunded_rounds",
            [
                dict(r.to_dict(), run_id=run_id)
                for run_id, s in refund_runs
                for r in s.refunded_rounds
            ],
            tuple(EvidenceRef(RefKind.RUN_SUMMARY, run_id) for run_id, _ in refund_runs),
        )
        movement_runs = [
            (run_id, s) for run_id, s in sorted(evidence.loop_summaries.items()) if s.movements
        ]
        movements = Indicator.of(
            "correction_movements",
            [dict(m.to_dict(), run_id=run_id) for run_id, s in movement_runs for m in s.movements],
            tuple(EvidenceRef(RefKind.RUN_SUMMARY, run_id) for run_id, _ in movement_runs),
        )

    return (
        Indicator.of(
            "correction_rounds",
            len(decisions),
            tuple(EvidenceRef(RefKind.ARTIFACT, a.artifact_id) for a in decisions),
        ),
        Indicator.of(
            "failed_emission_artifacts",
            len(banked),
            tuple(EvidenceRef(RefKind.ARTIFACT, a.artifact_id) for a in banked),
        ),
        failed_emissions,
        _contentless_emissions(evidence, missing),
        Indicator.of(
            "framing_rerolls",
            max(0, len(framing) - 1),
            tuple(EvidenceRef(RefKind.RUN, r.run_id) for r in framing[1:]),
        ),
        Indicator.of(
            "plan_defect_terminations",
            len(plan_defects),
            tuple(EvidenceRef(RefKind.ARTIFACT, t.artifact_id) for t in plan_defects),
        ),
        refunds,
        movements,
    )


def _contentless_emissions(evidence: CycleEvidence, missing: list[str]) -> Indicator:
    """Every emission that yielded no file (SIP-0108 §10d): a task's own attempts and the
    correction rounds whose repair was empty, from the run summaries that recorded them."""
    name = "contentless_emissions"
    if missing:
        return Indicator.unaskable(name, _no_run_summary_reason(missing))
    predates = sorted(
        run_id for run_id, s in evidence.loop_summaries.items() if s.absent_emissions is None
    )
    if predates:
        return Indicator.unaskable(name, f"run_summary_predates_capture: {', '.join(predates)}")
    recorded = [
        (run_id, a)
        for run_id, s in sorted(evidence.loop_summaries.items())
        for a in s.absent_emissions or ()
    ]
    return Indicator.of(
        name,
        {
            "task_attempts": sum(1 for _, a in recorded if a.attempt is not None),
            "repair_rounds": sum(1 for _, a in recorded if a.round_index is not None),
        },
        tuple(EvidenceRef(RefKind.RUN_SUMMARY, run_id) for run_id, _ in recorded),
    )


def _efficiency_dimension(evidence: CycleEvidence) -> tuple[Indicator, ...]:
    if not evidence.runs:
        names = (
            "wall_clock_seconds_by_run",
            "wall_clock_seconds",
            "tokens_by_run",
            "tokens_by_task_type",
            "llm_calls",
        )
        return tuple(Indicator.unaskable(n, "no_runs") for n in names)

    unfinished = [r.run_id for r in evidence.runs if r.started_at is None or r.finished_at is None]
    by_run = {
        r.run_id: (r.finished_at - r.started_at).total_seconds()
        for r in evidence.runs
        if r.started_at is not None and r.finished_at is not None
    }
    run_refs = tuple(EvidenceRef(RefKind.RUN, run_id) for run_id in by_run)
    if unfinished:
        reason = f"run_unfinished: {', '.join(unfinished)}"
        wall = (
            Indicator.unaskable("wall_clock_seconds_by_run", reason),
            Indicator.unaskable("wall_clock_seconds", reason),
        )
    else:
        wall = (
            Indicator.of("wall_clock_seconds_by_run", dict(sorted(by_run.items())), run_refs),
            Indicator.of("wall_clock_seconds", sum(by_run.values()), run_refs),
        )

    missing = _missing_run_summaries(evidence)
    if missing:
        reason = _no_run_summary_reason(missing)
        usage = (
            Indicator.unaskable("tokens_by_run", reason),
            Indicator.unaskable("tokens_by_task_type", reason),
            Indicator.unaskable("llm_calls", reason),
        )
    else:
        summaries = dict(sorted(evidence.loop_summaries.items()))
        summary_refs = tuple(EvidenceRef(RefKind.RUN_SUMMARY, run_id) for run_id in summaries)
        by_type: dict[str, UsageTotals] = {}
        total = UsageTotals()
        for s in summaries.values():
            total = total + s.usage.total
            for task_type, totals in s.usage.by_task_type.items():
                by_type[task_type] = by_type.get(task_type, UsageTotals()) + totals
        unreported = sorted(t for s in summaries.values() for t in s.usage.tasks_unreported)
        usage = (
            Indicator.of(
                "tokens_by_run",
                {run_id: _tokens(s.usage.total) for run_id, s in summaries.items()},
                summary_refs,
            ),
            Indicator.of(
                "tokens_by_task_type",
                {t: _tokens(v) for t, v in sorted(by_type.items())},
                summary_refs,
            ),
            Indicator.of(
                "llm_calls",
                {
                    "calls": total.calls,
                    "failed_calls": total.failed_calls,
                    "tasks_unreported": unreported,
                },
                summary_refs,
            ),
        )
    return (*wall, *usage)


def _tokens(totals: UsageTotals) -> dict[str, int]:
    return {
        "prompt": totals.prompt_tokens,
        "completion": totals.completion_tokens,
        "reasoning": totals.reasoning_tokens,
        "unreported_prompt": totals.unreported_prompt,
        "unreported_completion": totals.unreported_completion,
        "unreported_reasoning": totals.unreported_reasoning,
    }


# ---------------------------------------------------------------------------------------------
# Attribution — the terminal evidence of the cycle's final state transition (§4.2)
# ---------------------------------------------------------------------------------------------

#: Inputs the attribution rows need and no store holds (see the module docstring).
UNRECORDED_ROUND_FAILURE_EVENTS = "round_failure_events: run summary predates their recording"
UNRECORDED_CHECK_LOCUS = "failed_check_locus: not stored"
UNRECORDED_REFUSED_EMISSIONS = "refused_emissions: evidence events are not stored as values"
UNRECORDED_PROOFS = "failed_proofs: rejection record predates their recording"

_TERMINAL_STATUSES = frozenset({RunStatus.COMPLETED, RunStatus.FAILED, RunStatus.CANCELLED})


def _attribution(outcome: CycleOutcome, evidence: CycleEvidence) -> AttributionReading:
    if not evidence.runs:
        return AttributionReading(IndicatorState.UNASKABLE, reason="no_runs")
    final = max(evidence.runs, key=lambda r: r.run_number)
    if final.status not in _TERMINAL_STATUSES:
        return AttributionReading(
            IndicatorState.UNASKABLE, reason=f"cycle_not_terminal: {final.status}"
        )

    if any(
        g.decision == GateDecisionValue.REJECTED and is_machine_decision(g.decided_by)
        for g in final.gate_decisions
    ):
        return _gate_refusal(final, evidence)
    if final.status == RunStatus.COMPLETED:
        return _completed(final, outcome, evidence)
    if final.status == RunStatus.FAILED:
        return _failed_run(final, evidence)
    return _read(
        TerminalEvidence(kind=TerminalKind.OTHER),
        refs=(EvidenceRef(RefKind.RUN, final.run_id),),
    )


def _read(
    terminal: TerminalEvidence, *, refs: tuple[EvidenceRef, ...], unrecorded: tuple[str, ...] = ()
) -> AttributionReading:
    return AttributionReading(
        IndicatorState.OBSERVED,
        attribution=attribute(terminal),
        terminal_kind=terminal.kind,
        refs=tuple(sorted(set(refs))),
        unrecorded=unrecorded,
    )


def _gate_refusal(final: RunRecord, evidence: CycleEvidence) -> AttributionReading:
    records = [r for r in evidence.rejection_records if r.run_id == final.run_id]
    if not records:
        return AttributionReading(
            IndicatorState.UNASKABLE, reason=f"no_rejection_record: {final.run_id}"
        )
    record = records[-1]
    validators = tuple(sorted(record.classes))
    proofs = tuple(sorted(record.proofs or {}))
    refs = (
        EvidenceRef(RefKind.RUN, final.run_id),
        EvidenceRef(RefKind.ARTIFACT, record.artifact_id),
    )
    if record.proofs is None and not validators:
        # A pre-§4.2 record with no classified validator: plan and manifest refusals are
        # indistinguishable without parsing the note, so the row is not chosen.
        return _read(
            TerminalEvidence(kind=TerminalKind.OTHER), refs=refs, unrecorded=(UNRECORDED_PROOFS,)
        )
    kind = (
        TerminalKind.MANIFEST_GATE_REFUSED
        if proofs and not validators
        else TerminalKind.PLAN_GATE_REFUSED
    )
    return _read(
        TerminalEvidence(kind=kind, refused_validators=validators, failed_proofs=proofs),
        refs=refs,
        unrecorded=(UNRECORDED_PROOFS,) if record.proofs is None else (),
    )


def _completed(
    final: RunRecord, outcome: CycleOutcome, evidence: CycleEvidence
) -> AttributionReading:
    if _no_summaries(outcome, evidence):
        return AttributionReading(IndicatorState.UNASKABLE, reason=_NO_VERIFICATION_SUMMARY)
    verdict = str(outcome.verdict)
    failures = tuple(
        FailureEvent(
            run_id=final.run_id,
            task_id="",
            check_id=check_id,
            category=FailureEvidenceCategory.EXECUTED_AND_FAILED,
        )
        for check_id in sorted(outcome.failed)
    )
    unverified = tuple(
        FailureEvent(
            run_id=final.run_id, task_id="", check_id=u.check_id, not_executed_reason=u.reason
        )
        for u in sorted(outcome.unverified, key=lambda u: u.check_id)
        if u.required
    )
    return _read(
        TerminalEvidence(
            kind=TerminalKind.COMPLETED,
            verdict=verdict,
            failure_events=failures,
            unverified=unverified,
        ),
        refs=(EvidenceRef(RefKind.RUN, final.run_id), *_summary_refs(evidence)),
        unrecorded=(UNRECORDED_CHECK_LOCUS,) if failures else (),
    )


def _failed_run(final: RunRecord, evidence: CycleEvidence) -> AttributionReading:
    summary = evidence.loop_summaries.get(final.run_id)
    if summary is None or summary.terminal is None:
        return AttributionReading(
            IndicatorState.UNASKABLE, reason=f"no_terminal_decision: {final.run_id}"
        )
    decision = summary.terminal
    refs = (EvidenceRef(RefKind.RUN, final.run_id), EvidenceRef(RefKind.RUN_SUMMARY, final.run_id))
    movements = tuple(
        MovementEvent(
            run_id=final.run_id, task_id=m.task_id, round_index=m.round_index, movement=m.movement
        )
        for m in summary.movements
    )
    unrecorded: tuple[str, ...] = ()
    failures: tuple[FailureEvent, ...] = ()
    if decision.kind in (TerminalKind.CORRECTION_TERMINATED, TerminalKind.RUN_TIME_BUDGET_EXCEEDED):
        if summary.round_failures is None:
            unrecorded = (UNRECORDED_ROUND_FAILURE_EVENTS,)
        else:
            failures = tuple(
                FailureEvent(
                    run_id=final.run_id,
                    task_id=r.task_id,
                    round_index=r.round_index,
                    category=r.category,
                    locus=r.locus,
                    emission_signature=r.emission_signature,
                )
                for r in summary.round_failures
            )
    elif decision.kind == TerminalKind.COMPLIANCE_BUDGET_EXCEEDED:
        unrecorded = (UNRECORDED_REFUSED_EMISSIONS,)
    return _read(
        TerminalEvidence(
            kind=decision.kind,
            refused_validators=decision.refused_validators,
            termination_reason=decision.termination_reason,
            failure_events=failures,
            movements=movements,
        ),
        refs=refs,
        unrecorded=unrecorded,
    )


# ---------------------------------------------------------------------------------------------
# Identity
# ---------------------------------------------------------------------------------------------


def evidence_identity(outcome: CycleOutcome, evidence: CycleEvidence) -> str:
    """A sha256 over the canonical form of both arguments — equal evidence, equal identity,
    whatever order the adapter assembled it in."""
    payload = {"outcome": _canonical(outcome), "evidence": _canonical(evidence)}
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def _canonical(obj: Any) -> Any:
    if isinstance(obj, RunLoopSummary):
        return obj.to_dict()
    if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
        return {f.name: _canonical(getattr(obj, f.name)) for f in dataclasses.fields(obj)}
    if isinstance(obj, Mapping):
        return {str(k): _canonical(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple, set, frozenset)):
        items = [_canonical(v) for v in obj]
        return sorted(items, key=lambda v: json.dumps(v, sort_keys=True))
    if isinstance(obj, datetime):
        return obj.isoformat()
    if isinstance(obj, StrEnum):
        return str(obj)
    return obj
