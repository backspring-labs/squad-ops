"""The one failure-attribution registry (SIP-0108 §4.2).

Every attribution class literal, every source value's disposition and every composition rule
lives here. The source vocabularies stay where they are authoritative — the failure evidence
category and locus, the plan validators, the manifest's winnability proofs, the correction
movement, the correction termination reason, the framework's failure classification and the
not-executed reason — and a consumer imports this module rather than re-deriving a mapping
from any of them.

**Classes name what the evidence shows, never a cause.** Evidence cannot establish a cause,
and Campaign will act on these values, so a deterministic but unjustified causal label is worse
than :attr:`AttributionClass.UNATTRIBUTED`. Later analysis — a person, an agent, Campaign,
memory — may infer causes from these facts; the scorecard does not.

**Totality over dispositions.** Every value of every source vocabulary has exactly one declared
:class:`Disposition`, carrying the governance attribute ``primary_eligible`` as a required
keyword (the #730 ``CheckSpec`` shape, so no entry defaults through). A drift test enumerates
each vocabulary from its own module and fails on a value declared zero times or twice.
``non_failure`` is a first-class declaration: ``new`` and ``progress`` are movements that are
not failures, and ``converged`` is a termination that is not one.

**Provenance.** A :class:`~squadops.cycles.task_outcome.FailureClassification` is an input only
where the framework set it deterministically — a handler's own ``failure_classification`` or
the executor's compliance termination. The analyzer's ``classification`` is an agent's output
and never an input (SIP-0108 §3.1); the evidence assembler that feeds :func:`attribute` holds
that line, and this module has no way to tell the two apart, so it says so here.

Pure: no I/O, no clock, no agent. The same evidence in any order yields the same attribution.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from enum import StrEnum

from squadops.cycles import manifest_gates
from squadops.cycles.correction_signature import (
    MOVEMENT_EXPANSION,
    MOVEMENT_NEW,
    MOVEMENT_PROGRESS,
    MOVEMENT_REPEAT,
    MOVEMENT_SHIFTED,
)
from squadops.cycles.emission_integrity import SIGNATURE_CAP_EXHAUSTED
from squadops.cycles.failure_evidence import FailureEvidenceCategory, FailureLocus
from squadops.cycles.task_outcome import CorrectionTerminationReason, FailureClassification
from squadops.cycles.verification_integrity import (
    EVALUATOR_GAP_PREFIX,
    UNSPECIFIED_REASON,
    NotExecutedReason,
)

#: The registry's contract version — named by every assessment that reads it (SIP-0108 §4.1).
ATTRIBUTION_REGISTRY_VERSION = 1


class AttributionClass(StrEnum):
    """What the evidence shows (SIP-0108 §4.2). The only home of these literals."""

    #: A producer's artifact failed an executed criterion, the application under test failed
    #: it, or the emission had nothing extractable below its completion cap.
    PRODUCER_OUTPUT_FAILURE = "producer_output_failure"
    #: The verifying artifact itself could not run or collect: the suite is the defect.
    VERIFICATION_ARTIFACT_FAILURE = "verification_artifact_failure"
    #: Content lost between emission and artifact, a correction chain terminated as not
    #: progressing, or rounds that moved without converging.
    HANDOFF_OR_CONVERGENCE_FAILURE = "handoff_or_convergence_failure"
    #: A task's inputs lacked what its contract required. **Reserved**: no reachable evidence
    #: establishes it today, and the registry says so rather than manufacturing a mapping.
    INPUT_CONTRACT_FAILURE = "input_contract_failure"
    #: A declared budget ran out: the completion cap with nothing extractable, the correction
    #: attempts, the run time budget.
    BUDGET_EXHAUSTION = "budget_exhaustion"
    #: The implementation plan was refused by a named plan validator.
    PLAN_GATE_FAILURE = "plan_gate_failure"
    #: The authored manifest or its criteria were refused by a named winnability proof.
    CRITERIA_OR_CONTRACT_FAILURE = "criteria_or_contract_failure"
    #: A producer emitted outside its write grant past the compliance budget (SIP-0100 §3.4a).
    WRITE_AUTHORITY_VIOLATION = "write_authority_violation"
    #: The environment failed before or around the product.
    ENVIRONMENT_OR_INFRASTRUCTURE_FAILURE = "environment_or_infrastructure_failure"
    #: The evidence establishes less than any class claims — counted and shown, never hidden.
    UNATTRIBUTED = "unattributed"


class DispositionKind(StrEnum):
    """How a source value is disposed of."""

    #: The value maps to one class on its own.
    ATTRIBUTION = "attribution"
    #: The value is not a failure (a movement toward convergence, a configured non-execution).
    NON_FAILURE = "non_failure"
    #: The value is an executed failure whose class depends on its locus (rule 5).
    COMPOSED_WITH_LOCUS = "composed_with_locus"
    #: The value is the locus that rule 5 composes with — never attributed alone.
    LOCUS = "locus"
    #: An absent emission: the completion cap decides between two classes (rule 3).
    ABSENT_EMISSION = "absent_emission"


class Vocabulary(StrEnum):
    """The eight source vocabularies (SIP-0108 §2)."""

    FAILURE_EVIDENCE_CATEGORY = "failure_evidence_category"
    FAILURE_LOCUS = "failure_locus"
    PLAN_VALIDATOR = "plan_validator"
    WINNABILITY_PROOF = "winnability_proof"
    CORRECTION_MOVEMENT = "correction_movement"
    CORRECTION_TERMINATION_REASON = "correction_termination_reason"
    FAILURE_CLASSIFICATION = "failure_classification"
    NOT_EXECUTED_REASON = "not_executed_reason"


@dataclass(frozen=True, kw_only=True)
class Disposition:
    """One source value's declared disposition. Every attribute is required (#730)."""

    vocabulary: Vocabulary
    value: str
    kind: DispositionKind
    attribution: AttributionClass | None
    primary_eligible: bool

    def __post_init__(self) -> None:
        if (self.kind == DispositionKind.ATTRIBUTION) != (self.attribution is not None):
            raise ValueError(
                f"{self.vocabulary}:{self.value}: an attribution disposition names exactly one "
                f"class, and no other kind names one"
            )


