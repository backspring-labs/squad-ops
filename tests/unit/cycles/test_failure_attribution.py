"""SIP-0108 §4.2 — the one failure-attribution registry.

Each test names the defect it catches: a source value with no disposition (or two), an
attribution literal or mapping living outside the registry, a composition rule applied out of
order, a primary chosen arbitrarily, or an attribution that depends on the order the evidence
arrived in.
"""

from __future__ import annotations

import itertools
import re
from pathlib import Path

import pytest

from squadops.cycles import correction_signature, failure_attribution, manifest_gates
from squadops.cycles.failure_attribution import (
    DISPOSITIONS,
    EVALUATOR_GAP_FAMILY,
    AttributionClass,
    Disposition,
    DispositionKind,
    FailureEvent,
    MovementEvent,
    TerminalEvidence,
    TerminalKind,
    Vocabulary,
    attribute,
    compose,
    disposition_for,
)
from squadops.cycles.failure_evidence import FailureEvidenceCategory, FailureLocus
from squadops.cycles.implementation_plan import ImplementationPlan
from squadops.cycles.task_outcome import CorrectionTerminationReason, FailureClassification
from squadops.cycles.verification_integrity import UNSPECIFIED_REASON, NotExecutedReason

pytestmark = [pytest.mark.domain_orchestration]

_REPO = Path(__file__).resolve().parents[3]


def _constants(namespace, prefix: str = "") -> set[str]:
    return {
        value
        for name, value in vars(namespace).items()
        if name.isupper() and name.startswith(prefix) and isinstance(value, str)
    }


#: Each vocabulary read from the module where it is authoritative — never restated here.
_SOURCES = {
    Vocabulary.FAILURE_EVIDENCE_CATEGORY: lambda: _constants(FailureEvidenceCategory),
    Vocabulary.FAILURE_LOCUS: lambda: _constants(FailureLocus),
    Vocabulary.PLAN_VALIDATOR: lambda: {
        n for n in dir(ImplementationPlan) if n.startswith("validate_")
    },
    Vocabulary.WINNABILITY_PROOF: lambda: _constants(manifest_gates, "PROOF_"),
    Vocabulary.CORRECTION_MOVEMENT: lambda: _constants(correction_signature, "MOVEMENT_"),
    Vocabulary.CORRECTION_TERMINATION_REASON: lambda: _constants(CorrectionTerminationReason),
    Vocabulary.FAILURE_CLASSIFICATION: lambda: _constants(FailureClassification),
    Vocabulary.NOT_EXECUTED_REASON: lambda: (
        _constants(NotExecutedReason) | {EVALUATOR_GAP_FAMILY, UNSPECIFIED_REASON}
    ),
}


class TestEverySourceValueHasExactlyOneDisposition:
    @pytest.mark.parametrize("vocabulary", list(Vocabulary))
    def test_the_declared_values_are_the_source_values(self, vocabulary):
        """Bug caught: a new plan validator, proof, movement or reason lands in its own
        module and silently reads ``unattributed`` forever — or a value is removed and the
        registry keeps a dead entry."""
        declared = [d.value for d in DISPOSITIONS if d.vocabulary == vocabulary]
        assert len(declared) == len(set(declared)), f"{vocabulary}: a value declared twice"
        assert set(declared) == _SOURCES[vocabulary]()

    def test_a_value_declared_twice_refuses_to_build(self):
        twice = (
            Disposition(
                vocabulary=Vocabulary.CORRECTION_MOVEMENT,
                value="repeat",
                kind=DispositionKind.NON_FAILURE,
                attribution=None,
                primary_eligible=False,
            ),
        ) * 2
        with pytest.raises(ValueError, match="declared twice"):
            failure_attribution._index(twice)

    @pytest.mark.parametrize(
        ("kind", "attribution"),
        [
            (DispositionKind.ATTRIBUTION, None),
            (DispositionKind.NON_FAILURE, AttributionClass.UNATTRIBUTED),
        ],
    )
    def test_only_an_attribution_disposition_names_a_class(self, kind, attribution):
        with pytest.raises(ValueError, match="exactly one class"):
            Disposition(
                vocabulary=Vocabulary.CORRECTION_MOVEMENT,
                value="x",
                kind=kind,
                attribution=attribution,
                primary_eligible=False,
            )

    def test_the_reserved_class_has_no_manufactured_mapping(self):
        """``input_contract_failure`` is reserved: no reachable evidence establishes it, and a
        mapping invented to use it would attribute a cause the evidence does not show."""
        assert not [
            d for d in DISPOSITIONS if d.attribution == AttributionClass.INPUT_CONTRACT_FAILURE
        ]

    def test_an_evaluator_gap_resolves_to_its_family(self):
        declared = disposition_for(
            Vocabulary.NOT_EXECUTED_REASON, "evaluator_gap:unsupported_file_extension"
        )
        assert declared is not None and declared.attribution == AttributionClass.UNATTRIBUTED
        assert disposition_for(Vocabulary.NOT_EXECUTED_REASON, "never_heard_of_it") is None


