"""Propagate a cycle/run cancellation beyond the registry (#77, #529).

Flipping registry status is the source of truth, but a cancelled run leaves two
kinds of live state behind, and each needs an explicit hand-off:

- **#77 — the Prefect flow run.** Without this it keeps executing (orphaned
  GPU/LLM work). We reconstruct the flow-run name(s) for the cancelled run(s)
  via the same ``flow_run_name`` the executor wrote, find the still-running flow
  run(s), and transition them to CANCELLED so workers stop.
- **#529 — the run's focus leases.** Cancellation bypasses the executor's
  finalize path, so the cycle leases the run holds are never released. Post-#288
  that is a hard block: the next cycle recruiting any of those agents pauses at
  admission with ``focus_lease_conflict`` and needs manual SQL to clear.

Both are best-effort and never raise, so the cancel route reports the cycle/run
as cancelled even if Prefect is unreachable or no lease wiring exists (the
failure is logged).
"""

from __future__ import annotations

import logging

from squadops.api.runtime.deps import (
    get_focus_lease_port,
    get_runtime_coordinator,
    get_workflow_tracker,
)
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


async def release_cancelled_run_leases(cycle_id: str, run_ids: list[str]) -> int:
    """Release the focus leases held by the cancelled run(s). Returns how many cleared.

    Each run's leases are keyed by ``owner_ref = run_id`` (the executor's
    recruitment call), so the sweep needs nothing but the ids the route already
    has — which is the point: the agents a dead or cancelled run recruited are
    exactly what a caller *cannot* enumerate.

    Returns 0 when no coordinator/lease port is wired (a pool-less deployment
    has no leases to release).
    """
    coordinator = get_runtime_coordinator()
    focus_lease = get_focus_lease_port()
    if coordinator is None or focus_lease is None or not run_ids:
        return 0
    from squadops.runtime import reasons
    from squadops.runtime.lease_reaper import release_owner_leases

    released = 0
    for run_id in run_ids:
        try:
            released += await release_owner_leases(
                coordinator, focus_lease, run_id, reason_code=reasons.LEASE_STRANDED_AT_CANCEL
            )
        except Exception:
            logger.warning(
                "#529: focus-lease release failed for cancelled run %s", run_id, exc_info=True
            )
    if released:
        logger.info(
            "#529: released %d stranded focus lease(s) for cancelled cycle %s (runs=%s)",
            released,
            cycle_id,
            run_ids,
        )
    return released