def _each(
    vocabulary: Vocabulary,
    values: Iterable[str],
    kind: DispositionKind,
    attribution: AttributionClass | None,
    *,
    primary_eligible: bool,
) -> tuple[Disposition, ...]:
    return tuple(
        Disposition(
            vocabulary=vocabulary,
            value=value,
            kind=kind,
            attribution=attribution,
            primary_eligible=primary_eligible,
        )
        for value in values
    )


_A = DispositionKind.ATTRIBUTION
_C = AttributionClass

#: Every plan validator a plan gate can refuse under — ``ImplementationPlan.validate_*``, the
#: names ``RejectionClassifier`` records. Listed, not introspected, so a new validator fails the
#: drift test until someone declares what its refusal shows.
PLAN_VALIDATORS: tuple[str, ...] = (
    "validate_against_profile",
    "validate_build_config",
    "validate_builder_floor",
    "validate_check_applicability",
    "validate_command_checks",
    "validate_criteria_refs",
    "validate_criteria_scope",
    "validate_derived_criteria",
    "validate_expected_artifact_shapes",
    "validate_frozen_artifact_ownership",
    "validate_manifest_plan_consistency",
    "validate_module_existence",
    "validate_qa_artifact_ownership",
    "validate_qa_suite_namespace",
    "validate_unique_expected_artifacts",
)

#: Every winnability proof class a manifest gate can report (``manifest_gates.PROOF_*``).
WINNABILITY_PROOFS: tuple[str, ...] = (
    manifest_gates.PROOF_PARSES,
    manifest_gates.PROOF_LINT,
    manifest_gates.PROOF_EXPANDS,
    manifest_gates.PROOF_CONTRACT_DERIVES,
    manifest_gates.PROOF_CHECKS_LIVE,
    manifest_gates.PROOF_TESTID_COVERAGE,
    manifest_gates.PROOF_STATUS_DECLARED,
    manifest_gates.PROOF_STATUS_WARRANTED,
    manifest_gates.PROOF_ERROR_SHAPE,
    manifest_gates.PROOF_STACK_MATCHES_CONFIG,
    manifest_gates.PROOF_SCAFFOLD_READY,
    manifest_gates.PROOF_INTERFACE_COHERENT,
    manifest_gates.PROOF_SOURCE_PRD,
    manifest_gates.PROOF_DECISION_RECORD,
)