def test_no_attribution_class_literal_lives_outside_the_registry():
    """Bug caught: a second mapping growing beside the registry — the "no source-to-attribution
    mapping outside it" rule, held at the one place a mapping would have to spell a class."""
    literals = {c.value for c in AttributionClass}
    #: A different vocabulary that shares a word: who DECIDED a gate when auth is off.
    allowed = {("src/squadops/cycles/gate_attribution.py", "unattributed")}
    registry = Path("src/squadops/cycles/failure_attribution.py")
    pattern = re.compile(r"""["']([a-z_]+)["']""")
    found = []
    for root in ("src", "adapters", "scripts"):
        for path in (_REPO / root).rglob("*.py"):
            rel = path.relative_to(_REPO)
            if rel == registry:
                continue
            for match in pattern.finditer(path.read_text(encoding="utf-8")):
                if match.group(1) in literals and (str(rel), match.group(1)) not in allowed:
                    found.append(f"{rel}: {match.group(1)}")
    assert found == []


_E = FailureEvidenceCategory


class TestCompositionAppliesTheDeclaredPrecedence:
    @pytest.mark.parametrize(
        ("event", "expected"),
        [
            # 1. environment first, whatever the locus says
            (
                dict(category=_E.SANDBOX_PREEXEC_FAILURE, locus=FailureLocus.OWN_ARTIFACT),
                AttributionClass.ENVIRONMENT_OR_INFRASTRUCTURE_FAILURE,
            ),
            (
                dict(category=_E.VERIFICATION_INFRA_FAILURE, locus=FailureLocus.SUBJECT),
                AttributionClass.ENVIRONMENT_OR_INFRASTRUCTURE_FAILURE,
            ),
            # 2. nothing to classify
            (dict(category=_E.EVIDENCE_UNAVAILABLE), AttributionClass.UNATTRIBUTED),
            # 3. an absent emission: the completion cap decides
            (
                dict(category=_E.EMISSION_ABSENT, emission_signature="cap_exhausted"),
                AttributionClass.BUDGET_EXHAUSTION,
            ),
            (
                dict(category=_E.EMISSION_ABSENT, emission_signature="unextractable"),
                AttributionClass.PRODUCER_OUTPUT_FAILURE,
            ),
            # 4. lost content
            (
                dict(category=_E.EXTRACTION_LOSS, locus=FailureLocus.SUBJECT),
                AttributionClass.HANDOFF_OR_CONVERGENCE_FAILURE,
            ),
            # 5. an executed failure composes with its locus
            (
                dict(category=_E.EXECUTED_AND_FAILED, locus=FailureLocus.OWN_ARTIFACT),
                AttributionClass.VERIFICATION_ARTIFACT_FAILURE,
            ),
            (
                dict(category=_E.APP_ERROR, locus=FailureLocus.SUBJECT),
                AttributionClass.PRODUCER_OUTPUT_FAILURE,
            ),
            (
                dict(category=_E.EXECUTED_AND_FAILED, locus=FailureLocus.UNKNOWN),
                AttributionClass.UNATTRIBUTED,
            ),
            (dict(category=_E.EXECUTED_AND_FAILED), AttributionClass.UNATTRIBUTED),
            # a check that did not execute, by its reason
            (
                dict(not_executed_reason=NotExecutedReason.MISSING_TOOLING),
                AttributionClass.ENVIRONMENT_OR_INFRASTRUCTURE_FAILURE,
            ),
            (
                dict(not_executed_reason=NotExecutedReason.SUBJECT_MISSING),
                AttributionClass.PRODUCER_OUTPUT_FAILURE,
            ),
            (
                dict(not_executed_reason="evaluator_gap:unsupported_file_extension"),
                AttributionClass.UNATTRIBUTED,
            ),
            (dict(not_executed_reason="a_reason_nobody_declared"), AttributionClass.UNATTRIBUTED),
            (dict(), AttributionClass.UNATTRIBUTED),
        ],
    )
    def test_the_first_matching_rule_decides(self, event, expected):
        """Bug caught: rules applied out of order — an infrastructure failure read through its
        locus as the product's fault, or a locus attributed with no executed failure."""
        assert compose(FailureEvent(run_id="r", task_id="t", **event)) == expected

    def test_a_configured_non_execution_is_not_a_failure(self):
        event = FailureEvent(
            run_id="r", task_id="t", not_executed_reason=NotExecutedReason.CONFIG_DISABLED
        )
        assert compose(event) is None


