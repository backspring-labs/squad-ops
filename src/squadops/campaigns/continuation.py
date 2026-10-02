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


@dataclass(frozen=True)
class EndedCycle:
    cycle_id: str
    kind: CycleKind
    ending: CycleEnding


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
    verdict = latest_verdict(latest)
    primary = latest_primary(latest)
    repairs_remain = counters.repair_cycles < policy.max_repair_cycles_per_increment
    retries_remain = counters.retry_cycles < policy.max_retry_cycles_per_increment
    environment = primary is AttributionClass.ENVIRONMENT_OR_INFRASTRUCTURE_FAILURE
    rejected = verdict is RunVerdict.REJECTED and cycle.ending is CycleEnding.ASSESSED
    # Row 13's predicate: this increment is abandoned, and counts as unaccepted.
    abandons = rejected and not environment and not repairs_remain

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
    row, action = _pending(cycle, verdict, environment, repairs_remain, retries_remain)
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


def _pending(
    cycle: EndedCycle,
    verdict: RunVerdict | None,
    environment: bool,
    repairs_remain: bool,
    retries_remain: bool,
) -> tuple[int, PendingAction]:
    if cycle.kind is CycleKind.CALIBRATION:
        return 5, PendingAction.PROPOSE
    if cycle.ending is not CycleEnding.ASSESSED:
        return 6, PendingAction.PROPOSE
    if verdict is RunVerdict.ACCEPTED:
        return 7, PendingAction.PROPOSE
    if verdict is RunVerdict.BLOCKED_UNVERIFIED:
        return (8, PendingAction.REPAIR) if repairs_remain else (9, PendingAction.ESCALATE)
    if verdict is RunVerdict.REJECTED:
        if environment:
            return (10, PendingAction.RETRY) if retries_remain else (11, PendingAction.ESCALATE)
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
    return None
