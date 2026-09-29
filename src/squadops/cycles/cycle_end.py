"""How a cycle ended — the typed, read-only view at the completion boundary (#1507 step 3).

``CycleCompletion`` (``adapters/cycles/cycle_completion.py``) produces one ``CycleEnd`` for every way
``execute_cycle`` ends, and it is the one place 2.0's continuation request enters (the Campaign
SIP's Appendix A). In 1.9 nothing consumes it beyond its wiring test: it is a view, and a PR in
which it changes an outcome has changed behaviour (the map's §5).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from squadops.cycles.run_loop_summary import RunTerminalDecision


class CycleStopReason(StrEnum):
    """Why the workload sequence stopped — one per way ``execute_cycle`` ends."""

    #: The last workload ran and its run finished.
    SEQUENCE_COMPLETED = "sequence_completed"
    #: A single-workload cycle's one run ended (D7's fast path); how, is its run's status.
    SINGLE_WORKLOAD_ENDED = "single_workload_ended"
    RUN_FAILED = "run_failed"
    RUN_CANCELLED = "run_cancelled"
    #: The gate's plan check rejected the plan and no framing re-roll was left (#473, #522).
    PLAN_REJECTED = "plan_rejected"
    #: The gate's decision was a rejection.
    GATE_REJECTED = "gate_rejected"
    #: Returned for revision where none could run: the budget spent, or not a framing workload.
    REVISION_UNAVAILABLE = "revision_unavailable"
    #: A decision value the dispatch doesn't know — never read as an approval (#466).
    GATE_DECISION_UNRECOGNIZED = "gate_decision_unrecognized"


@dataclass(frozen=True)
class CycleEnd:
    """A cycle's end, read-only. The cycle's ``CycleAssessment`` is read by ``cycle_id``
    (``adapters/cycles/cycle_evidence.assess_cycle``); this view never computes it."""

    cycle_id: str
    last_run_id: str
    #: The last run's persisted status.
    last_run_status: str
    #: The last run's terminal decision, as its loop summary recorded it (SIP-0108 §4.1); None
    #: when the run recorded none.
    last_run_terminal: RunTerminalDecision | None
    stopped_because: CycleStopReason
