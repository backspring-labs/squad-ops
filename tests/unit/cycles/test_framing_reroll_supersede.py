"""Framing re-roll supersedes a COMPLETED run (#522, root-caused on pf-43).

#522 gave a system plan-validation rejection a bounded framing re-roll instead of killing
the cycle. It passed its harness and **never once fired live**. pf-43 showed why: the
re-roll's first act is ``cancel_run`` on the superseded framing run, but inter-workload
gates are decided on COMPLETED runs by design (SIP-0083 D15 — ``GATE_REJECTED_STATES``
excludes COMPLETED for exactly that reason). So the run is already terminal when the
rejection lands, ``COMPLETED -> CANCELLED`` was not a legal transition, and the raise
killed the re-roll before it created the replacement run.

Observed on pf-43 (``cyc_e83829c268a6``): framing finished 16:47:10.65, the REJECTED gate
decision was recorded 16:47:10.73, and then nothing — no re-roll log, no WORKLOAD_ADVANCED
event, no second run, and a cycle that simply stopped with two of its two re-rolls unused.
"""

from __future__ import annotations

import pytest

from squadops.cycles.lifecycle import TERMINAL_STATES, validate_run_transition
from squadops.cycles.models import IllegalStateTransitionError, RunStatus

pytestmark = [pytest.mark.domain_cycles]


def test_completed_run_can_be_superseded():
    """The exact transition the re-roll needs, and the one pf-43 died on."""
    validate_run_transition(RunStatus.COMPLETED, RunStatus.CANCELLED)


def test_a_gate_rejection_lands_on_a_completed_run():
    """Pins the premise: if COMPLETED ever became gate-rejecting, the edge is moot."""
    from squadops.cycles.lifecycle import GATE_REJECTED_STATES

    assert RunStatus.COMPLETED not in GATE_REJECTED_STATES
    assert RunStatus.COMPLETED in TERMINAL_STATES


@pytest.mark.parametrize(
    "source",
    [RunStatus.CANCELLED, RunStatus.FAILED],
)
def test_other_terminal_states_still_cannot_be_cancelled(source):
    """Only COMPLETED gains the edge — this is a supersede, not a general unlock."""
    with pytest.raises(IllegalStateTransitionError):
        validate_run_transition(source, RunStatus.CANCELLED)


def test_completed_still_cannot_go_anywhere_else():
    for dest in (RunStatus.RUNNING, RunStatus.PAUSED, RunStatus.QUEUED, RunStatus.COMPLETED):
        with pytest.raises(IllegalStateTransitionError):
            validate_run_transition(RunStatus.COMPLETED, dest)


def test_the_pf43_sequence_now_completes():
    """Replay of the real state sequence: run completes, gate rejects, re-roll supersedes."""
    validate_run_transition(RunStatus.QUEUED, RunStatus.RUNNING)
    validate_run_transition(RunStatus.RUNNING, RunStatus.COMPLETED)
    # the gate decision is recorded here (COMPLETED is not gate-rejecting)
    validate_run_transition(RunStatus.COMPLETED, RunStatus.CANCELLED)
