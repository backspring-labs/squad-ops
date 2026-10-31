"""The continuation decision: what a campaign does after one of its cycles ends (SIP-0109 §10,
§9.5; #1800).

Pure: it reads the campaign, its counters, the cycle that ended and that cycle's assessment, and
returns a terminal outcome or a pending action with its guard. It persists nothing and dispatches
nothing — the caller writes the result in one control-log transition, and only a launch action
under ``proceed`` becomes a launch intent there (§12b). ``tests/unit/architecture`` holds it to
that by its import closure.

Three ordered steps, the first match winning in each:
1. **terminal outcomes** (rows 1–4) end the campaign;
2. **the pending action** (rows 5–14);
3. **the guard**, for a guardable action only: a pausing limit holds it (``paused``), otherwise
   ``proceed``. ``escalate`` has no guard, so escalation wins over a simultaneous pausing limit.

As built (§24b): the counters are read with the ending cycle counted. The no-progress count also
counts the abandonment row 13 would make, so the cycle that reaches the limit stops the campaign
instead of launching one more proposal. Whether the objective's measurement is met is the
caller's reading, passed in: the measurement is the objective's own text.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from squadops.campaigns.models import (
    Campaign,
    CampaignOutcome,
    CampaignPolicy,
    CycleKind,
)
from squadops.cycles.cycle_assessment import CycleAssessment, IndicatorState
from squadops.cycles.failure_attribution import AttributionClass
from squadops.cycles.verification_integrity import RunVerdict


class CycleEnding(StrEnum):
    """How a campaign cycle ended, for the decision. ``assessed`` is every ending that reached
    the build: its verdict (or its absence) is in the assessment."""

    ASSESSED = "assessed"
    REJECTED_AT_GATE = "rejected_at_gate"
    PROPOSAL_FAILED = "proposal_failed"
    #: §24bj: the plan gate escalated and its bound passed with nobody deciding it. Unaccepted,
    #: and neither rejected nor failed: silence is never a verdict.
    PARKED = "parked"
    #: §24bw: the run was held on its instruction bindings and the bound passed with the store
    #: still not answering. An infrastructure ending (rows 10 and 11), counted nowhere.
    HELD_STORE = "held_store"
    #: §24bw: held on an operator's input that can't be bound (a required reference at the
    #: cycle's commit, an instruction withdrawn or narrowed to nothing). Row 17 escalates.
    HELD_INPUT = "held_input"
    #: §24cb (#2704): the framing run's plan gate stopped the cycle before its build. Its plan was
    #: rejected (by the plan check with no re-roll left, by a person, or for a revision none could
    #: run), or the gate failed. Nothing was built, so there is no verdict: a calibration ends on
    #: row 2, and an increment, repair or retry is abandoned on row 18.
    STOPPED_AT_PLAN_GATE = "stopped_at_plan_gate"


@dataclass(frozen=True)
class EndedCycle:
    cycle_id: str
    kind: CycleKind
    ending: CycleEnding
    #: §8: an increment's own acceptance — its evaluation's verdict, or ``blocked_unverified``
    #: when the evaluation was never written. ``None`` for every other cycle.
    increment_verdict: RunVerdict | None = None
    #: #2315 (§24bq): its evaluation rejected it only for criteria the accepted application
    #: already meets — nothing blocked, nothing else unmet. A repair rebuilds the candidate, and
    #: those criteria's tests pass on the accepted tree whatever the candidate does.
    rejected_only_as_already_met: bool = False


def cycle_verdict(latest: CycleAssessment, cycle: EndedCycle) -> RunVerdict | None:
    """The verdict the decision reads (§8.4). A calibration's is the cycle's own. An increment is
    accepted only when the cycle's acceptance and its own (§8) both accepted: either rejecting
    rejects it, and anything unread leaves it ``blocked_unverified``, never accepted.

    A cycle that never reached its assessment has none (#2303): parked at its plan gate, stopped
    there (#2704), rejected at the increment gate, or its proposal failed. Its last run's summary
    judged a framing or a proposal, never a build, and a framing run's reads ``accepted`` with
    nothing executed. Read as the cycle's, it promoted a parked increment and met the objective
    with it, and promoted a calibration whose plan was rejected three times as an empty tree."""
    if cycle.ending is not CycleEnding.ASSESSED:
        return None
    verdict = latest_verdict(latest)
    if verdict is None or cycle.increment_verdict is None:
        return verdict
    pair = {verdict, cycle.increment_verdict}
    if RunVerdict.REJECTED in pair:
        return RunVerdict.REJECTED
    if pair == {RunVerdict.ACCEPTED}:
        return RunVerdict.ACCEPTED
    return RunVerdict.BLOCKED_UNVERIFIED


@dataclass(frozen=True)
class CampaignCounters:
    """The campaign's counts at the end of a cycle, that cycle counted (§9.5)."""

    cycles: int
    elapsed_s: int
    tokens: int
    #: Repair and retry cycles already run on the current increment.
    repair_cycles: int
    retry_cycles: int
    rejected_proposals_in_row: int
    #: Proposal cycles in a row that ended ``proposal_failed`` (§24bn, #2231).
    failed_proposals_in_row: int
    unaccepted_increments: int
    #: The objective's measurement, read with this increment counted (row 3).
    objective_met: bool


class CampaignLimit(StrEnum):
    """The limits the decision reads (§9.5). The others act inside a cycle or at the launcher."""

    TOTAL_CYCLES = "total_cycles"
    NO_PROGRESS = "unaccepted_increments"
    ELAPSED_TIME = "elapsed_time"
    BUDGET = "budget"
    REJECTED_PROPOSALS_IN_ROW = "rejected_proposals_in_row"
    FAILED_PROPOSALS_IN_ROW = "failed_proposals_in_row"


class TerminalCause(StrEnum):
    ABORTED = "aborted"
    CALIBRATION = "calibration"
    OBJECTIVE_MET = "objective_met"
    TOTAL_CYCLES = CampaignLimit.TOTAL_CYCLES.value
    NO_PROGRESS = CampaignLimit.NO_PROGRESS.value


class PendingAction(StrEnum):
    PROPOSE = "propose"
    REPAIR = "repair"
    RETRY = "retry"
    ABANDON_AND_PROPOSE = "abandon_and_propose"
    ESCALATE = "escalate"

    @property
    def guardable(self) -> bool:
        """An action the campaign would execute on its own. ``escalate`` waits for the owner."""
        return self is not PendingAction.ESCALATE

    @property
    def launches(self) -> CycleKind | None:
        """The cycle this action's launch intent creates, if it creates one."""
        return _LAUNCHES.get(self)


_LAUNCHES = {
    PendingAction.PROPOSE: CycleKind.INCREMENT,
    PendingAction.ABANDON_AND_PROPOSE: CycleKind.INCREMENT,
    PendingAction.REPAIR: CycleKind.REPAIR,
    PendingAction.RETRY: CycleKind.RETRY,
}


class Guard(StrEnum):
    PROCEED = "proceed"
    PAUSED = "paused"


@dataclass(frozen=True)
class ContinuationDecision:
    """A terminal outcome, or a pending action and its guard (§15). ``row`` is the §10 row that
    fired, so the control-log row says which predicate decided."""

    cycle_id: str
    row: int
    outcome: CampaignOutcome | None = None
    cause: TerminalCause | None = None
    action: PendingAction | None = None
    guard: Guard | None = None
    paused_by: CampaignLimit | None = None

    def __post_init__(self) -> None:
        if (self.outcome is None) == (self.action is None):
            raise ValueError("a decision is a terminal outcome or a pending action, not both")
        if self.action is not None and (self.guard is None) == self.action.guardable:
            raise ValueError(f"{self.action}: a guard exactly when the action is guardable")
        if (self.guard is Guard.PAUSED) != (self.paused_by is not None):
            raise ValueError("a paused guard names its limit, and only a paused one")

    @property
    def terminal(self) -> bool:
        return self.outcome is not None


def latest_verdict(latest: CycleAssessment) -> RunVerdict | None:
    """The cycle's verdict, or ``None`` when it never reached one (no verification summary)."""
    indicator = latest.indicator("verdict")
    if indicator.state is not IndicatorState.OBSERVED:
        return None
    return RunVerdict(indicator.value)


def latest_primary(latest: CycleAssessment) -> AttributionClass | None:
    reading = latest.attribution
    if reading.state is not IndicatorState.OBSERVED or reading.attribution is None:
        return None
    return reading.attribution.primary


#: The endings at which an increment, repair or retry built nothing and is abandoned, counting as
#: unaccepted, by their row. Each spends no repair, since there is no candidate to repair. A
#: calibration with either was not accepted, so row 2 ends the campaign before these are asked.
#: - §24bj, row 15: parked, its plan gate's escalation expired with nobody deciding it.
#: - §24cb, row 18 (#2704): stopped at its plan gate, its plan refused or the gate failed.
_ABANDONED_UNBUILT: dict[CycleEnding, int] = {
    CycleEnding.PARKED: 15,
    CycleEnding.STOPPED_AT_PLAN_GATE: 18,
}


def campaign_continuation_decision(
    campaign: Campaign,
    counters: CampaignCounters,
    cycle: EndedCycle,
    latest: CycleAssessment,
) -> ContinuationDecision:
    """§10, once per campaign cycle, keyed by ``cycle.cycle_id``."""
    if latest.cycle_id != cycle.cycle_id:
        raise ValueError(
            f"the assessment is of {latest.cycle_id}, the decision is for {cycle.cycle_id}"
        )
    policy = campaign.policy
    verdict = cycle_verdict(latest, cycle)
    primary = latest_primary(latest)
    repairs_remain = counters.repair_cycles < policy.max_repair_cycles_per_increment
    retries_remain = counters.retry_cycles < policy.max_retry_cycles_per_increment
    environment = primary is AttributionClass.ENVIRONMENT_OR_INFRASTRUCTURE_FAILURE
    rejected = verdict is RunVerdict.REJECTED and cycle.ending is CycleEnding.ASSESSED
    # Row 16 (#2315): the build passed its own verification, and its increment was rejected only
    # for criteria the accepted application already meets. No repair can change that.
    already_met = (
        rejected
        and cycle.rejected_only_as_already_met
        and latest_verdict(latest) is RunVerdict.ACCEPTED
    )
    # Rows 13, 15 and 18: this decision abandons the increment, and the abandonment counts as
    # unaccepted at this decision, so the one that reaches the limit stops rather than proposing
    # once more (#2294). A parked calibration, or one stopped at its plan gate, never reaches row
    # 4: row 2 ends the campaign. Row 16's abandonment (criteria the accepted application already
    # meets, told to the next proposal) counts toward no limit but the cycles and the budget
    # (#2849, §24ct): the work built and verified; the criteria were the fault.
    abandons = (rejected and not environment and not already_met and not repairs_remain) or (
        cycle.ending in _ABANDONED_UNBUILT
    )

    def stop(row: int, outcome: CampaignOutcome, cause: TerminalCause) -> ContinuationDecision:
        return ContinuationDecision(cycle.cycle_id, row, outcome=outcome, cause=cause)

    # Step 1: terminal outcomes.
    if campaign.outcome is CampaignOutcome.ABORTED:
        return stop(1, CampaignOutcome.ABORTED, TerminalCause.ABORTED)
    if cycle.kind is CycleKind.CALIBRATION and verdict is not RunVerdict.ACCEPTED:
        return stop(2, CampaignOutcome.FAILURE, TerminalCause.CALIBRATION)
    if (
        cycle.kind is not CycleKind.CALIBRATION
        and verdict is RunVerdict.ACCEPTED
        and counters.objective_met
    ):
        return stop(3, CampaignOutcome.SUCCESS, TerminalCause.OBJECTIVE_MET)
    if counters.cycles >= policy.max_cycles:
        return stop(4, CampaignOutcome.EXHAUSTED, TerminalCause.TOTAL_CYCLES)
    if counters.unaccepted_increments + abandons >= policy.max_unaccepted_increments:
        return stop(4, CampaignOutcome.FAILURE, TerminalCause.NO_PROGRESS)

    # Step 2: the pending action.
    row, action = _pending(cycle, verdict, environment, repairs_remain, retries_remain, already_met)
    if not action.guardable:
        return ContinuationDecision(cycle.cycle_id, row, action=action)

    # Step 3: the guard.
    limit = _pausing_limit(policy, counters)
    return ContinuationDecision(
        cycle.cycle_id,
        row,
        action=action,
        guard=Guard.PAUSED if limit else Guard.PROCEED,
        paused_by=limit,
    )


def calibration_record_decision(
    campaign: Campaign, record_id: str, *, elapsed_s: int
) -> ContinuationDecision:
    """§10 for a calibration record (§24bv point 1, §24cc), once per record, keyed by its id.

    The record is read as an accepted calibration, so row 5 proposes. Row 2 never fires: a start
    that would have failed it was refused, and wrote no record. The record is no cycle, so it
    counts toward none of row 4's limits and none of step 3's guards: the guard reads counters
    with nothing counted but the elapsed time, which runs from the start as for any campaign.
    Row 1 still comes first."""
    if campaign.outcome is CampaignOutcome.ABORTED:
        return ContinuationDecision(
            record_id, 1, outcome=CampaignOutcome.ABORTED, cause=TerminalCause.ABORTED
        )
    nothing_counted = CampaignCounters(
        cycles=0,
        elapsed_s=elapsed_s,
        tokens=0,
        repair_cycles=0,
        retry_cycles=0,
        rejected_proposals_in_row=0,
        failed_proposals_in_row=0,
        unaccepted_increments=0,
        objective_met=False,
    )
    limit = _pausing_limit(campaign.policy, nothing_counted)
    return ContinuationDecision(
        record_id,
        5,
        action=PendingAction.PROPOSE,
        guard=Guard.PAUSED if limit else Guard.PROCEED,
        paused_by=limit,
    )


def _pending(
    cycle: EndedCycle,
    verdict: RunVerdict | None,
    environment: bool,
    repairs_remain: bool,
    retries_remain: bool,
    already_met: bool,
) -> tuple[int, PendingAction]:
    if cycle.kind is CycleKind.CALIBRATION:
        return 5, PendingAction.PROPOSE
    # Rows 15 and 18, asked before row 6, which would propose without counting the increment.
    if cycle.ending in _ABANDONED_UNBUILT:
        return _ABANDONED_UNBUILT[cycle.ending], PendingAction.ABANDON_AND_PROPOSE
    # §24bw, asked before row 6: a hold that expired said nothing about the squad's work. The
    # store's reads as the environment's (rows 10 and 11); an operator's input escalates (row 17),
    # so the owner re-binds or withdraws it and resumes. Neither is an abandonment.
    if cycle.ending is CycleEnding.HELD_STORE:
        return (10, PendingAction.RETRY) if retries_remain else (11, PendingAction.ESCALATE)
    if cycle.ending is CycleEnding.HELD_INPUT:
        return 17, PendingAction.ESCALATE
    if cycle.ending is not CycleEnding.ASSESSED:
        return 6, PendingAction.PROPOSE
    if verdict is RunVerdict.ACCEPTED:
        return 7, PendingAction.PROPOSE
    # #1824 (§24bg, §24bh): rows 10 and 11 read the attribution, not the verdict, and are asked
    # before rows 8 and 9. A run that failed outside the work verified nothing, so finalization
    # records it ``blocked_unverified``, and a repair would have no work to repair.
    if environment:
        return (10, PendingAction.RETRY) if retries_remain else (11, PendingAction.ESCALATE)
    if verdict is RunVerdict.BLOCKED_UNVERIFIED:
        return (8, PendingAction.REPAIR) if repairs_remain else (9, PendingAction.ESCALATE)
    if verdict is RunVerdict.REJECTED:
        # Row 16 (#2315, §24bq), asked before row 12: a rejection only for criteria the accepted
        # application already meets is abandoned for a new proposal, told which they are.
        if already_met:
            return 16, PendingAction.ABANDON_AND_PROPOSE
        if repairs_remain:
            return 12, PendingAction.REPAIR
        return 13, PendingAction.ABANDON_AND_PROPOSE
    return 14, PendingAction.ESCALATE


def _pausing_limit(policy: CampaignPolicy, counters: CampaignCounters) -> CampaignLimit | None:
    if counters.elapsed_s >= policy.max_elapsed_s:
        return CampaignLimit.ELAPSED_TIME
    if counters.tokens >= policy.budget_tokens:
        return CampaignLimit.BUDGET
    if counters.rejected_proposals_in_row >= policy.max_rejected_proposals_in_row:
        return CampaignLimit.REJECTED_PROPOSALS_IN_ROW
    # §24bn (#2231): a failed proposal is retried by the next proposal cycle (row 6), up to the
    # policy's retries; the failure past them holds that launch for the owner.
    if counters.failed_proposals_in_row > policy.max_proposal_run_retries:
        return CampaignLimit.FAILED_PROPOSALS_IN_ROW
    return None
