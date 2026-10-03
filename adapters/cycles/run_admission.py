"""A run's admission — #1507 step 2 (docs/plans/1-9-0-completion-boundary-map.md).

The reserve-buffer guard and the focus-lease recruitment that ``execute_run`` runs between
planning and seeding, and the release its ``finally`` runs whatever the outcome — what admits a
participant also lets it go. Moved as found; the recruited ids are recorded on ``RunInProgress``
the moment admission returns them, so the release sees exactly who was recruited.

It borrows late (defended-bespoke-decisions §38), by the executor's own names.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

from adapters.cycles.execution_errors import _ExecutionError, _RecruitmentRejectedError
from adapters.cycles.run_provisioning import RunInProgress
from squadops.runtime import reasons
from squadops.runtime.admission import admit_participants, release_participants
from squadops.runtime.focus_reaper import release_owner_leases
from squadops.runtime.recruitment import reserve_buffer_decision

# The executor's logger name, not this module's: the sweep's warning is read by where it has always
# come from, and an extraction changes no line anyone reads.
logger = logging.getLogger("adapters.cycles.dispatched_flow_executor")

#: How often a run waiting for the box reads the lease again (SIP-0109 §9.3; #1802).
BOX_POLL_S = 15.0


class RunAdmission:
    """Admits a run's participants before it seeds, and releases them when it ends."""

    #: What admission borrows from the executor, read at call time (§38).
    BORROWED = ("_assignment_port", "_coordinator", "_focus_lease_port", "_campaign_registry")

    def __init__(self, *, executor: Callable[[], Any]) -> None:
        self._executor = executor

    def __getattr__(self, name: str) -> Any:
        if name in RunAdmission.BORROWED:
            return getattr(self._executor(), name)
        raise AttributeError(name)

    async def await_box(self, run_id: str) -> None:
        """SIP-0109 §9.3 (#1802): a run does not start while the supervisor holds the box.

        It waits, still queued, reading the lease every ``BOX_POLL_S``, and starts once the
        lease is released or has expired. A wait, not a failure (§24l), so an approval granted
        while the supervisor held the box does not become a dead increment. Its ceiling is the
        holding campaign's ``owner_ruling_bound_s``, the longest any ruling may take: a lease
        renewed past it fails the run with the reason. An executor with no campaign registry
        has no lease to read.
        """
        registry = self._campaign_registry
        if registry is None:
            return
        started: datetime | None = None
        bound_s = 0.0
        while True:
            lease = await registry.box_lease()
            now = datetime.now(UTC)
            if lease is None or not lease.supervisor_holds(now):
                if started is not None:
                    logger.info(
                        "run_start_box_free run=%s waited_s=%.0f",
                        run_id,
                        (now - started).total_seconds(),
                    )
                return
            if started is None:
                started = now
                if lease.campaign_id:
                    campaign = await registry.get_campaign(lease.campaign_id)
                    bound_s = float(campaign.policy.owner_ruling_bound_s)
                logger.warning(
                    "run_start_waiting_for_box run=%s held_by=%s campaign=%s until=%s bound_s=%.0f",
                    run_id,
                    lease.held_by,
                    lease.campaign_id,
                    lease.expires_at,
                    bound_s,
                )
            if (now - started).total_seconds() >= bound_s:
                raise _ExecutionError(
                    f"run {run_id} waited {bound_s:.0f}s for the box, the holding campaign's "
                    f"owner ruling bound, and the supervisor ({lease.held_by}) still holds it "
                    f"(SIP-0109 §9.3)"
                )
            await asyncio.sleep(BOX_POLL_S)

    async def admit(
        self, state: RunInProgress, participating_agent_ids: set[str], run_id: str
    ) -> None:
        # SIP-0089 §2.5: reserve-buffer guard. The plan now names every
        # agent this run would recruit. If one is committed to — or about to
        # start — a hard duty window (§11.4), defer the run rather than pull
        # the agent into cycle work. Opt-in: skipped when no AssignmentPort
        # is wired. Decision is pure (time-injected) and lives in the runtime
        # domain; we only enforce it here.
        if self._assignment_port is not None:
            guard_now = datetime.now(UTC)
            active_assignments = await self._assignment_port.list_active_assignments(guard_now)
            decision = reserve_buffer_decision(
                active_assignments,
                participating_agent_ids,
                guard_now,
            )
            if not decision.allowed:
                raise _RecruitmentRejectedError(decision.blocking_agent_id, decision.reason)

        # SIP-0089 §3.5 (#233): having cleared the reserve-buffer guard, route
        # recruitment through the coordinator — each participant transitions
        # ambient→cycle, acquiring its cycle FocusLease (§3.4). A lease
        # conflict is a deferral, not a failure: it rides the same
        # _RecruitmentRejectedError → RUN_PAUSED path with a typed focus_lease_*
        # reason (no new EventType). admission rolls back any agents it already
        # recruited before deferring, so a paused run strands no one in cycle.
        # Opt-in: skipped when no coordinator is wired (§2.5-only fallback).
        if self._coordinator is not None:
            admission = await admit_participants(
                self._coordinator,
                participating_agent_ids,
                owner_ref=run_id,
            )
            if not admission.admitted:
                raise _RecruitmentRejectedError(admission.blocking_agent_id, admission.reason)
            state.recruited_agent_ids = admission.recruited_agent_ids

    async def release(self, run_id: str, recruited_agent_ids: tuple[str, ...]) -> None:
        # SIP-0089 §3.5 (#233): release the cycle leases this run acquired,
        # whatever the outcome (completed/failed/paused/cancelled). Best-effort
        # and isolated per agent — a stranded cycle lease would block all of an
        # agent's future recruitment, so this must run before anything that can
        # raise. Empty (and skipped) when the run recruited no one.
        if self._coordinator is not None and recruited_agent_ids:
            await release_participants(self._coordinator, recruited_agent_ids, owner_ref=run_id)
        # #373: then sweep anything still held under this run's owner_ref.
        # `recruited_agent_ids` records only the agents *this* admission call
        # transitioned; a recruitment replay (#288 idempotent-skip on a
        # resumed run) leaves leases owned by this run that the release above
        # cannot see. Best-effort — a sweep failure must not mask the run's
        # own outcome.
        if self._coordinator is not None and self._focus_lease_port is not None:
            try:
                await release_owner_leases(
                    self._coordinator,
                    self._focus_lease_port,
                    run_id,
                    reason_code=reasons.LEASE_STRANDED_AT_RUN_FINALIZE,
                )
            except Exception:
                logger.warning("Stranded-lease sweep failed for run %s", run_id, exc_info=True)
