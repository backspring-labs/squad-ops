"""Startup hygiene sweeps for state a dead process left active (#373, #672).

Composition-root helper, kept out of ``main.py`` for the same reason
``scheduler_bootstrap`` is: the wiring gate and the terminal predicate are then
unit-testable without standing up FastAPI, and the composition root keeps one
generic call per sweep instead of an inline block per issue.

Both sweeps close the same class of bug — an interrupted run leaves a row
*active* with no owner left to terminalize it, and the uniqueness rules that
make the runtime correct (§3.2 one lease per agent, §4.2 one activity per agent)
then turn that residue into a hard block on every later run:

- :func:`reap_stranded_leases` (#373) — a held cycle lease makes recruitment
  reject with ``focus_lease_conflict``, so the next cycle pauses before
  dispatching a task.
- :func:`reap_stranded_cycle_modes` (#710) — the inverse residue: `cycle` mode
  with *no* lease, which the lease sweep structurally cannot see. Recruitment
  then idempotent-skips forever and focus arbitration is off entirely.
- :func:`reap_stranded_activities` (#672) — an active activity trips
  ``uq_runtime_activities_one_active_per_agent``, so activity tracking goes
  silently dead for that agent.

Each owns its own best-effort contract: a reap failure is logged and never
blocks startup, because a runtime-api that will not boot is worse than one that
boots with residue.

The domain reapers (``runtime.focus_reaper`` / ``runtime.activity_reaper``) stay
free of cycle-domain imports (D26); the "is the owner finished?" question is
answered here, where the registry is already in scope.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from squadops.ports.cycles.cycle_registry import CycleRegistryPort
    from squadops.ports.runtime.activity import RuntimeActivityPort
    from squadops.ports.runtime.focus_lease import FocusLeasePort
    from squadops.ports.runtime.state import RuntimeStatePort
    from squadops.runtime.coordinator import RuntimeCoordinator

logger = logging.getLogger(__name__)


async def reap_stranded_leases(
    cycle_registry: CycleRegistryPort,
    coordinator: RuntimeCoordinator | None,
    focus_lease_port: FocusLeasePort | None,
) -> int:
    """Release every held cycle focus lease at startup (#373).

    Returns how many cleared; 0 when the sweep is unwired (no Postgres pool) or
    the reap failed.

    **Every** held lease is orphaned here, not just the terminal-owned ones. Runs
    execute in this process (the executor dispatches from inside runtime-api), so
    a process that has not begun serving owns no in-flight run — and the
    deployment is single-instance by construction, the same constraint the
    coordinator's single-writer rule already depends on (see
    ``scheduler_bootstrap``). Sparing a lease whose run still reads ``running``
    would miss #373's own evidence: a SIGKILL leaves the run row non-terminal
    forever, so the leases under it would never clear and the manual-SQL recovery
    would stay mandatory for exactly the case the issue was filed about.

    The run lookup therefore informs the *log*, not the decision — a lease under
    a non-terminal run says the previous process died mid-run, which is worth
    stating out loud. #373's complaint was that this failed silently.
    """
    if coordinator is None or focus_lease_port is None:
        return 0
    try:
        from squadops.cycles.lifecycle import TERMINAL_STATES
        from squadops.cycles.models import RunNotFoundError, RunStatus
        from squadops.runtime import reasons
        from squadops.runtime.focus_reaper import reap_stale_leases

        async def _owner_cannot_be_executing(run_id: str) -> bool:
            try:
                owning_run = await cycle_registry.get_run(run_id)
            except RunNotFoundError:
                logger.warning("Releasing focus lease held by unknown run %s", run_id)
                return True
            if RunStatus(owning_run.status) not in TERMINAL_STATES:
                logger.warning(
                    "Releasing focus lease held by run %s still marked %r — no run "
                    "can be executing at startup, so its executor died mid-run and "
                    "the run status is stale.",
                    run_id,
                    owning_run.status,
                )
            return True

        released = await reap_stale_leases(
            coordinator,
            focus_lease_port,
            owner_is_finished=_owner_cannot_be_executing,
            reason_code=reasons.LEASE_STRANDED_AT_STARTUP,
        )
        if released:
            logger.info("Startup reap released %d stranded focus lease(s)", released)
        return released
    except Exception:
        logger.warning("Startup stranded-lease reap failed", exc_info=True)
        return 0


async def reap_stranded_modes(
    coordinator: RuntimeCoordinator | None,
    state_port: RuntimeStatePort | None,
) -> int:
    """Return every agent left in `cycle` mode to `ambient` at startup (#710).

    Returns how many moved; 0 when unwired or the reap failed.

    Runs *after* :func:`reap_stranded_leases`, which already returns the agents
    it clears — so what remains here is the residue with no lease at all, the
    state that made focus arbitration silently inert for 64 cycles. Same
    justification as the other two sweeps: nothing dispatches in a process that
    has not begun serving, so no agent can legitimately hold cycle focus yet.
    """
    if coordinator is None or state_port is None:
        return 0
    try:
        from squadops.runtime.focus_reaper import reap_stranded_cycle_modes

        reaped = await reap_stranded_cycle_modes(coordinator, state_port)
        if reaped:
            logger.warning(
                "Startup reap returned %d agent(s) from a stranded cycle mode to ambient — "
                "recruitment had been idempotent-skipping them, so no focus lease was being "
                "acquired at all.",
                reaped,
            )
        return reaped
    except Exception:
        logger.warning("Startup stranded-mode reap failed", exc_info=True)
        return 0


async def reap_stranded_activities(
    cycle_registry: CycleRegistryPort,
    activity_port: RuntimeActivityPort | None,
) -> int:
    """End every active runtime activity at startup (#672, #561).

    Returns how many ended; 0 when unwired or the reap failed.

    Same reasoning as :func:`reap_stranded_leases`, and the same correction: a
    cycle whose runs were killed mid-flight derives as ACTIVE forever, so gating
    on a terminal cycle status spared exactly the rows a crash strands — #561's
    live evidence was four agents with one open row each, two of them dead for
    three days. Nothing dispatches in a process that has not begun serving, so
    every active row here is residue. The cycle status is looked up for the
    *log*, not the decision.
    """
    if activity_port is None:
        return 0
    try:
        from squadops.cycles.lifecycle import derive_cycle_status
        from squadops.cycles.models import CycleNotFoundError, CycleStatus
        from squadops.runtime.activity_reaper import reap_stale_activities

        async def _owner_cannot_be_dispatching(cycle_id: str | None) -> bool:
            if cycle_id is None:
                # A duty/ambient row has no cycle to consult. Sparing it is what
                # left #561's residue unreachable by any sweep.
                logger.warning("Ending stranded activity with no owning cycle")
                return True
            try:
                owning_cycle = await cycle_registry.get_cycle(cycle_id)
            except CycleNotFoundError:
                logger.warning("Ending stranded activity of unknown cycle %s", cycle_id)
                return True
            runs = await cycle_registry.list_runs(cycle_id)
            derived = derive_cycle_status(runs, cycle_cancelled=owning_cycle.cancelled)
            if derived not in (CycleStatus.COMPLETED, CycleStatus.FAILED, CycleStatus.CANCELLED):
                logger.warning(
                    "Ending stranded activity of cycle %s still deriving as %s — nothing "
                    "dispatches at startup, so its executor died mid-task.",
                    cycle_id,
                    derived.value,
                )
            return True

        reaped = await reap_stale_activities(
            activity_port, owner_is_finished=_owner_cannot_be_dispatching
        )
        if reaped:
            logger.info("Startup reap ended %d stranded runtime activity row(s)", reaped)
        return reaped
    except Exception:
        logger.warning("Startup stranded-activity reap failed", exc_info=True)
        return 0
