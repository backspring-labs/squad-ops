"""The continuation decision (SIP-0109 §10, §9.5; #1800).

The assessments are the real projection's (``assess``) over a one-run cycle, so the decision reads
the verdict and attribution exactly as the completion boundary will hand them over.
"""

from __future__ import annotations

import dataclasses
from datetime import UTC, datetime

import pytest

from squadops.campaigns.continuation import (
    CampaignCounters,
    CampaignLimit,
    ContinuationDecision,
    CycleEnding,
    EndedCycle,
    Guard,
    PendingAction,
    TerminalCause,
    campaign_continuation_decision,
)
from squadops.campaigns.models import CampaignOutcome, CampaignState, CycleKind
from squadops.cycles.cycle_assessment import (
    AssessorIdentity,
    AttributionReading,
    CycleEvidence,
    IndicatorState,
    RunRecord,
    assess,
)
from squadops.cycles.failure_attribution import Attribution, AttributionClass
from squadops.cycles.verification_integrity import CycleOutcome, RunVerdict
from tests.unit.campaigns.builders import campaign

CYCLE = "cyc_000000000001"
T0 = datetime(2026, 10, 2, 12, 0, tzinfo=UTC)

#: The builders' policy: 6 cycles, 1 repair and 1 retry per increment, 2 rejected proposals in a
#: row, 2 unaccepted increments, 12 h, 2M tokens.
CAMPAIGN = campaign(state=CampaignState.EVALUATING)


def assessment(verdict: RunVerdict | None, *, environment: bool = False):
    """The real projection over one implementation run. ``None`` is a run that failed before any
    verification summary: the verdict is unaskable."""
    run = RunRecord(
        run_id="run_1",
        run_number=1,
        workload_type="implementation",
        status="failed" if verdict is None else "completed",
        started_at=T0,
        finished_at=T0,
    )
    evidence = CycleEvidence(
        cycle_id=CYCLE,
        runs=(run,),
        verification_summary_runs=() if verdict is None else ("run_1",),
    )
    outcome = CycleOutcome(
        verdict=verdict or RunVerdict.REJECTED,
        verified=(),
        failed=("tests_pass",) if verdict is RunVerdict.REJECTED else (),
        unverified=(),
        run_count=1,
        criteria_verified=(),
        criteria_total=(),
    )
    latest = assess(outcome, evidence, assessor=AssessorIdentity("2.0.0", None))
    if environment:
        # Set directly, for the decision's own precedence. A completed cycle does not reach it (a
        # rejected completion's failed checks read unattributed); a failed run does, through its
        # terminal decision (#1824, test_retry_on_infrastructure.py).
        latest = dataclasses.replace(
            latest,
            attribution=AttributionReading(
                IndicatorState.OBSERVED,
                Attribution(
                    primary=AttributionClass.ENVIRONMENT_OR_INFRASTRUCTURE_FAILURE, contributing=()
                ),
            ),
        )
    return latest


def counters(**overrides) -> CampaignCounters:
    values = dict(
        cycles=2,
        elapsed_s=3600,
        tokens=100_000,
        repair_cycles=0,
        retry_cycles=0,
        rejected_proposals_in_row=0,
        failed_proposals_in_row=0,
        unaccepted_increments=0,
        objective_met=False,
    )
    values.update(overrides)
    return CampaignCounters(**values)


def decide(
    verdict: RunVerdict | None,
    *,
    kind: CycleKind = CycleKind.INCREMENT,
    ending: CycleEnding = CycleEnding.ASSESSED,
    environment: bool = False,
    the_campaign=CAMPAIGN,
    **count_overrides,
) -> ContinuationDecision:
    return campaign_continuation_decision(
        the_campaign,
        counters(**count_overrides),
        EndedCycle(CYCLE, kind, ending),
        assessment(verdict, environment=environment),
    )


def shape(decision: ContinuationDecision) -> tuple:
    return (decision.row, decision.outcome or decision.action, decision.guard, decision.paused_by)


_ACC, _REJ, _BLK = RunVerdict.ACCEPTED, RunVerdict.REJECTED, RunVerdict.BLOCKED_UNVERIFIED
_ABORTED = campaign(state=CampaignState.COMPLETED, outcome=CampaignOutcome.ABORTED)
_GO = Guard.PROCEED