#: The declared value for the evaluator-gap family: every ``evaluator_gap:<reason>`` resolves
#: to this one entry.
EVALUATOR_GAP_FAMILY = f"{EVALUATOR_GAP_PREFIX}*"

DISPOSITIONS: tuple[Disposition, ...] = (
    # FailureEvidenceCategory
    *_each(
        Vocabulary.FAILURE_EVIDENCE_CATEGORY,
        (FailureEvidenceCategory.EXECUTED_AND_FAILED, FailureEvidenceCategory.APP_ERROR),
        DispositionKind.COMPOSED_WITH_LOCUS,
        None,
        primary_eligible=True,
    ),
    *_each(
        Vocabulary.FAILURE_EVIDENCE_CATEGORY,
        (FailureEvidenceCategory.EXTRACTION_LOSS,),
        _A,
        _C.HANDOFF_OR_CONVERGENCE_FAILURE,
        primary_eligible=True,
    ),
    *_each(
        Vocabulary.FAILURE_EVIDENCE_CATEGORY,
        (FailureEvidenceCategory.EMISSION_ABSENT,),
        DispositionKind.ABSENT_EMISSION,
        None,
        primary_eligible=True,
    ),
    *_each(
        Vocabulary.FAILURE_EVIDENCE_CATEGORY,
        (
            FailureEvidenceCategory.SANDBOX_PREEXEC_FAILURE,
            FailureEvidenceCategory.VERIFICATION_INFRA_FAILURE,
        ),
        _A,
        _C.ENVIRONMENT_OR_INFRASTRUCTURE_FAILURE,
        primary_eligible=True,
    ),
    *_each(
        Vocabulary.FAILURE_EVIDENCE_CATEGORY,
        (FailureEvidenceCategory.EVIDENCE_UNAVAILABLE,),
        _A,
        _C.UNATTRIBUTED,
        primary_eligible=True,
    ),
    # FailureLocus — composed with the category, never attributed alone
    *_each(
        Vocabulary.FAILURE_LOCUS,
        (FailureLocus.OWN_ARTIFACT, FailureLocus.SUBJECT, FailureLocus.UNKNOWN),
        DispositionKind.LOCUS,
        None,
        primary_eligible=False,
    ),
    # Plan validators and winnability proofs
    *_each(
        Vocabulary.PLAN_VALIDATOR,
        PLAN_VALIDATORS,
        _A,
        _C.PLAN_GATE_FAILURE,
        primary_eligible=True,
    ),
    *_each(
        Vocabulary.WINNABILITY_PROOF,
        WINNABILITY_PROOFS,
        _A,
        _C.CRITERIA_OR_CONTRACT_FAILURE,
        primary_eligible=True,
    ),
    # Correction movement — contributing only
    *_each(
        Vocabulary.CORRECTION_MOVEMENT,
        (MOVEMENT_REPEAT, MOVEMENT_SHIFTED, MOVEMENT_EXPANSION),
        _A,
        _C.HANDOFF_OR_CONVERGENCE_FAILURE,
        primary_eligible=False,
    ),
    *_each(
        Vocabulary.CORRECTION_MOVEMENT,
        (MOVEMENT_NEW, MOVEMENT_PROGRESS),
        DispositionKind.NON_FAILURE,
        None,
        primary_eligible=False,
    ),
    # CorrectionTerminationReason
    *_each(
        Vocabulary.CORRECTION_TERMINATION_REASON,
        (CorrectionTerminationReason.EXHAUSTED,),
        _A,
        _C.BUDGET_EXHAUSTION,
        primary_eligible=True,
    ),
    *_each(
        Vocabulary.CORRECTION_TERMINATION_REASON,
        (CorrectionTerminationReason.PLAN_DEFECT,),
        _A,
        _C.HANDOFF_OR_CONVERGENCE_FAILURE,
        primary_eligible=True,
    ),
    # SIP-0096 §17a change 5: a confirmed dispute is a check defect (SIP-0108 §4.2).
    *_each(
        Vocabulary.CORRECTION_TERMINATION_REASON,
        (CorrectionTerminationReason.CONTESTED_CHECK,),
        _A,
        _C.CRITERIA_OR_CONTRACT_FAILURE,
        primary_eligible=True,
    ),
    *_each(
        Vocabulary.CORRECTION_TERMINATION_REASON,
        (CorrectionTerminationReason.INFRASTRUCTURE_FAILURE,),
        _A,
        _C.ENVIRONMENT_OR_INFRASTRUCTURE_FAILURE,
        primary_eligible=True,
    ),
    *_each(
        Vocabulary.CORRECTION_TERMINATION_REASON,
        (CorrectionTerminationReason.CONVERGED,),
        DispositionKind.NON_FAILURE,
        None,
        primary_eligible=False,
    ),
    # FailureClassification — framework-set values only (see the module docstring)
    *_each(
        Vocabulary.FAILURE_CLASSIFICATION,
        (FailureClassification.WORK_PRODUCT,),
        _A,
        _C.PRODUCER_OUTPUT_FAILURE,
        primary_eligible=True,
    ),
    *_each(
        Vocabulary.FAILURE_CLASSIFICATION,
        (FailureClassification.CONTRACT_COMPLIANCE,),
        _A,
        _C.WRITE_AUTHORITY_VIOLATION,
        primary_eligible=True,
    ),
    *_each(
        Vocabulary.FAILURE_CLASSIFICATION,
        (FailureClassification.EXECUTION,),
        _A,
        _C.ENVIRONMENT_OR_INFRASTRUCTURE_FAILURE,
        primary_eligible=True,
    ),
    # Each of these names a cause, and only the analyzer sets it.
    *_each(
        Vocabulary.FAILURE_CLASSIFICATION,
        (
            FailureClassification.ALIGNMENT,
            FailureClassification.DECISION,
            FailureClassification.MODEL_LIMITATION,
        ),
        _A,
        _C.UNATTRIBUTED,
        primary_eligible=True,
    ),
    # NotExecutedReason
    *_each(
        Vocabulary.NOT_EXECUTED_REASON,
        (NotExecutedReason.MISSING_TOOLING, NotExecutedReason.TIMEOUT_BEFORE_EXECUTION),
        _A,
        _C.ENVIRONMENT_OR_INFRASTRUCTURE_FAILURE,
        primary_eligible=True,
    ),
    *_each(
        Vocabulary.NOT_EXECUTED_REASON,
        (NotExecutedReason.SUBJECT_MISSING, NotExecutedReason.IMPORT_ERROR),
        _A,
        _C.PRODUCER_OUTPUT_FAILURE,
        primary_eligible=True,
    ),
    # Declared non-execution by configuration.
    *_each(
        Vocabulary.NOT_EXECUTED_REASON,
        (
            NotExecutedReason.CONFIG_DISABLED,
            NotExecutedReason.UNSUPPORTED_STACK,
            NotExecutedReason.FILTERED_OUT,
        ),
        DispositionKind.NON_FAILURE,
        None,
        primary_eligible=False,
    ),
    *_each(
        Vocabulary.NOT_EXECUTED_REASON,
        (EVALUATOR_GAP_FAMILY, UNSPECIFIED_REASON),
        _A,
        _C.UNATTRIBUTED,
        primary_eligible=True,
    ),
)


