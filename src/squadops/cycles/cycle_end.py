"""How a cycle ended — the typed, read-only view at the completion boundary (#1507 step 3).

``CycleCompletion`` (``src/squadops/execution/cycle_completion.py``) produces one ``CycleEnd`` for every way
``execute_cycle`` ends, and it is the one place 2.0's continuation request enters (the Campaign
SIP's Appendix A). In 1.9 nothing consumes it beyond its wiring test: it is a view, and a PR in
which it changes an outcome has changed behaviour (the map's §5).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from squadops.cycles.failure_attribution import TerminalKind
from squadops.cycles.models import RunStatus
from squadops.cycles.run_loop_summary import RunTerminalDecision


class CycleStopReason(StrEnum):
    """Why the workload sequence stopped — one per way ``execute_cycle`` ends."""

    #: The last workload ran and its run finished.
    SEQUENCE_COMPLETED = "sequence_completed"
    #: A single-workload cycle's one run ended (D7's fast path); how, is its run's status.
    SINGLE_WORKLOAD_ENDED = "single_workload_ended"
    RUN_FAILED = "run_failed"
    RUN_CANCELLED = "run_cancelled"
    #: #1754: the run was deferred — admission paused it (a duty window or a focus-lease
    #: conflict, SIP-0089 §2.5) or a task's BLOCKED outcome did. It stays resumable: ``runs
    #: resume`` re-enters the sequence at it (#257).
    RUN_PAUSED = "run_paused"
    #: #1754: ``execute_run`` returned with the run still queued or running, which its contract
    #: excludes. Recorded as what it is rather than read as completed.
    RUN_NOT_TERMINAL = "run_not_terminal"
    #: The gate's plan check rejected the plan and no framing re-roll was left (#473, #522).
    PLAN_REJECTED = "plan_rejected"
    #: The gate's decision was a rejection.
    GATE_REJECTED = "gate_rejected"
    #: Returned for revision where none could run: the budget spent, or not a framing workload.
    REVISION_UNAVAILABLE = "revision_unavailable"
    #: A decision value the dispatch doesn't know — never read as an approval (#466).
    GATE_DECISION_UNRECOGNIZED = "gate_decision_unrecognized"
    #: The inter-workload gate raised before any decision (#2213): a defect, never an approval.
    GATE_FAILED = "gate_failed"
    #: #2890 (SIP-0109 §24cz): the implementation run ended at its qa task because a criterion's
    #: test already passes on the campaign branch's head. The run declares it in its terminal
    #: decision (``TerminalKind.CRITERIA_NOT_CHECKABLE``); the completion boundary reads it.
    CRITERIA_NOT_CHECKABLE = "criteria_not_checkable"


#: Why the sequence stops on a run that did not complete — every ``RunStatus`` but ``COMPLETED``
#: (#1754). The loop used to stop only on the first two, and read the rest as completed.
STOP_REASON_FOR_UNCOMPLETED_RUN: dict[RunStatus, CycleStopReason] = {
    RunStatus.FAILED: CycleStopReason.RUN_FAILED,
    RunStatus.CANCELLED: CycleStopReason.RUN_CANCELLED,
    RunStatus.PAUSED: CycleStopReason.RUN_PAUSED,
    RunStatus.QUEUED: CycleStopReason.RUN_NOT_TERMINAL,
    RunStatus.RUNNING: CycleStopReason.RUN_NOT_TERMINAL,
}

#: The endings a failed run declares for the cycle, by its terminal decision's kind (#2890). A
#: failed run stops the sequence as ``run_failed``; one whose raise site declared an ending of the
#: cycle's own (SIP-0108 §4.1) is recorded and heard as that ending, so the campaign reads what
#: the run decided rather than an assessment of a build that never delivered.
STOP_REASON_FOR_TERMINAL_KIND: dict[TerminalKind, CycleStopReason] = {
    TerminalKind.CRITERIA_NOT_CHECKABLE: CycleStopReason.CRITERIA_NOT_CHECKABLE,
}


#: The stops a run's own ending reaches the boundary by: a sequence's failed run, and the one run
#: of a single-workload cycle, which is how a campaign's repair runs (#2946).
_STOPS_A_RUN_CAN_DECLARE_OVER = frozenset(
    {CycleStopReason.RUN_FAILED, CycleStopReason.SINGLE_WORKLOAD_ENDED}
)


def declared_stop_reason(
    stopped_because: CycleStopReason, terminal: RunTerminalDecision | None
) -> CycleStopReason:
    """``stopped_because``, or the cycle's ending the run's terminal decision declares
    (``STOP_REASON_FOR_TERMINAL_KIND``). Any other stop, a run that declared no ending of the
    cycle's, and a summary whose terminal is not a decision, are left as the sequence read them."""
    if stopped_because not in _STOPS_A_RUN_CAN_DECLARE_OVER or not isinstance(
        terminal, RunTerminalDecision
    ):
        return stopped_because
    return STOP_REASON_FOR_TERMINAL_KIND.get(terminal.kind, stopped_because)


@dataclass(frozen=True)
class CycleEnd:
    """A cycle's end, read-only. The cycle's ``CycleAssessment`` is read by ``cycle_id``
    (``src/squadops/execution/cycle_evidence.assess_cycle``); this view never computes it."""

    cycle_id: str
    last_run_id: str
    #: The last run's persisted status.
    last_run_status: str
    #: The last run's terminal decision, as its loop summary recorded it (SIP-0108 §4.1); None
    #: when the run recorded none.
    last_run_terminal: RunTerminalDecision | None
    stopped_because: CycleStopReason


@dataclass(frozen=True)
class RecordedEnd:
    """One ending of a cycle as the completion boundary recorded it, before its campaign was told
    (SIP-0109 §12a, #1803). What a re-entry reads: never a stop reason reconstructed from the
    cycle's runs, which a gate rejection and a failed run can leave looking alike."""

    cycle_id: str
    last_run_id: str
    stopped_because: CycleStopReason
