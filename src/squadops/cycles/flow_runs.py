"""Ending a run's Prefect flow runs that no live process will end (#2007).

A run's flow run is opened by the process executing it, and ended by that process when the run
ends. A restart breaks that: the process that owned the flow run is gone, and the re-attach
(SIP-0109 §24am) opens a new one for the same run. The 2.0 recovery diagnostics left nine flow
runs ``RUNNING`` for 20–30 hours this way, each beside a completed flow run of the same name.

A run's flow runs share one name (``naming.flow_run_name``), and one run executes in one process
at a time, so an open flow run with the run's name that the executing process did not open
belongs to a process that died. This ends them: when a flow run is opened for the run, and when
the run ends. The cycle-cancel path ends a cancelled cycle's flow runs the same way (#77).

Best-effort, as the tracker is: a failure is logged and never fails the run. Prefect is a view,
and ``cycle_runs`` is the record.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from squadops.cycles.models import RunStatus

if TYPE_CHECKING:
    from squadops.ports.cycles.workflow_tracker import WorkflowTrackerPort

logger = logging.getLogger(__name__)


async def end_open_flow_runs(
    tracker: WorkflowTrackerPort | None,
    names: list[str],
    *,
    status: RunStatus = RunStatus.CANCELLED,
    keep: str | None = None,
) -> list[str]:
    """End every still-open flow run named in ``names``, except ``keep``. Returns those ended.

    ``status`` is what they are set to: ``CANCELLED`` for a flow run no process will finish.
    ``keep`` is the caller's own flow run, which it ends itself with the run's real status.
    """
    if tracker is None or not names:
        return []
    try:
        open_ids = await tracker.find_active_flow_run_ids(names)
    except Exception:
        logger.warning("could not list the open flow runs %s", names, exc_info=True)
        return []
    ended = []
    for flow_run_id in open_ids:
        if flow_run_id == keep:
            continue
        try:
            await tracker.set_flow_run_state(flow_run_id, status)
        except Exception:
            logger.warning("could not end flow run %s", flow_run_id, exc_info=True)
            continue
        ended.append(flow_run_id)
    return ended
