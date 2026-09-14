"""SIP-0108 §4.1 (a) — the cycle assessment, a pure projection over the durable record.

Each test names what it catches: an unaskable indicator written as a zero, an observed value
citing nothing, an attribution chosen from evidence that does not support it, or an identity that
moves when nothing about the evidence did.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from squadops.cycles.cycle_assessment import (
    ASSESSMENT_VERSION,
    UNRECORDED_CHECK_LOCUS,
    UNRECORDED_PROOFS,
    UNRECORDED_ROUND_FAILURE_EVENTS,
    ArtifactRecord,
    AssessorIdentity,
    CycleEvidence,
    EvidenceRef,
    GateDecisionRecord,
    IndicatorState,
    RefKind,
    RejectionRecord,
    RunRecord,
    TerminationRecord,
    assess,
)
from squadops.cycles.failure_attribution import (
    ATTRIBUTION_REGISTRY_VERSION,
    AttributionClass,
    TerminalKind,
)
from squadops.cycles.llm_usage import RunUsage, UsageTotals
from squadops.cycles.run_loop_summary import MovementRecord, RefundedRound, RunLoopSummary
from squadops.cycles.run_loop_summary import RunTerminalDecision as Decision
from squadops.cycles.task_outcome import CorrectionTerminationReason
from squadops.cycles.verification_integrity import (
    CycleOutcome,
    NotExecutedReason,
    RunVerdict,
    UnverifiedCheck,
)

pytestmark = [pytest.mark.domain_orchestration]

T0 = datetime(2026, 9, 14, 12, 0, tzinfo=UTC)
ASSESSOR = AssessorIdentity(framework_version="1.7.5", git_sha="d1e52082")


def _run(run_id, number, workload, status="completed", seconds=600, gates=()):
    return RunRecord(
        run_id=run_id,
        run_number=number,
        workload_type=workload,
        status=status,
        started_at=T0,
        finished_at=T0 + timedelta(seconds=seconds) if seconds is not None else None,
        gate_decisions=tuple(gates),
    )


def _summary(calls=4, prompt=100, terminal=None, refunds=(), movements=(), unreported=()):
    return RunLoopSummary(
        run_id="",
        usage=RunUsage(
            by_task_type={"qa.test": UsageTotals(calls=calls, prompt_tokens=prompt)},
            tasks_reported=1,
            tasks_unreported=tuple(unreported),
        ),
        refunded_rounds=tuple(refunds),
        movements=tuple(movements),
        terminal=terminal,
    )


def _outcome(verdict=RunVerdict.ACCEPTED, failed=(), unverified=(), runs=2, criteria=(3, 3)):
    return CycleOutcome(
        verdict=verdict,
        verified=("tests_pass",),
        failed=tuple(failed),
        unverified=tuple(unverified),
        run_count=runs,
        criteria_verified=tuple(f"c{i}" for i in range(criteria[0])),
        criteria_total=tuple(f"c{i}" for i in range(criteria[1])),
    )


def _accepted_cycle() -> tuple[CycleOutcome, CycleEvidence]:
    evidence = CycleEvidence(
        cycle_id="cyc_1",
        runs=(_run("run_f1", 1, "framing"), _run("run_i1", 2, "implementation", seconds=1800)),
        verification_summary_runs=("run_f1", "run_i1"),
        loop_summaries={
            "run_f1": _summary(calls=3, prompt=50),
            "run_i1": _summary(
                calls=9,
                prompt=900,
                terminal=Decision(kind=TerminalKind.COMPLETED),
                refunds=(RefundedRound("t-qa", 0, "empty_repair_emission", ("empty",)),),
                movements=(MovementRecord("t-qa", 0, "new"),),
            ),
        },
        artifacts=(
            ArtifactRecord("art_dec", "run_i1", "document", "governance.correction_decision"),
            ArtifactRecord("art_src", "run_i1", "source", "development.develop"),
        ),
    )
    return _outcome(), evidence


class TestFourDimensions:
    def test_every_observed_indicator_cites_the_record_it_read(self):
        """Bug caught: a value with no reference — nothing a reader could resolve it against."""
        assessment = assess(*_accepted_cycle(), assessor=ASSESSOR)

        for group in (
            assessment.outcome,
            assessment.quality,
            assessment.coordination,
            assessment.efficiency,
        ):
            for ind in group:
                if ind.state == IndicatorState.OBSERVED:
                    assert ind.refs, ind.name
        assert assessment.indicator("verdict").value == "accepted"
        assert assessment.indicator("criteria_coverage").value == {"verified": 3, "total": 3}
        assert assessment.indicator("correction_rounds").value == 1
        assert assessment.indicator("correction_rounds").refs == (
            EvidenceRef(RefKind.ARTIFACT, "art_dec"),
        )
        assert assessment.indicator("wall_clock_seconds").value == 2400
        assert assessment.indicator("llm_calls").value == {
            "calls": 12,
            "failed_calls": 0,
            "tasks_unreported": [],
        }
        assert assessment.indicator("tokens_by_run").value["run_i1"]["prompt"] == 900
        assert assessment.indicator("refunded_rounds").refs == (
            EvidenceRef(RefKind.RUN_SUMMARY, "run_i1"),
        )
        assert assessment.indicator("verified_functional").state == IndicatorState.UNASKABLE
        assert (assessment.assessment_version, assessment.attribution_registry_version) == (
            ASSESSMENT_VERSION,
            ATTRIBUTION_REGISTRY_VERSION,
        )
        assert assessment.assessor == ASSESSOR

    def test_a_run_without_a_run_summary_makes_its_loop_facts_unaskable_never_zero(self):
        """Bug caught: a historical cycle — finalized before the run summary existed — reading
        zero tokens and zero refunds, which a comparison would take as the cheaper arm."""
        outcome, evidence = _accepted_cycle()
        historical = CycleEvidence(**{**evidence.__dict__, "loop_summaries": {}})

        assessment = assess(outcome, historical, assessor=ASSESSOR)

        for name in ("refunded_rounds", "correction_movements", "tokens_by_run", "llm_calls"):
            ind = assessment.indicator(name)
            assert ind.state == IndicatorState.UNASKABLE, name
            assert ind.value is None, name
            assert ind.reason == "no_run_summary: run_f1, run_i1", name
        # What the run rows and the vault hold still reads.
        assert assessment.indicator("correction_rounds").value == 1
        assert assessment.indicator("wall_clock_seconds").value == 2400

    @pytest.mark.parametrize(
        ("banked", "expected"),
        [
            (
                (
                    ArtifactRecord("a1", "run_i1", "document", "qa.test", "t-qa", "failed", 1),
                    ArtifactRecord("a2", "run_i1", "document", "qa.test", "t-qa", "failed", 1),
                    ArtifactRecord("a3", "run_i1", "document", "qa.test", "t-qa", "failed", 2),
                ),
                (IndicatorState.OBSERVED, 2),
            ),
            (
                (ArtifactRecord("a1", "run_i1", "document", "qa.test", "t-qa", "failed", None),),
                (IndicatorState.UNASKABLE, None),
            ),
            ((), (IndicatorState.ASKED_NONE, 0)),
        ],
        ids=["stamped", "pre-1.7.5 stamp", "none banked"],
    )
    def test_failed_emissions_count_attempts_by_stamp_or_are_unaskable(self, banked, expected):
        """Bug caught: two artifacts of one attempt counted as two emissions, or an unstamped
        bank read as a number (#1436)."""
        outcome, evidence = _accepted_cycle()
        evidence = CycleEvidence(**{**evidence.__dict__, "artifacts": banked})

        ind = assess(outcome, evidence, assessor=ASSESSOR).indicator("failed_emissions")

        assert (ind.state, ind.value) == expected

    def test_framing_rerolls_and_plan_defect_terminations_cite_their_runs_and_artifacts(self):
        outcome, evidence = _accepted_cycle()
        evidence = CycleEvidence(
            **{
                **evidence.__dict__,
                "runs": (
                    _run("run_f1", 1, "framing", status="cancelled"),
                    _run("run_f2", 2, "framing"),
                    _run("run_i1", 3, "implementation"),
                ),
                "loop_summaries": {},
                "terminations": (
                    TerminationRecord(
                        "term_1", "run_i1", CorrectionTerminationReason.PLAN_DEFECT, "t"
                    ),
                ),
            }
        )

        assessment = assess(outcome, evidence, assessor=ASSESSOR)

        assert assessment.indicator("framing_rerolls").value == 1
        assert assessment.indicator("framing_rerolls").refs == (EvidenceRef(RefKind.RUN, "run_f2"),)
        assert assessment.indicator("plan_defect_terminations").refs == (
            EvidenceRef(RefKind.ARTIFACT, "term_1"),
        )

    def test_a_cycle_with_no_verification_summary_reads_its_outcome_unaskable(self):
        """Bug caught: a cycle that never verified anything reading ``accepted`` with 0/0."""
        _, evidence = _accepted_cycle()
        evidence = CycleEvidence(**{**evidence.__dict__, "verification_summary_runs": ()})

        assessment = assess(_outcome(runs=0, criteria=(0, 0)), evidence, assessor=ASSESSOR)

        for ind in (*assessment.outcome, assessment.indicator("failed_checks")):
            assert ind.state == IndicatorState.UNASKABLE
        assert assessment.attribution.state == IndicatorState.UNASKABLE


def _failed_impl(decision, movements=()):
    evidence = CycleEvidence(
        cycle_id="cyc_1",
        runs=(_run("run_f1", 1, "framing"), _run("run_i1", 2, "implementation", status="failed")),
        verification_summary_runs=("run_f1", "run_i1"),
        loop_summaries={
            "run_f1": _summary(),
            "run_i1": _summary(terminal=decision, movements=movements),
        },
    )
    return _outcome(verdict=RunVerdict.BLOCKED_UNVERIFIED), evidence


def _gate_refused(record):
    gate = GateDecisionRecord("progress_plan_review", "rejected", "system:plan_validation")
    evidence = CycleEvidence(
        cycle_id="cyc_1",
        runs=(_run("run_f1", 1, "framing", gates=(gate,)),),
        verification_summary_runs=("run_f1",),
        rejection_records=(record,) if record else (),
    )
    return _outcome(runs=1), evidence


class TestAttribution:
    @pytest.mark.parametrize(
        ("classes", "proofs", "primary", "unrecorded"),
        [
            ({"validate_criteria_scope": 1}, {}, AttributionClass.PLAN_GATE_FAILURE, ()),
            ({}, {"lint": 2}, AttributionClass.CRITERIA_OR_CONTRACT_FAILURE, ()),
            ({"validate_criteria_scope": 1}, {"lint": 1}, AttributionClass.UNATTRIBUTED, ()),
            (
                {"validate_criteria_scope": 1},
                None,
                AttributionClass.PLAN_GATE_FAILURE,
                (UNRECORDED_PROOFS,),
            ),
            ({}, None, AttributionClass.UNATTRIBUTED, (UNRECORDED_PROOFS,)),
        ],
        ids=["validators", "proofs", "both", "pre-4.2 with validators", "pre-4.2 empty"],
    )
    def test_a_gate_refusal_reads_its_record_not_its_note(
        self, classes, proofs, primary, unrecorded
    ):
        """Bug caught: a refusal attributed from prose, or a pre-§4.2 record with nothing
        classified chosen as a plan-gate failure when it may have been the manifest."""
        record = RejectionRecord("art_rej", "run_f1", "progress_plan_review", classes, proofs)

        reading = assess(*_gate_refused(record), assessor=ASSESSOR).attribution

        assert reading.state == IndicatorState.OBSERVED
        assert reading.attribution.primary == primary
        assert reading.unrecorded == unrecorded
        assert EvidenceRef(RefKind.ARTIFACT, "art_rej") in reading.refs

    def test_a_gate_refusal_without_its_record_is_unaskable(self):
        reading = assess(*_gate_refused(None), assessor=ASSESSOR).attribution
        assert (reading.state, reading.reason) == (
            IndicatorState.UNASKABLE,
            "no_rejection_record: run_f1",
        )

    def test_an_exhausted_correction_budget_is_budget_exhaustion_and_names_what_is_unrecorded(self):
        """Bug caught: the primary read from ``failure_reason`` prose, or the missing per-round
        failure events silently treated as none."""
        decision = Decision(
            kind=TerminalKind.CORRECTION_TERMINATED,
            termination_reason=CorrectionTerminationReason.EXHAUSTED,
            task_id="t-qa",
        )
        outcome, evidence = _failed_impl(
            decision,
            movements=(MovementRecord("t-qa", 0, "new"), MovementRecord("t-qa", 1, "repeat")),
        )

        reading = assess(outcome, evidence, assessor=ASSESSOR).attribution

        assert reading.terminal_kind == TerminalKind.CORRECTION_TERMINATED
        assert reading.attribution.primary == AttributionClass.BUDGET_EXHAUSTION
        assert [c.value for c in reading.attribution.contributing] == ["repeat"]
        assert reading.unrecorded == (UNRECORDED_ROUND_FAILURE_EVENTS,)
        assert EvidenceRef(RefKind.RUN_SUMMARY, "run_i1") in reading.refs

    def test_a_failed_run_with_no_terminal_decision_is_unaskable(self):
        outcome, evidence = _failed_impl(None)
        reading = assess(outcome, evidence, assessor=ASSESSOR).attribution
        assert (reading.state, reading.reason) == (
            IndicatorState.UNASKABLE,
            "no_terminal_decision: run_i1",
        )

    def test_a_cycle_still_running_has_no_attribution_yet(self):
        outcome, evidence = _accepted_cycle()
        evidence = CycleEvidence(
            **{
                **evidence.__dict__,
                "runs": (_run("run_i1", 1, "implementation", status="running", seconds=None),),
            }
        )
        reading = assess(outcome, evidence, assessor=ASSESSOR).attribution
        assert (reading.state, reading.reason) == (
            IndicatorState.UNASKABLE,
            "cycle_not_terminal: running",
        )

    @pytest.mark.parametrize(
        ("outcome", "primary", "unrecorded"),
        [
            (_outcome(), None, ()),
            (
                _outcome(verdict=RunVerdict.REJECTED, failed=("tests_pass",)),
                AttributionClass.UNATTRIBUTED,
                (UNRECORDED_CHECK_LOCUS,),
            ),
            (
                _outcome(
                    verdict=RunVerdict.BLOCKED_UNVERIFIED,
                    unverified=(
                        UnverifiedCheck("tests_pass", NotExecutedReason.MISSING_TOOLING, True),
                    ),
                ),
                AttributionClass.ENVIRONMENT_OR_INFRASTRUCTURE_FAILURE,
                (),
            ),
        ],
        ids=["accepted", "rejected", "blocked"],
    )
    def test_a_completed_cycle_is_read_from_its_verdict(self, outcome, primary, unrecorded):
        """Bug caught: a rejected completion given a class its evidence cannot support — the
        failed check's locus is not stored, so it reads unattributed and says why."""
        _, evidence = _accepted_cycle()

        reading = assess(outcome, evidence, assessor=ASSESSOR).attribution

        assert reading.attribution.primary == primary
        assert reading.unrecorded == unrecorded


class TestIdentity:
    def test_the_same_evidence_in_any_order_has_one_identity_and_a_change_moves_it(self):
        """Bug caught: an identity keyed on the order the adapter happened to read rows in —
        a cache that never hits — or one that ignores a changed value, which serves a stale
        assessment for new evidence."""
        outcome, evidence = _accepted_cycle()
        reordered = CycleEvidence(
            **{
                **evidence.__dict__,
                "runs": tuple(reversed(evidence.runs)),
                "artifacts": tuple(reversed(evidence.artifacts)),
                "loop_summaries": dict(reversed(list(evidence.loop_summaries.items()))),
            }
        )
        changed = CycleEvidence(
            **{
                **evidence.__dict__,
                "runs": (evidence.runs[0], _run("run_i1", 2, "implementation", seconds=1801)),
            }
        )

        base = assess(outcome, evidence, assessor=ASSESSOR).evidence_identity
        assert assess(outcome, reordered, assessor=ASSESSOR).evidence_identity == base
        assert assess(outcome, changed, assessor=ASSESSOR).evidence_identity != base
        other_assessor = AssessorIdentity("1.8.0", None)
        assert assess(outcome, evidence, assessor=other_assessor).evidence_identity == base