def _event(task: str, round_index: int | None, category: str, locus: str | None = None, check=None):
    return FailureEvent(
        run_id="run_1",
        task_id=task,
        round_index=round_index,
        check_id=check,
        category=category,
        locus=locus,
    )


class TestThePrimaryIsTheTerminalEvidence:
    def test_an_accepted_cycle_carries_neither(self):
        result = attribute(TerminalEvidence(kind=TerminalKind.COMPLETED, verdict="accepted"))
        assert (result.primary, result.contributing) == (None, ())

    @pytest.mark.parametrize(
        ("terminal", "primary", "contributing"),
        [
            (
                TerminalEvidence(
                    kind=TerminalKind.PLAN_GATE_REFUSED,
                    refused_validators=("validate_check_applicability", "validate_builder_floor"),
                ),
                AttributionClass.PLAN_GATE_FAILURE,
                [AttributionClass.PLAN_GATE_FAILURE] * 2,
            ),
            (
                TerminalEvidence(
                    kind=TerminalKind.MANIFEST_GATE_REFUSED,
                    failed_proofs=(manifest_gates.PROOF_EXPANDS,),
                ),
                AttributionClass.CRITERIA_OR_CONTRACT_FAILURE,
                [AttributionClass.CRITERIA_OR_CONTRACT_FAILURE],
            ),
            (
                TerminalEvidence(
                    kind=TerminalKind.CORRECTION_TERMINATED,
                    termination_reason=CorrectionTerminationReason.PLAN_DEFECT,
                    failure_events=(
                        _event("qa", 0, _E.EXECUTED_AND_FAILED, FailureLocus.SUBJECT),
                        _event("qa", 1, _E.EXECUTED_AND_FAILED, FailureLocus.OWN_ARTIFACT),
                    ),
                    movements=(
                        MovementEvent(
                            run_id="run_1", task_id="qa", round_index=1, movement="repeat"
                        ),
                        MovementEvent(run_id="run_1", task_id="qa", round_index=0, movement="new"),
                    ),
                ),
                AttributionClass.HANDOFF_OR_CONVERGENCE_FAILURE,
                [
                    AttributionClass.PRODUCER_OUTPUT_FAILURE,
                    AttributionClass.HANDOFF_OR_CONVERGENCE_FAILURE,
                    AttributionClass.VERIFICATION_ARTIFACT_FAILURE,
                ],
            ),
            (
                TerminalEvidence(
                    kind=TerminalKind.CORRECTION_TERMINATED,
                    termination_reason=CorrectionTerminationReason.EXHAUSTED,
                ),
                AttributionClass.BUDGET_EXHAUSTION,
                [],
            ),
            (
                TerminalEvidence(
                    kind=TerminalKind.CORRECTION_TERMINATED,
                    termination_reason=CorrectionTerminationReason.CONVERGED,
                ),
                AttributionClass.UNATTRIBUTED,
                [],
            ),
            (
                TerminalEvidence(
                    kind=TerminalKind.COMPLIANCE_BUDGET_EXCEEDED,
                    failure_events=(_event("dev", None, _E.EXECUTED_AND_FAILED),),
                ),
                AttributionClass.WRITE_AUTHORITY_VIOLATION,
                [AttributionClass.WRITE_AUTHORITY_VIOLATION],
            ),
            (
                TerminalEvidence(
                    kind=TerminalKind.RUN_TIME_BUDGET_EXCEEDED,
                    failure_events=(_event("dev", None, _E.EMISSION_ABSENT),),
                ),
                AttributionClass.BUDGET_EXHAUSTION,
                [AttributionClass.PRODUCER_OUTPUT_FAILURE],
            ),
            (
                TerminalEvidence(
                    kind=TerminalKind.COMPLETED,
                    verdict="rejected",
                    failure_events=(
                        _event("qa", None, _E.EXECUTED_AND_FAILED, FailureLocus.OWN_ARTIFACT, "a"),
                        _event("qa", None, _E.EXECUTED_AND_FAILED, FailureLocus.OWN_ARTIFACT, "b"),
                    ),
                ),
                AttributionClass.VERIFICATION_ARTIFACT_FAILURE,
                [AttributionClass.VERIFICATION_ARTIFACT_FAILURE] * 2,
            ),
            (
                TerminalEvidence(kind=TerminalKind.OTHER),
                AttributionClass.UNATTRIBUTED,
                [],
            ),
        ],
    )
    def test_each_final_state_reads_its_row(self, terminal, primary, contributing):
        result = attribute(terminal)
        assert result.primary == primary
        assert [c.attribution for c in result.contributing] == contributing

    def test_a_rejection_whose_failures_disagree_is_unattributed_not_picked(self):
        """Bug caught: a primary chosen by whichever failed check came first — an arbitrary
        pick Campaign would then act on."""
        result = attribute(
            TerminalEvidence(
                kind=TerminalKind.COMPLETED,
                verdict="rejected",
                failure_events=(
                    _event("qa", None, _E.EXECUTED_AND_FAILED, FailureLocus.OWN_ARTIFACT, "a"),
                    _event("dev", None, _E.EXECUTED_AND_FAILED, FailureLocus.SUBJECT, "b"),
                ),
            )
        )
        assert result.primary == AttributionClass.UNATTRIBUTED
        assert len(result.contributing) == 2

    def test_a_blocked_cycle_reads_its_unverified_reasons_and_ignores_configured_ones(self):
        def unverified(check, reason):
            return FailureEvent(
                run_id="run_1", task_id="qa", check_id=check, not_executed_reason=reason
            )

        result = attribute(
            TerminalEvidence(
                kind=TerminalKind.COMPLETED,
                verdict="blocked_unverified",
                unverified=(
                    unverified("frontend_build", NotExecutedReason.MISSING_TOOLING),
                    unverified("tests_pass", NotExecutedReason.TIMEOUT_BEFORE_EXECUTION),
                    unverified("lint", NotExecutedReason.CONFIG_DISABLED),
                ),
            )
        )
        assert result.primary == AttributionClass.ENVIRONMENT_OR_INFRASTRUCTURE_FAILURE
        assert [c.check_id for c in result.contributing] == ["frontend_build", "tests_pass"]