@pytest.mark.parametrize(
    ("verdict", "kwargs", "expected"),
    [
        (_ACC, dict(the_campaign=_ABORTED, objective_met=True), (1, CampaignOutcome.ABORTED)),
        (_BLK, dict(kind=CycleKind.CALIBRATION), (2, CampaignOutcome.FAILURE)),
        (_ACC, dict(objective_met=True), (3, CampaignOutcome.SUCCESS)),
        (_REJ, dict(cycles=6), (4, CampaignOutcome.EXHAUSTED)),
        (
            None,
            dict(ending=CycleEnding.PROPOSAL_FAILED, unaccepted_increments=2),
            (4, CampaignOutcome.FAILURE),
        ),
        (_ACC, dict(kind=CycleKind.CALIBRATION), (5, PendingAction.PROPOSE, _GO)),
        (None, dict(ending=CycleEnding.REJECTED_AT_GATE), (6, PendingAction.PROPOSE, _GO)),
        (None, dict(ending=CycleEnding.PROPOSAL_FAILED), (6, PendingAction.PROPOSE, _GO)),
        (_ACC, {}, (7, PendingAction.PROPOSE, _GO)),
        (_BLK, {}, (8, PendingAction.REPAIR, _GO)),
        (_BLK, dict(repair_cycles=1), (9, PendingAction.ESCALATE, None)),
        (_REJ, dict(environment=True), (10, PendingAction.RETRY, _GO)),
        (_REJ, dict(environment=True, retry_cycles=1), (11, PendingAction.ESCALATE, None)),
        # §24bh: a run the box refused verified nothing, so it reads blocked_unverified.
        (_BLK, dict(environment=True), (10, PendingAction.RETRY, _GO)),
        (_BLK, dict(environment=True, retry_cycles=1), (11, PendingAction.ESCALATE, None)),
        (_REJ, {}, (12, PendingAction.REPAIR, _GO)),
        (_REJ, dict(repair_cycles=1), (13, PendingAction.ABANDON_AND_PROPOSE, _GO)),
        (None, {}, (14, PendingAction.ESCALATE, None)),
        # §24bj: a parked increment, repair or retry is abandoned, counting as unaccepted; asked
        # before row 6, which would otherwise propose without counting it.
        (None, dict(ending=CycleEnding.PARKED), (15, PendingAction.ABANDON_AND_PROPOSE, _GO)),
        (
            None,
            dict(ending=CycleEnding.PARKED, kind=CycleKind.REPAIR),
            (15, PendingAction.ABANDON_AND_PROPOSE, _GO),
        ),
        # A parked calibration has nothing to build on: row 2 ends the campaign.
        (
            None,
            dict(ending=CycleEnding.PARKED, kind=CycleKind.CALIBRATION),
            (2, CampaignOutcome.FAILURE),
        ),
        # §24cb (#2704): a cycle stopped at its plan gate built nothing, whatever its framing
        # summary reads (here ``accepted``). An increment or repair is abandoned, counted, on row
        # 18, asked before row 6; a calibration ends on row 2.
        (
            _ACC,
            dict(ending=CycleEnding.STOPPED_AT_PLAN_GATE),
            (18, PendingAction.ABANDON_AND_PROPOSE, _GO),
        ),
        (
            _ACC,
            dict(ending=CycleEnding.STOPPED_AT_PLAN_GATE, kind=CycleKind.REPAIR),
            (18, PendingAction.ABANDON_AND_PROPOSE, _GO),
        ),
        (
            _ACC,
            dict(ending=CycleEnding.STOPPED_AT_PLAN_GATE, kind=CycleKind.CALIBRATION),
            (2, CampaignOutcome.FAILURE),
        ),
        # A run of parks ends at the no-progress rule, the park that reaches the limit (2) counted
        # at its own decision, as a rejection's abandonment is (#2294): one prior park and this one.
        (
            None,
            dict(ending=CycleEnding.PARKED, unaccepted_increments=1),
            (4, CampaignOutcome.FAILURE),
        ),
        (
            None,
            dict(ending=CycleEnding.PARKED, kind=CycleKind.RETRY, unaccepted_increments=1),
            (4, CampaignOutcome.FAILURE),
        ),
    ],
)
def test_each_row_is_reached_by_a_crafted_input(verdict, kwargs, expected):
    """§19 criterion 12. Bug caught: a row shadowed by an earlier predicate, or an action under
    the wrong guard — a repair launched where the owner should have been asked."""
    expected = expected + (None,) * (4 - len(expected))
    assert shape(decide(verdict, **kwargs)) == expected


