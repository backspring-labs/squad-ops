"""
Stranded RuntimeActivity hygiene (#672 — the FocusLease #373 class, applied to activities).

`runtime_activities` enforces one active activity per agent (D9, the §4.2
partial unique index). The §4.4 instrumentation terminalizes each activity when
its task replies — but an interrupted run strands the row in an active state
with no expiry, and every later ``start_activity`` for that agent then trips
``uq_runtime_activities_one_active_per_agent``. The write is best-effort, so
runs proceed while activity tracking goes silently dead and the traceback
recurs at every dispatch. Two complementary sweeps close the class:

- :func:`abort_cycle_activities` — run finalize: task dispatch for the run is
  over, so any activity still active for its cycle is stranded; end them all.
  Called from the ``RunCompletion`` collaborator on every terminal path.
- :func:`reap_stale_activities` — startup: end active activities whose owning
  cycle is already terminal (rows stranded by a process death that skipped
  finalize, and historic rows predating the sweep).

Both are best-effort and per-row isolated, like ``admission.release_participants``:
one bad row never blocks clearing the rest, and the adapter's active-only
UPDATE guard makes a concurrent terminalization a harmless no-op (counted only
when the row actually flipped).

Pure orchestration: depends only on the activity port and ``runtime.reasons``.
Cycle-status knowledge enters through the ``cycle_is_terminal`` predicate the
composition root supplies — ``squadops.runtime`` never imports the cycles
domain (D26 direction).
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from squadops.runtime import reasons

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from squadops.ports.runtime.activity import RuntimeActivityPort

logger = logging.getLogger(__name__)


async def abort_cycle_activities(
    activity_port: RuntimeActivityPort,
    cycle_id: str,
    *,
    reason_code: str = reasons.ACTIVITY_STRANDED_AT_RUN_FINALIZE,
) -> int:
    """Abort every active activity owned by ``cycle_id``; return how many flipped.

    Run-finalize sweep: the finishing run's dispatch loop has exited, so an
    active row for its cycle has no owner left to terminalize it.
    """
    aborted = 0
    for activity in await activity_port.list_active_activities(cycle_id=cycle_id):
        try:
            ended = await activity_port.abort_activity(activity.runtime_activity_id, reason_code)
        except Exception:
            logger.warning(
                "best-effort abort of stranded activity %s (agent=%s, cycle=%s) failed",
                activity.runtime_activity_id,
                activity.agent_id,
                cycle_id,
                exc_info=True,
            )
            continue
        if ended is not None:
            aborted += 1
            logger.info(
                "aborted stranded activity %s (agent=%s, cycle=%s, type=%s)",
                activity.runtime_activity_id,
                activity.agent_id,
                cycle_id,
                activity.activity_type,
            )
    return aborted


async def reap_stale_activities(
    activity_port: RuntimeActivityPort,
    *,
    cycle_is_terminal: Callable[[str], Awaitable[bool]],
) -> int:
    """Abort active activities whose owning cycle is terminal; return how many flipped.

    Startup reaper. Activities without a ``cycle_id`` (duty/ambient sources)
    have no owning cycle to consult and are left alone. A predicate or abort
    failure skips that row only — the reaper must clear what it can, since one
    stranded row blocks all of that agent's future activity tracking.
    """
    reaped = 0
    for activity in await activity_port.list_active_activities():
        if activity.cycle_id is None:
            continue
        try:
            if not await cycle_is_terminal(activity.cycle_id):
                continue
            ended = await activity_port.abort_activity(
                activity.runtime_activity_id, reasons.ACTIVITY_STRANDED_CYCLE_TERMINAL
            )
        except Exception:
            logger.warning(
                "best-effort reap of stranded activity %s (agent=%s, cycle=%s) failed",
                activity.runtime_activity_id,
                activity.agent_id,
                activity.cycle_id,
                exc_info=True,
            )
            continue
        if ended is not None:
            reaped += 1
            logger.info(
                "reaped stranded activity %s (agent=%s, cycle=%s, type=%s)",
                activity.runtime_activity_id,
                activity.agent_id,
                activity.cycle_id,
                activity.activity_type,
            )
    return reaped