def _index(dispositions: Iterable[Disposition]) -> Mapping[tuple[Vocabulary, str], Disposition]:
    index: dict[tuple[Vocabulary, str], Disposition] = {}
    for d in dispositions:
        key = (d.vocabulary, d.value)
        if key in index:
            raise ValueError(f"{d.vocabulary}:{d.value} is declared twice")
        index[key] = d
    return index


_BY_VALUE = _index(DISPOSITIONS)


def disposition_for(vocabulary: Vocabulary, value: str) -> Disposition | None:
    """The declared disposition of ``value``, or ``None`` when it is undeclared.

    An ``evaluator_gap:<reason>`` resolves to the family entry. ``None`` is not a guess: the
    caller treats an undeclared value as :attr:`AttributionClass.UNATTRIBUTED`, and the drift
    test is what keeps every current value declared.
    """
    if vocabulary == Vocabulary.NOT_EXECUTED_REASON and value.startswith(EVALUATOR_GAP_PREFIX):
        value = EVALUATOR_GAP_FAMILY
    return _BY_VALUE.get((vocabulary, value))


# ---------------------------------------------------------------------------------------------
# Composition — one failure event, facts from several vocabularies, one class
# ---------------------------------------------------------------------------------------------


@dataclass(frozen=True, kw_only=True)
class FailureEvent:
    """One failure the evidence records, with the facts composition reads.

    ``round_index`` is the correction round (``None`` for a failure outside the correction
    path); ``check_id`` names the check when the event is a check's. ``emission_signature`` is
    the #998 signature of an absent emission (``cap_exhausted`` / ``empty`` /
    ``unextractable``); ``not_executed_reason`` is set for a check that did not execute.
    """

    run_id: str
    task_id: str
    round_index: int | None = None
    check_id: str | None = None
    category: str | None = None
    locus: str | None = None
    emission_signature: str | None = None
    not_executed_reason: str | None = None

    def sort_key(self) -> tuple:
        return (
            self.run_id,
            -1 if self.round_index is None else self.round_index,
            self.task_id,
            self.check_id or "",
            self.category or "",
            self.locus or "",
            self.not_executed_reason or "",
        )