@pytest.mark.parametrize(
    ("verdict", "kwargs", "expected"),
    [
        # Success first: the cycle that meets the objective also exhausts the cycle count.
        (_ACC, dict(objective_met=True, cycles=6), (3, CampaignOutcome.SUCCESS, None, None)),
        # blocked_unverified never stops in success, whatever the measurement says.
        (_BLK, dict(objective_met=True), (8, PendingAction.REPAIR, _GO, None)),
        # A calibration cycle carries no increment, so it cannot meet the objective.
        (
            _ACC,
            dict(kind=CycleKind.CALIBRATION, objective_met=True),
            (5, PendingAction.PROPOSE, _GO, None),
        ),
        # Escalation wins over a simultaneous pausing limit: one ruling, never a held escalation.
        (_BLK, dict(repair_cycles=1, elapsed_s=12 * 3600), (9, PendingAction.ESCALATE, None, None)),
        # A pausing limit holds a launch.
        (
            _ACC,
            dict(tokens=2_000_000),
            (7, PendingAction.PROPOSE, Guard.PAUSED, CampaignLimit.BUDGET),
        ),
        (
            None,
            dict(ending=CycleEnding.REJECTED_AT_GATE, rejected_proposals_in_row=2),
            (6, PendingAction.PROPOSE, Guard.PAUSED, CampaignLimit.REJECTED_PROPOSALS_IN_ROW),
        ),
        # §24bn (#2231): a failed proposal is retried by the next proposal cycle while the
        # policy's retries (1 here) remain; the failure past them holds that launch.
        (
            None,
            dict(ending=CycleEnding.PROPOSAL_FAILED, failed_proposals_in_row=1),
            (6, PendingAction.PROPOSE, _GO, None),
        ),
        (
            None,
            dict(ending=CycleEnding.PROPOSAL_FAILED, failed_proposals_in_row=2),
            (6, PendingAction.PROPOSE, Guard.PAUSED, CampaignLimit.FAILED_PROPOSALS_IN_ROW),
        ),
        # The cycle that reaches the no-progress limit by its own abandonment stops the campaign,
        # rather than launching one more proposal first.
        (
            _REJ,
            dict(repair_cycles=1, unaccepted_increments=1),
            (4, CampaignOutcome.FAILURE, None, None),
        ),
    ],
    ids=[
        "success-first",
        "blocked-never-success",
        "calibration",
        "escalate-over-pause",
        "budget-pauses",
        "rejections-pause",
        "a-failed-proposal-is-retried",
        "failures-past-the-retries-pause",
        "abandonment-counts",
    ],
)
def test_the_precedence_is_as_written(verdict, kwargs, expected):
    assert shape(decide(verdict, **kwargs)) == expected


def test_the_no_progress_stop_names_its_limit():
    decision = decide(_REJ, repair_cycles=1, unaccepted_increments=1)
    assert (decision.cause, decision.terminal) == (TerminalCause.NO_PROGRESS, True)


def test_an_assessment_of_another_cycle_is_refused():
    """Bug caught: the decision keyed by one cycle and computed from another's assessment."""
    with pytest.raises(ValueError, match="the assessment is of"):
        campaign_continuation_decision(
            CAMPAIGN,
            counters(),
            EndedCycle("cyc_other", CycleKind.INCREMENT, CycleEnding.ASSESSED),
            assessment(_ACC),
        )


@pytest.mark.parametrize(
    "kwargs",
    [
        dict(row=3, outcome=CampaignOutcome.SUCCESS, action=PendingAction.PROPOSE),
        dict(row=9, action=PendingAction.ESCALATE, guard=Guard.PROCEED),
        dict(row=7, action=PendingAction.PROPOSE),
        dict(row=7, action=PendingAction.PROPOSE, guard=Guard.PAUSED),
    ],
    ids=["both", "guarded-escalation", "unguarded-launch", "pause-without-limit"],
)
def test_a_malformed_decision_cannot_be_constructed(kwargs):
    with pytest.raises(ValueError):
        ContinuationDecision(CYCLE, **kwargs)


