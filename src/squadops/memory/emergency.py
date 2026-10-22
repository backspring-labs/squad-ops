"""A task instruction's emergency withdrawal (SIP-0110 Appendix A §3.8, T13; #2178).

A withdrawal stops the next dispatch (§5w). An emergency one also stops the work already built on
the instruction: each run of its cycle still in flight is halted, at its next task boundary or in
the wait of the task it has out, whose output is then never accepted. A run that received the
instruction restarts as a new run of its cycle from the first of its tasks that received it, through
the checkpoint before that task (the run's accepted work before it), with its bindings read again,
so the withdrawn instruction is absent. A run that only built on work an earlier run of its cycle
did under the instruction is halted and nothing in it restarts: the restart is a new cycle.

History is kept and never reused: the exposures and envelopes stay, marked as having used a
withdrawn instruction (§5u's mark), and the restart copies nothing of the work after its checkpoint.

Pure: the route reads the exposures and the runs, and these rules decide.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass

from squadops.cycles.models import Run, RunStatus
from squadops.memory.exposures import Exposure

#: The forwarding override a restart run carries: the halted run and the task it restarts from.
EMERGENCY_RESTART_OVERRIDE = "emergency_restart"

#: A run its cycle hasn't finished with: one that would go on to build on the instruction's work.
IN_FLIGHT = frozenset({RunStatus.QUEUED.value, RunStatus.RUNNING.value, RunStatus.PAUSED.value})


@dataclass(frozen=True)
class Halt:
    """A run to halt, and the task its restart runs again from (``None``: no restart)."""

    run_id: str
    restart_from_task_id: str | None


def tasks_received(
    record_id: str, exposures: Iterable[Exposure], *, cycle_id: str
) -> dict[str, list[str]]:
    """Each run of ``cycle_id`` whose dispatch was handed a revision of ``record_id``, with the
    tasks that received it, each in the order first recorded. A held task was handed nothing."""
    received: dict[str, list[str]] = {}
    for e in sorted(exposures, key=lambda x: (x.recorded_at, x.attempt)):
        if e.cycle_id != cycle_id or e.held:
            continue
        supplied = (e.task_instructions or {}).get("supplied") or ()
        if any(s.get("record_id") == record_id for s in supplied):
            tasks = received.setdefault(e.run_id, [])
            if e.task_id not in tasks:
                tasks.append(e.task_id)
    return received


def halts_for(received: Mapping[str, Sequence[str]], runs: Iterable[Run]) -> list[Halt]:
    """The runs of the cycle to halt once some run of it received the instruction: every run still
    in flight, since it either received the instruction or builds on work that did. Each restarts
    from the first of its own tasks that received it, or not at all. Conservative: a run whose
    cycle only received the instruction in a run it discarded is halted too."""
    if not received:
        return []
    return [
        Halt(r.run_id, received[r.run_id][0] if received.get(r.run_id) else None)
        for r in runs
        if r.status in IN_FLIGHT
    ]


def restart_checkpoint(checkpoints: Iterable, before_task_id: str):
    """The latest of a halted run's checkpoints taken before ``before_task_id`` completed: the
    accepted work its restart keeps. ``None`` when there is none, so the restart runs from the
    start."""
    usable = [c for c in checkpoints if before_task_id not in c.completed_task_ids]
    return max(usable, key=lambda c: c.checkpoint_index) if usable else None