def compose(event: FailureEvent) -> AttributionClass | None:
    """The class one failure event shows, by the declared precedence (SIP-0108 §4.2).

    Returns ``None`` only for a declared non-failure (a configured non-execution). An event the
    rules cannot place is :attr:`AttributionClass.UNATTRIBUTED`, never a guess.
    """
    category = event.category
    # 1. Environment first — whatever the locus says.
    if category in (
        FailureEvidenceCategory.SANDBOX_PREEXEC_FAILURE,
        FailureEvidenceCategory.VERIFICATION_INFRA_FAILURE,
    ):
        return AttributionClass.ENVIRONMENT_OR_INFRASTRUCTURE_FAILURE
    # 2. Nothing to classify.
    if category == FailureEvidenceCategory.EVIDENCE_UNAVAILABLE:
        return AttributionClass.UNATTRIBUTED
    # 3. An absent emission: the completion cap decides.
    if category == FailureEvidenceCategory.EMISSION_ABSENT:
        if event.emission_signature == SIGNATURE_CAP_EXHAUSTED:
            return AttributionClass.BUDGET_EXHAUSTION
        return AttributionClass.PRODUCER_OUTPUT_FAILURE
    # 4. Lost content.
    if category == FailureEvidenceCategory.EXTRACTION_LOSS:
        return AttributionClass.HANDOFF_OR_CONVERGENCE_FAILURE
    # 5. An executed failure composes with its locus.
    if category in (FailureEvidenceCategory.EXECUTED_AND_FAILED, FailureEvidenceCategory.APP_ERROR):
        if event.locus == FailureLocus.OWN_ARTIFACT:
            return AttributionClass.VERIFICATION_ARTIFACT_FAILURE
        if event.locus == FailureLocus.SUBJECT:
            return AttributionClass.PRODUCER_OUTPUT_FAILURE
        return AttributionClass.UNATTRIBUTED
    # A check that did not execute is disposed of by its reason.
    if event.not_executed_reason is not None:
        declared = disposition_for(Vocabulary.NOT_EXECUTED_REASON, event.not_executed_reason)
        if declared is None:
            return AttributionClass.UNATTRIBUTED
        if declared.kind == DispositionKind.NON_FAILURE:
            return None
        return declared.attribution
    return AttributionClass.UNATTRIBUTED