@pytest.mark.parametrize(
    ("cycle_verdict", "increment_verdict", "expected_row"),
    [
        (_ACC, _ACC, 7),  # both accepted: the next increment is proposed
        (_ACC, _BLK, 8),  # a route nobody rendered (§8.3): repaired, never proposed past
        (_ACC, _REJ, 12),  # a criterion that does not discriminate (§8.2)
        (_BLK, _ACC, 8),
        (_REJ, _ACC, 12),
    ],
    ids=[
        "both-accepted",
        "increment-blocked",
        "increment-rejected",
        "cycle-blocked",
        "cycle-rejected",
    ],
)
def test_an_increment_is_accepted_only_when_its_own_acceptance_is(
    cycle_verdict, increment_verdict, expected_row
):
    """§8.4. Bug caught: an increment whose cycle passed its own checks read as accepted while
    its new criterion never discriminated, or a declared page never rendered — the next increment
    proposed on top of an unproven one."""
    decision = campaign_continuation_decision(
        CAMPAIGN,
        counters(),
        EndedCycle(CYCLE, CycleKind.INCREMENT, CycleEnding.ASSESSED, increment_verdict),
        assessment(cycle_verdict),
    )

    assert decision.row == expected_row


@pytest.mark.parametrize(
    ("earlier_parks", "expected"),
    [(0, (15, PendingAction.ABANDON_AND_PROPOSE)), (1, (4, CampaignOutcome.FAILURE))],
    ids=["the first park proposes again", "the second park stops"],
)
def test_parks_in_a_row_stop_at_the_limit_through_the_counters_the_decision_reads(
    earlier_parks, expected
):
    """#2294, through ``derive_counters`` as ``CycleCompletion.end`` derives them: the earlier
    parks' row-15 decisions on the log, then this park's decision, under a limit of 2. Bug caught:
    the park that reaches the limit proposing once more, so a campaign whose questions nobody
    answers launches a third increment before it stops, the shape SIP-0109 fixed for row 13."""
    from unittest.mock import MagicMock

    from squadops.campaigns.models import ControlOperation
    from squadops.campaigns.progress import CycleRecord, derive_counters

    started = MagicMock()
    started.operation, started.committed_at = ControlOperation.START, T0
    log = [started]
    for _ in range(earlier_parks):
        park = MagicMock()
        park.operation, park.outcome = ControlOperation.DECIDE, "applied"
        park.binding = {
            "row": 15,
            "ending": CycleEnding.PARKED.value,
            "action": PendingAction.ABANDON_AND_PROPOSE.value,
            "guard": Guard.PROCEED.value,
        }
        log.append(park)
    launched = [CycleRecord(CycleKind.CALIBRATION, 10)] + [
        CycleRecord(CycleKind.INCREMENT, 10) for _ in range(earlier_parks + 1)
    ]
    assert CAMPAIGN.policy.max_unaccepted_increments == 2

    decision = campaign_continuation_decision(
        CAMPAIGN,
        derive_counters(
            CAMPAIGN, log, launched, ending=CycleEnding.PARKED, now=T0, objective_met=False
        ),
        EndedCycle(CYCLE, CycleKind.INCREMENT, CycleEnding.PARKED),
        assessment(None),
    )

    assert (decision.row, decision.outcome or decision.action) == expected


@pytest.mark.parametrize(
    ("cycle_verdict", "count_overrides", "expected"),
    [
        # The build passed its own checks, and its criteria were met already: no repair can
        # change that, so a new proposal follows whether repairs remain or not.
        (_ACC, {}, (16, PendingAction.ABANDON_AND_PROPOSE, _GO, None)),
        (_ACC, dict(repair_cycles=1), (16, PendingAction.ABANDON_AND_PROPOSE, _GO, None)),
        # The build failed its own checks too, and a repair can fix those: row 12 as before.
        (_REJ, {}, (12, PendingAction.REPAIR, _GO, None)),
        # Counted as unaccepted at its own decision, as row 13's is (#2294): one before and this
        # one reach the builders' limit of two.
        (_ACC, dict(unaccepted_increments=1), (4, CampaignOutcome.FAILURE, None, None)),
    ],
    ids=["repairs-remain", "repairs-spent", "its-own-checks-failed", "counts-as-unaccepted"],
)
def test_a_rejection_only_for_already_met_criteria_is_abandoned_for_a_new_proposal(
    cycle_verdict, count_overrides, expected
):
    """#2315 (§24bq, row 16). Bug caught: an increment rejected only because its new criteria
    already pass on the accepted application sent to a repair, which rebuilds the candidate and
    cannot change a test that passes on the baseline (``cmp_fd71a56a9142``: one repair spent, the
    same split, then row 13)."""
    decision = campaign_continuation_decision(
        CAMPAIGN,
        counters(**count_overrides),
        EndedCycle(
            CYCLE,
            CycleKind.INCREMENT,
            CycleEnding.ASSESSED,
            RunVerdict.REJECTED,
            rejected_only_as_already_met=True,
        ),
        assessment(cycle_verdict),
    )

    assert shape(decision) == expected
