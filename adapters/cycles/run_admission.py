"""A run's admission — #1507 step 2 (docs/plans/1-9-0-completion-boundary-map.md).

The reserve-buffer guard and the focus-lease recruitment that ``execute_run`` runs between
planning and seeding, and the release its ``finally`` runs whatever the outcome — what admits a
participant also lets it go. Moved as found; the recruited ids are recorded on ``RunInProgress``
the moment admission returns them, so the release sees exactly who was recruited.

It borrows late (defended-bespoke-decisions §38), by the executor's own names.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

from adapters.cycles.execution_errors import _RecruitmentRejectedError
from adapters.cycles.run_provisioning import RunInProgress
from squadops.runtime import reasons
from squadops.runtime.admission import admit_participants, release_participants
from squadops.runtime.focus_reaper import release_owner_leases
from squadops.runtime.recruitment import reserve_buffer_decision

# The executor's logger name, not this module's: the sweep's warning is read by where it has always
# come from, and an extraction changes no line anyone reads.
logger = logging.getLogger("adapters.cycles.dispatched_flow_executor")


class RunAdmission:
    """Admits a run's participants before it seeds, and releases them when it ends."""

    #: What admission borrows from the executor, read at call time (§38).
    BORROWED = ("_assignment_port", "_coordinator", "_focus_lease_port")

    def __init__(self, *, executor: Callable[[], Any]) -> None:
        self._executor = executor

    def __getattr__(self, name: str) -> Any:
        if name in RunAdmission.BORROWED:
            return getattr(self._executor(), name)
        raise AttributeError(name)

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