# ---------------------------------------------------------------------------------------------
# Primary and contributing — the terminal evidence of the final state transition
# ---------------------------------------------------------------------------------------------


class TerminalKind(StrEnum):
    """The cycle's final state transition, read from the structured terminal decision."""

    PLAN_GATE_REFUSED = "plan_gate_refused"
    MANIFEST_GATE_REFUSED = "manifest_gate_refused"
    CORRECTION_TERMINATED = "correction_terminated"
    COMPLIANCE_BUDGET_EXCEEDED = "compliance_budget_exceeded"
    RUN_TIME_BUDGET_EXCEEDED = "run_time_budget_exceeded"
    COMPLETED = "completed"
    OTHER = "other"


@dataclass(frozen=True, kw_only=True)
class MovementEvent:
    """One round's movement class for one failed task (``classify_movement``)."""

    run_id: str
    task_id: str
    round_index: int
    movement: str


@dataclass(frozen=True, kw_only=True)
class TerminalEvidence:
    """What :func:`attribute` reads: the final state and the failures that led to it.

    ``failure_events`` holds, by kind: every correction round's failures; the failed required
    checks of a rejected completion; the failures up to an exceeded time budget; the refused
    emissions of an exceeded compliance budget. ``unverified`` holds a blocked completion's
    required unverified checks, each as an event carrying its ``not_executed_reason``.
    """

    kind: TerminalKind
    verdict: str | None = None
    refused_validators: tuple[str, ...] = ()
    failed_proofs: tuple[str, ...] = ()
    termination_reason: str | None = None
    failure_events: tuple[FailureEvent, ...] = ()
    unverified: tuple[FailureEvent, ...] = ()
    movements: tuple[MovementEvent, ...] = ()


@dataclass(frozen=True, kw_only=True)
class Contribution:
    """One contributing disposition, citing the fact it came from."""

    source: str
    run_id: str
    task_id: str
    round_index: int | None
    check_id: str | None
    value: str
    attribution: AttributionClass

    def sort_key(self) -> tuple:
        return (
            self.run_id,
            -1 if self.round_index is None else self.round_index,
            self.task_id,
            self.check_id or "",
            self.source,
            self.value,
            self.attribution,
        )


@dataclass(frozen=True, kw_only=True)
class Attribution:
    """One primary disposition and its ordered contributing dispositions (``None`` / empty for
    an accepted cycle)."""

    primary: AttributionClass | None
    contributing: tuple[Contribution, ...]
    registry_version: int = ATTRIBUTION_REGISTRY_VERSION


#: Verdicts, as ``RunVerdict`` spells them — the terminal table's two completed rows.
_VERDICT_ACCEPTED = "accepted"
_VERDICT_REJECTED = "rejected"
_VERDICT_BLOCKED = "blocked_unverified"


def _event_contribution(source: str, event: FailureEvent) -> Contribution | None:
    attribution = compose(event)
    if attribution is None:
        return None
    return Contribution(
        source=source,
        run_id=event.run_id,
        task_id=event.task_id,
        round_index=event.round_index,
        check_id=event.check_id,
        value=event.category or event.not_executed_reason or "",
        attribution=attribution,
    )


def _declared_contributions(
    vocabulary: Vocabulary, values: Iterable[str], *, run_id: str = "", task_id: str = ""
) -> list[Contribution]:
    out: list[Contribution] = []
    for value in values:
        declared = disposition_for(vocabulary, value)
        attribution = (
            declared.attribution if declared is not None else AttributionClass.UNATTRIBUTED
        )
        if declared is not None and declared.kind == DispositionKind.NON_FAILURE:
            continue
        out.append(
            Contribution(
                source=vocabulary,
                run_id=run_id,
                task_id=task_id,
                round_index=None,
                check_id=None,
                value=value,
                attribution=attribution or AttributionClass.UNATTRIBUTED,
            )
        )
    return out


