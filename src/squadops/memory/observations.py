"""Observations: what Cross-Cycle Memory reads from the records that stay authoritative
(SIP-0110 §0.2–§0.5; slice 3a, #2096).

An observation is one immutable occurrence from one of three sources:
- **a rejected plan:** a plan-review gate decision that rejects, with the validators and proofs
  its ``rejection_record`` names (#809);
- **a failed correction round:** a round of the run's loop summary, with its attribution, its
  failed checks and the round's own account of why (``failed_detail``, #2028);
- **a returned proposal:** an increment ruling that returns it (SIP-0109 §9.4), with the
  supervisor's classification.

Each is a projection of its source, keyed by the source record, so projecting the same record
twice adds nothing (§0.3). Pure: the reconciler in ``adapters`` reads the records and writes the
observations.

**Eligibility** (§0.3). A cycle that declares an injected fault is a diagnostic by
construction, a replay re-executes another run, and a failure attributed to the environment
says nothing about authoring. None of these produces an observation.

**Evidence time.** ``observed_at`` is when the source record was committed: the gate decision's
time, the run's finish (its loop summary is written at finalization), or the ruling row's commit.
It is never earlier than the evidence itself, so a replay's temporal-validity cut (§0.11) on it
can only be conservative.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any

from squadops.campaigns.models import (
    ControlLogEntry,
    ControlOperation,
    ControlOutcome,
    ProposalClassification,
)
from squadops.cycles.cycle_assessment import RejectionRecord
from squadops.cycles.failure_attribution import AttributionClass, FailureEvent, compose
from squadops.cycles.models import Cycle, GateDecisionValue, Run
from squadops.cycles.run_loop_summary import RunLoopSummary


class ObservationSource(StrEnum):
    """The three committed records memory observes (§0.3)."""

    PLAN_REVIEW = "plan_review"
    CORRECTION_ROUND = "correction_round"
    PROPOSAL_RULING = "proposal_ruling"


#: The vocabulary an observation's classification is in, by source (§0.4). ``unclassified`` is
#: an explicit disposition, never a missing one.
VOCABULARY_PLAN_VALIDATOR = "plan_validator"
VOCABULARY_ATTRIBUTION = "attribution"
VOCABULARY_PROPOSAL = "proposal_classification"
UNCLASSIFIED = "unclassified"

#: The plan-review gate whose rejections are plan-review observations.
PLAN_REVIEW_GATE = "progress_plan_review"

#: The increment-gate decisions that return a proposal (SIP-0109 §9.4, ``RULING_MOVES``).
_RETURNING_DECISIONS = frozenset(
    {GateDecisionValue.RETURNED_FOR_REVISION.value, GateDecisionValue.REJECTED.value}
)


@dataclass(frozen=True)
class Classification:
    """An observation's classification disposition (§0.4): values in its source's vocabulary,
    or ``unclassified`` with the reason no class was recorded."""

    vocabulary: str
    values: tuple[str, ...] = ()
    rationale: str | None = None

    @property
    def is_classified(self) -> bool:
        return self.vocabulary != UNCLASSIFIED

    def to_dict(self) -> dict[str, Any]:
        return {
            "vocabulary": self.vocabulary,
            "values": list(self.values),
            "rationale": self.rationale,
        }


@dataclass(frozen=True)
class Observation:
    """One occurrence from one source (§0.2), as projected. Immutable: a new occurrence adds an
    observation, never edits one."""

    source: ObservationSource
    #: The source record's identity, which is the observation's: projecting it twice adds nothing.
    source_id: str
    project_id: str
    observed_at: datetime
    classification: Classification
    campaign_id: str | None = None
    cycle_id: str | None = None
    run_id: str | None = None
    task_id: str | None = None
    #: What the source recorded, kept as evidence and never read as guidance (§0.4).
    evidence: Mapping[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> Observation:
        c = data["classification"]
        return cls(
            source=ObservationSource(data["source"]),
            source_id=str(data["source_id"]),
            project_id=str(data["project_id"]),
            campaign_id=data.get("campaign_id"),
            cycle_id=data.get("cycle_id"),
            run_id=data.get("run_id"),
            task_id=data.get("task_id"),
            observed_at=datetime.fromisoformat(str(data["observed_at"])),
            classification=Classification(
                vocabulary=str(c["vocabulary"]),
                values=tuple(str(v) for v in c.get("values") or ()),
                rationale=c.get("rationale"),
            ),
            evidence=dict(data.get("evidence") or {}),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "source": self.source.value,
            "source_id": self.source_id,
            "project_id": self.project_id,
            "campaign_id": self.campaign_id,
            "cycle_id": self.cycle_id,
            "run_id": self.run_id,
            "task_id": self.task_id,
            "observed_at": self.observed_at.isoformat(),
            "classification": self.classification.to_dict(),
            "evidence": dict(self.evidence),
        }


def ineligibility(cycle: Cycle) -> str | None:
    """Why ``cycle`` produces no observation, or ``None`` when it does (§0.3)."""
    from squadops.capabilities.handlers.fault_injection import DECLARATION_KEY
    from squadops.cycles.replay import parse_replay_declaration

    overrides = cycle.execution_overrides or {}
    if overrides.get(DECLARATION_KEY):
        return "fault_injected"
    try:
        if parse_replay_declaration(overrides) is not None:
            return "replay"
    except ValueError:
        return "replay"  # a half-declared replay is still a replay, never an ordinary run
    return None


def observe_cycle(
    cycle: Cycle,
    runs: Sequence[Run],
    loop_summaries: Mapping[str, RunLoopSummary],
    rejection_records: Sequence[RejectionRecord],
) -> list[Observation]:
    """The rejected plans and failed correction rounds of one eligible cycle."""
    if ineligibility(cycle) is not None:
        return []
    observed: list[Observation] = []
    records_by_run: dict[str, list[RejectionRecord]] = {}
    for record in rejection_records:
        records_by_run.setdefault(record.run_id, []).append(record)
    for run in runs:
        observed.extend(_plan_reviews(cycle, run, records_by_run.get(run.run_id, [])))
        summary = loop_summaries.get(run.run_id)
        if summary is not None:
            observed.extend(_correction_rounds(cycle, run, summary))
    return observed


def _plan_reviews(cycle: Cycle, run: Run, records: list[RejectionRecord]) -> list[Observation]:
    observed: list[Observation] = []
    for decision in run.gate_decisions:
        if (
            decision.gate_name != PLAN_REVIEW_GATE
            or decision.decision != GateDecisionValue.REJECTED
        ):
            continue
        refused = sorted({name for r in records for name in (*r.classes, *(r.proofs or {}))})
        classification = (
            Classification(VOCABULARY_PLAN_VALIDATOR, tuple(refused))
            if refused
            else Classification(
                UNCLASSIFIED,
                rationale="a rejection with no rejection_record naming a validator or proof",
            )
        )
        observed.append(
            Observation(
                source=ObservationSource.PLAN_REVIEW,
                source_id=f"plan_review:{run.run_id}:{decision.gate_name}:{decision.decided_at.isoformat()}",
                project_id=cycle.project_id,
                campaign_id=cycle.campaign_id,
                cycle_id=cycle.cycle_id,
                run_id=run.run_id,
                observed_at=decision.decided_at,
                classification=classification,
                evidence={
                    "decided_by": decision.decided_by,
                    "notes": decision.notes or "",
                    "rejection_records": [r.artifact_id for r in records],
                },
            )
        )
    return observed


def _correction_rounds(cycle: Cycle, run: Run, summary: RunLoopSummary) -> list[Observation]:
    observed: list[Observation] = []
    finished = run.finished_at
    if finished is None:  # a summary is written at finalization; an unfinished run has none
        return observed
    for failure in summary.round_failures or ():  # None: a summary written before the field
        attribution = compose(
            FailureEvent(
                run_id=run.run_id,
                task_id=failure.task_id,
                round_index=failure.round_index,
                category=failure.category,
                locus=failure.locus,
                emission_signature=failure.emission_signature,
            )
        )
        if (
            attribution is None
            or attribution is AttributionClass.ENVIRONMENT_OR_INFRASTRUCTURE_FAILURE
        ):
            continue  # not a failure, or the environment's: nothing about authoring (§0.3)
        classification = (
            Classification(UNCLASSIFIED, rationale="the evidence establishes no attribution")
            if attribution is AttributionClass.UNATTRIBUTED
            else Classification(VOCABULARY_ATTRIBUTION, (attribution.value,))
        )
        observed.append(
            Observation(
                source=ObservationSource.CORRECTION_ROUND,
                source_id=f"correction_round:{run.run_id}:{failure.task_id}:{failure.round_index}",
                project_id=cycle.project_id,
                campaign_id=cycle.campaign_id,
                cycle_id=cycle.cycle_id,
                run_id=run.run_id,
                task_id=failure.task_id,
                observed_at=finished,
                classification=classification,
                evidence={
                    "round_index": failure.round_index,
                    "category": failure.category,
                    "locus": failure.locus,
                    "failed_checks": list(failure.failed_checks),
                    "failed_detail": [list(pair) for pair in failure.failed_detail],
                    **_failure_shapes(failure.failed_detail),
                },
            )
        )
    return observed


def _failure_shapes(failed_detail: Sequence[tuple[str, str]]) -> dict[str, Any]:
    """Each failing case's shape, by the table of the runner that ran it (§0.4, D14): an observed
    signature, never a cause. A case no row matches is recorded with no shape: unclassified."""
    # Local: the runner's tables sit in capabilities, which imports this package.
    from squadops.capabilities.handlers.test_runner import (
        FAILURE_SHAPE_TABLE_VERSION,
        failure_shape_of,
    )

    shapes = []
    for check, text in failed_detail:
        runner, shape = failure_shape_of(text)
        shapes.append({"check": check, "runner": runner, "shape": shape})
    return {"failure_shapes": shapes, "failure_shape_table_version": FAILURE_SHAPE_TABLE_VERSION}


def observe_proposal_rulings(
    campaign_id: str,
    project_id: str,
    log: Sequence[ControlLogEntry],
    *,
    ineligible_runs: frozenset[str] = frozenset(),
) -> list[Observation]:
    """The applied rulings that returned a proposal, each with the supervisor's classification of
    that version, or ``unclassified`` when none was recorded (§0.4). ``ineligible_runs`` are
    proposal runs of cycles ``ineligibility`` refuses."""
    classes: dict[tuple[str, int], list[str]] = {}
    for entry in log:
        if entry.operation is ControlOperation.CLASSIFY and entry.outcome is ControlOutcome.APPLIED:
            key = (str(entry.binding.get("proposal_id")), int(entry.binding.get("version") or 0))
            classes.setdefault(key, []).append(str(entry.binding.get("classification")))
    observed: list[Observation] = []
    for entry in log:
        if (
            entry.operation is not ControlOperation.RULE
            or entry.outcome is not ControlOutcome.APPLIED
        ):
            continue
        if str(entry.binding.get("decision")) not in _RETURNING_DECISIONS:
            continue
        if entry.target in ineligible_runs:
            continue
        key = (str(entry.binding.get("proposal_id")), int(entry.binding.get("version") or 0))
        recorded = sorted(set(classes.get(key, [])))
        known = {c.value for c in ProposalClassification}
        classification = (
            Classification(VOCABULARY_PROPOSAL, tuple(recorded))
            if recorded and set(recorded) <= known
            else Classification(
                UNCLASSIFIED, rationale="no classification of this version was recorded"
            )
        )
        observed.append(
            Observation(
                source=ObservationSource.PROPOSAL_RULING,
                source_id=f"proposal_ruling:{campaign_id}:{entry.entry_id}",
                project_id=project_id,
                campaign_id=campaign_id,
                run_id=entry.target,
                observed_at=entry.committed_at,
                classification=classification,
                evidence={
                    "proposal_id": key[0],
                    "version": key[1],
                    "decision": entry.binding.get("decision"),
                    "content_hash": entry.binding.get("content_hash"),
                    "baseline_tree": entry.binding.get("baseline_tree"),
                    "decided_by": entry.actor,
                    "reason": entry.reason,
                },
            )
        )
    return observed
