"""What a task instruction's emergency withdrawal halts, and where each restart runs from (SIP-0110
Appendix A §3.8, T13; #2178): the pure rules the route applies to its cycle's exposures and runs."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from squadops.cycles.checkpoint import RunCheckpoint
from squadops.cycles.models import Run
from squadops.memory.emergency import Halt, halts_for, restart_checkpoint, tasks_received
from squadops.memory.exposures import Exposure
from squadops.memory.recall import RecallQuery, UnitKind

pytestmark = [pytest.mark.domain_memory]

T0 = datetime(2026, 10, 22, tzinfo=UTC)


def _exposure(run_id, task_id, minute, *, record="mrec_1", cycle="cyc_a", held=False, attempt=1):
    return Exposure(
        run_id=run_id, task_id=task_id, cycle_id=cycle, agent_id="neo", seam="plan_writing",
        query=RecallQuery(project_id="p", task_type="t", role="dev", stack="s", model_family="f",
                          unit_kind=UnitKind.CYCLE, unit_id=cycle),
        recalled={"disposition": "disabled"}, recorded_at=T0 + timedelta(minutes=minute),
        attempt=attempt,
        task_instructions={"disposition": "supplied",
                           "supplied": [{"record_id": record, "revision": "1"}], "unresolved": []},
        # Held by its project section: the task section was supplied, and still reached nothing.
        project_instructions={"disposition": "incomplete", "supplied": [], "unresolved": []}
        if held else None,
    )  # fmt: skip


def test_the_tasks_that_received_it_are_read_in_the_order_they_were_handed_it():
    """Bugs caught: a restart from the last task that received it rather than the first, keeping
    work built on the earlier one; a held task (handed nothing) read as received; another cycle's
    run or another instruction's receipt counted."""
    exposures = [
        _exposure("run_1", "t_repair", 9),
        _exposure("run_1", "t_design", 2),
        _exposure("run_1", "t_design", 5, attempt=2),
        _exposure("run_1", "t_held", 1, held=True),
        _exposure("run_2", "t_other", 3, cycle="cyc_b"),
        _exposure("run_1", "t_plan", 4, record="mrec_2"),
    ]

    assert tasks_received("mrec_1", exposures, cycle_id="cyc_a") == {
        "run_1": ["t_design", "t_repair"]
    }


def _run(run_id, status):
    return Run(run_id=run_id, cycle_id="cyc_a", run_number=1, status=status,
               initiated_by="api", resolved_config_hash="h")  # fmt: skip


@pytest.mark.parametrize(
    ("received", "runs", "halts"),
    [
        ({"run_1": ["t_design", "t_repair"]}, [_run("run_1", "paused")], [Halt("run_1", "t_design")]),
        ({"run_1": ["t_design"]},
         [_run("run_1", "completed"), _run("run_2", "queued")], [Halt("run_2", None)]),
        ({"run_1": ["t_design"]}, [_run("run_1", "failed")], []),
        ({}, [_run("run_1", "running")], []),
    ],
    ids=["received-in-flight", "built-on-a-finished-run", "nothing-in-flight", "never-received"],
)  # fmt: skip
def test_what_is_halted_and_where_it_restarts(received, runs, halts):
    """Bugs caught: a paused (held or gated) run left running; a queued run that would build on
    the finished run's work started; a finished run halted; a run halted when nothing received
    the instruction."""
    assert halts_for(received, runs) == halts


def _checkpoint(index, *tasks):
    return RunCheckpoint("run_1", index, tasks, {}, (), (), T0)


def test_the_restart_keeps_the_latest_work_from_before_the_task_that_received_it():
    """Bugs caught: the restart keeping the checkpoint that holds the task's own output (built on
    the instruction), or an earlier one than it could, running accepted work again."""
    checkpoints = [_checkpoint(0, "t_a"), _checkpoint(2, "t_a", "t_b", "t_design"),
                   _checkpoint(1, "t_a", "t_b")]  # fmt: skip

    assert restart_checkpoint(checkpoints, "t_design").checkpoint_index == 1
    assert restart_checkpoint([_checkpoint(0, "t_design")], "t_design") is None