def _movement_contributions(movements: Iterable[MovementEvent]) -> list[Contribution]:
    out: list[Contribution] = []
    for m in movements:
        declared = disposition_for(Vocabulary.CORRECTION_MOVEMENT, m.movement)
        if declared is not None and declared.kind == DispositionKind.NON_FAILURE:
            continue
        out.append(
            Contribution(
                source=Vocabulary.CORRECTION_MOVEMENT,
                run_id=m.run_id,
                task_id=m.task_id,
                round_index=m.round_index,
                check_id=None,
                value=m.movement,
                attribution=(declared.attribution if declared else None)
                or AttributionClass.UNATTRIBUTED,
            )
        )
    return out


def _single_class(contributions: Iterable[Contribution]) -> AttributionClass:
    """The one class every contribution shows, or ``unattributed`` — never an arbitrary pick."""
    classes = {c.attribution for c in contributions}
    return classes.pop() if len(classes) == 1 else AttributionClass.UNATTRIBUTED


def attribute(terminal: TerminalEvidence) -> Attribution:
    """The primary disposition — the terminal evidence of the final state transition — and
    everything earlier as contributing, ordered by run, round, task and check (SIP-0108 §4.2).
    """
    events = [
        c
        for e in terminal.failure_events
        if (c := _event_contribution("failure_event", e)) is not None
    ]
    kind = terminal.kind
    primary: AttributionClass | None
    contributing: list[Contribution]

    if kind in (TerminalKind.PLAN_GATE_REFUSED, TerminalKind.MANIFEST_GATE_REFUSED):
        contributing = _declared_contributions(
            Vocabulary.PLAN_VALIDATOR, terminal.refused_validators
        ) + _declared_contributions(Vocabulary.WINNABILITY_PROOF, terminal.failed_proofs)
        if terminal.refused_validators and terminal.failed_proofs:
            # One gate refused on validators AND proofs — both rows' evidence at once, and no
            # declared rule picks one, so the primary is not chosen (SIP-0108 §10c).
            primary = AttributionClass.UNATTRIBUTED
        elif kind == TerminalKind.PLAN_GATE_REFUSED:
            primary = AttributionClass.PLAN_GATE_FAILURE
        else:
            primary = AttributionClass.CRITERIA_OR_CONTRACT_FAILURE
    elif kind == TerminalKind.CORRECTION_TERMINATED:
        declared = disposition_for(
            Vocabulary.CORRECTION_TERMINATION_REASON, terminal.termination_reason or ""
        )
        primary = (
            declared.attribution
            if declared is not None and declared.primary_eligible and declared.attribution
            else AttributionClass.UNATTRIBUTED
        )
        contributing = events + _movement_contributions(terminal.movements)
    elif kind == TerminalKind.COMPLIANCE_BUDGET_EXCEEDED:
        primary = AttributionClass.WRITE_AUTHORITY_VIOLATION
        contributing = [
            Contribution(
                source="refused_emission",
                run_id=e.run_id,
                task_id=e.task_id,
                round_index=e.round_index,
                check_id=e.check_id,
                value=FailureClassification.CONTRACT_COMPLIANCE,
                attribution=AttributionClass.WRITE_AUTHORITY_VIOLATION,
            )
            for e in terminal.failure_events
        ]
    elif kind == TerminalKind.RUN_TIME_BUDGET_EXCEEDED:
        primary = AttributionClass.BUDGET_EXHAUSTION
        contributing = events
    elif kind == TerminalKind.COMPLETED and terminal.verdict == _VERDICT_ACCEPTED:
        return Attribution(primary=None, contributing=())
    elif kind == TerminalKind.COMPLETED and terminal.verdict == _VERDICT_REJECTED:
        contributing = events
        primary = _single_class(events)
    elif kind == TerminalKind.COMPLETED and terminal.verdict == _VERDICT_BLOCKED:
        contributing = [
            c
            for e in terminal.unverified
            if (c := _event_contribution("unverified_check", e)) is not None
        ]
        primary = _single_class(contributing)
    else:
        primary = AttributionClass.UNATTRIBUTED
        contributing = events

    return Attribution(
        primary=primary,
        contributing=tuple(sorted(contributing, key=Contribution.sort_key)),
    )