def test_the_same_evidence_in_any_order_attributes_the_same():
    """SIP-0108 §5 criterion 4. Bug caught: contributing order, or the primary, following the
    order a store happened to return rows in — two readings of one cycle that disagree."""
    events = (
        _event("qa", 1, _E.EXECUTED_AND_FAILED, FailureLocus.OWN_ARTIFACT, "suite"),
        _event("dev", 0, _E.EMISSION_ABSENT),
        _event("qa", 0, _E.EXECUTED_AND_FAILED, FailureLocus.SUBJECT, "probe"),
        _event("builder", 2, _E.EXTRACTION_LOSS),
    )
    movements = (
        MovementEvent(run_id="run_1", task_id="qa", round_index=1, movement="shifted"),
        MovementEvent(run_id="run_1", task_id="qa", round_index=2, movement="expansion"),
        MovementEvent(run_id="run_1", task_id="dev", round_index=1, movement="progress"),
    )
    readings = {
        attribute(
            TerminalEvidence(
                kind=TerminalKind.CORRECTION_TERMINATED,
                termination_reason=CorrectionTerminationReason.PLAN_DEFECT,
                failure_events=e,
                movements=m,
            )
        )
        for e in itertools.permutations(events)
        for m in itertools.permutations(movements)
    }
    assert len(readings) == 1
