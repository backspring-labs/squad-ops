"""#77: propagate a cycle/run cancellation to Prefect.

Cancelling a cycle/run flips registry status, but without this the corresponding
Prefect flow run keeps executing (orphaned GPU/LLM work). We reconstruct the
flow-run name(s) for the cancelled run(s) — via the same ``flow_run_name`` the
executor wrote — find the still-running flow run(s) in Prefect, and transition
them to CANCELLED so workers stop.

Best-effort: registry cancellation is the source of truth; this never raises, so
the cancel route always reports the cycle/run as cancelled even if Prefect is
unreachable (the failure is logged).
"""

from __future__ import annotations

import logging

from squadops.api.runtime.deps import get_workflow_tracker
from squadops.cycles.naming import flow_run_name

logger = logging.getLogger(__name__)


async def cancel_orphaned_flow_runs(project_id: str, cycle_id: str, run_ids: list[str]) -> int:
    """Transition still-running Prefect flow runs for the given cycle runs to
    CANCELLED. Returns the number cancelled (0 if none active / Prefect off)."""
    if not run_ids:
        return 0
    try:
        tracker = get_workflow_tracker()
        names = [flow_run_name(project_id, cycle_id, rid) for rid in run_ids]
        flow_run_ids = await tracker.find_active_flow_run_ids(names)
        for flow_run_id in flow_run_ids:
            await tracker.set_flow_run_state(flow_run_id, "CANCELLED", "Cancelled")
        if flow_run_ids:
            logger.info(
                "#77: cancelled %d orphaned Prefect flow run(s) for cycle %s (runs=%s)",
                len(flow_run_ids),
                cycle_id,
                run_ids,
            )
        return len(flow_run_ids)
    except Exception:
        logger.warning(
            "#77: Prefect cancel propagation failed for cycle %s", cycle_id, exc_info=True
        )
        return 0
