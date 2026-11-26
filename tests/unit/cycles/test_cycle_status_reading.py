"""A cycle's recorded ending decides its status once it has ended (#3201).

Rehearsal 3 of the 2.8 demonstration: a cycle the Campaign ended at the gate kept its framing and
implementation workloads pending, so the cycle route read it ``active`` from then on, and the
Campaign's abort cancelled it 40 minutes after it ended. Its ``cycle_ends`` row said how it ended
all along.
"""

from __future__ import annotations

import pytest

from squadops.cycles.cycle_end import CycleStopReason, RecordedEnd
from squadops.cycles.lifecycle import (
    STATUS_OF_ENDING,
    StatusConflict,
    read_cycle_status,
)
from squadops.cycles.models import CycleStatus, Run


def _run(n: int, status: str) -> Run:
    return Run(
        run_id=f"run_{n}",
        cycle_id="cyc_1",
        run_number=n,
        status=status,
        initiated_by="campaign",
        resolved_config_hash="h",
    )


def _end(reason: CycleStopReason, last: int = 3) -> RecordedEnd:
    return RecordedEnd(cycle_id="cyc_1", last_run_id=f"run_{last}", stopped_because=reason)


#: Rehearsal 3's ``cyc_929c449744f1``: the proposal and its two revisions, the first two
#: cancelled by their revisions, and the framing and implementation workloads never started.
_ENDED_AT_GATE_RUNS = [_run(1, "cancelled"), _run(2, "cancelled"), _run(3, "completed")]
_ENDED_AT_GATE_WORKLOADS = ["completed", "pending", "pending"]


def test_a_cycle_ended_at_the_gate_reads_ended_not_active():
    """Bug caught: #3201 itself. Rule 3 read the pending workloads as work still to do."""
    reading = read_cycle_status(
        _ENDED_AT_GATE_RUNS,
        False,
        _ENDED_AT_GATE_WORKLOADS,
        _end(CycleStopReason.REVISION_UNAVAILABLE),
    )

    assert (reading.status, reading.recorded_ending, reading.conflict) == (
        CycleStatus.FAILED,
        CycleStopReason.REVISION_UNAVAILABLE,
        None,
    )


def test_without_its_end_record_the_same_cycle_reads_active():
    """The control: the reading the fix replaces, so the test above can't pass vacuously."""
    reading = read_cycle_status(_ENDED_AT_GATE_RUNS, False, _ENDED_AT_GATE_WORKLOADS, None)

    assert (reading.status, reading.recorded_ending) == (CycleStatus.ACTIVE, None)


def test_every_stop_reason_has_a_reading():
    """Bug caught: a stop reason added to ``CycleStopReason`` without a reading here raises a
    ``KeyError`` on every read of a cycle that stopped for it, the cycle list included."""
    assert set(STATUS_OF_ENDING) == set(CycleStopReason)


@pytest.mark.parametrize("reason", list(CycleStopReason))
def test_each_ending_reads_its_status_and_a_non_ending_defers_to_the_runs(reason):
    """Every ending, on a cycle whose runs have all stopped: an ending reads its own status and
    names itself; a stop that isn't an ending (a paused run, a single workload) reads the runs."""
    runs = [_run(1, "completed"), _run(2, "failed")]
    reading = read_cycle_status(runs, False, None, _end(reason, last=2))

    expected = STATUS_OF_ENDING[reason]
    if expected is None:
        assert (reading.status, reading.recorded_ending) == (CycleStatus.FAILED, None)
    else:
        assert (reading.status, reading.recorded_ending) == (expected, reason)


def test_a_run_still_live_from_before_the_ending_is_never_hidden():
    """Bug caught: an end row that conceals a run really going, so an abort skips it and the run
    keeps the box. The runs decide, and the conflict is named."""
    runs = [_run(1, "completed"), _run(2, "running"), _run(3, "completed")]
    reading = read_cycle_status(runs, False, None, _end(CycleStopReason.SEQUENCE_COMPLETED))

    assert (reading.status, reading.recorded_ending, reading.conflict) == (
        CycleStatus.ACTIVE,
        CycleStopReason.SEQUENCE_COMPLETED,
        StatusConflict.RUN_LIVE_AFTER_ENDING,
    )


def test_a_run_newer_than_the_ending_reopened_the_cycle():
    """Bug caught: a cycle retried after it failed reads failed while its new run completes. The
    newer run's cycle is read from its runs, and the old ending is history, not a conflict."""
    runs = [_run(1, "failed"), _run(2, "completed")]
    reading = read_cycle_status(runs, False, None, _end(CycleStopReason.RUN_FAILED, last=1))

    assert (reading.status, reading.recorded_ending, reading.conflict) == (
        CycleStatus.COMPLETED,
        None,
        None,
    )


def test_a_cancel_after_the_ending_leaves_the_ending_and_is_named():
    """``cyc_929c449744f1`` as stored: the abort's cancel landed 40 minutes after the cycle ended.
    The ending was first, so it stands, and the cancel is the conflict, never dropped."""
    reading = read_cycle_status(
        _ENDED_AT_GATE_RUNS,
        True,
        _ENDED_AT_GATE_WORKLOADS,
        _end(CycleStopReason.REVISION_UNAVAILABLE),
    )

    assert (reading.status, reading.conflict) == (
        CycleStatus.FAILED,
        StatusConflict.CANCELLED_AFTER_ENDING,
    )


def test_a_cancel_racing_the_cycle_s_completion_resolves_to_one_ending():
    """An abort that cancels as the cycle's last run completes: both records land. The reading
    names one ending, the completion the boundary recorded, and the cancel as the conflict."""
    runs = [_run(1, "completed"), _run(2, "completed")]
    reading = read_cycle_status(runs, True, None, _end(CycleStopReason.SEQUENCE_COMPLETED, 2))

    assert (reading.status, reading.conflict) == (
        CycleStatus.COMPLETED,
        StatusConflict.CANCELLED_AFTER_ENDING,
    )


def test_a_cancelled_cycle_whose_run_ended_cancelled_has_no_conflict():
    """A cancel of a live cycle ends its run cancelled, and both records agree."""
    runs = [_run(1, "completed"), _run(2, "cancelled")]
    reading = read_cycle_status(runs, True, None, _end(CycleStopReason.RUN_CANCELLED, 2))

    assert (reading.status, reading.conflict) == (CycleStatus.CANCELLED, None)
