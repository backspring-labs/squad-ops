"""
In-process duty transition scheduler (SIP-0089 §2.4).

A polling scheduler that opens and closes duty windows by **requesting**
transitions through the `RuntimeCoordinator`. Per D21 it is a *claimant, not an
authority*: it reads assignments and agent state but never writes
`AgentRuntimeState` directly — only the coordinator does.

Per-tick, for each active **duty** assignment:
- `window_state == active` and the agent is not yet on duty for it → open the
  window (on time → `duty_window_opened`; late → governed by `MissedWindowPolicy`);
- agent on duty for it and `window_state ∈ {in_reserve_after, closed}` → close it
  (`duty_window_closed`);
- `window_state == missed` (window ended, never entered) → enact the policy
  (skip → `assignment.window.skipped`; review → `assignment.window.review_required`).

Idempotency (D12/D21): open requests carry `scheduled_at = window_start` and
close requests `scheduled_at = window_end`, so the coordinator dedupes repeated
ticks within the same window.

Lifecycle: construction does nothing. `start()` launches the poll loop; bootstrap
calls it **only when `runtime.scheduler.enabled`**. It must not auto-start — unit
tests drive `tick()` directly. The v1.3 Temporal scheduler (SIP-0091) will sit
behind the same seam.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
from collections.abc import Callable
from datetime import UTC, datetime, timedelta

from squadops.ports.runtime.assignments import AssignmentPort
from squadops.ports.runtime.event_publisher import RuntimeEventPublisher
from squadops.ports.runtime.state import RuntimeStatePort
from squadops.runtime import events, reasons
from squadops.runtime.coordinator import RuntimeCoordinator, TransitionOutcome
from squadops.runtime.models import Assignment, window_state

logger = logging.getLogger(__name__)

# Config: runtime.scheduler.poll_interval_seconds (default 30); the scheduler is
# constructed/started by bootstrap only when runtime.scheduler.enabled is true.
_DEFAULT_POLL_INTERVAL_SECONDS = 30.0


class DutyScheduler:
    """Polls duty assignments and requests window-open/close transitions."""

    def __init__(
        self,
        assignments: AssignmentPort,
        coordinator: RuntimeCoordinator,
        state: RuntimeStatePort,
        *,
        events_publisher: RuntimeEventPublisher | None = None,
        poll_interval_seconds: float = _DEFAULT_POLL_INTERVAL_SECONDS,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._assignments = assignments
        self._coordinator = coordinator
        self._state = state
        self._events = events_publisher
        self._poll_interval_seconds = poll_interval_seconds
        self._clock = clock or (lambda: datetime.now(UTC))
        self._task: asyncio.Task | None = None

    async def tick(self, now: datetime | None = None) -> list[TransitionOutcome]:
        """Evaluate all active duty assignments once. Returns transitions requested."""
        at = now if now is not None else self._clock()
        outcomes: list[TransitionOutcome] = []
        for assignment in await self._assignments.list_active_assignments(at):
            if assignment.assignment_type != "duty":
                continue  # reserve / cycle_eligibility don't drive mode transitions
            outcome = await self._evaluate(assignment, at)
            if outcome is not None:
                outcomes.append(outcome)
        return outcomes

    async def _evaluate(self, a: Assignment, now: datetime) -> TransitionOutcome | None:
        state = await self._state.get_state(a.agent_id)
        in_duty = (
            state is not None
            and state.mode == "duty"
            and state.current_assignment_ref == a.assignment_id
        )
        st = window_state(a, now, entered_active=in_duty)

        if st == "active":
            if in_duty:
                return None  # already serving this window
            late = now - a.active_window.start
            if late <= timedelta(0):
                return await self._open(a, reasons.DUTY_WINDOW_OPENED)
            return await self._open_late(a, late)

        if st in ("in_reserve_after", "closed"):
            # window_state only yields these when in_duty is True (entered_active),
            # so this is the close path for an agent currently serving the window.
            return await self._close(a)

        if st == "missed":
            self._enact_missed(a)
            return None

        return None  # before_window / in_reserve_before — reserve is §2.5's concern

    async def _open(self, a: Assignment, reason: str) -> TransitionOutcome:
        return await self._coordinator.request_transition(
            a.agent_id,
            "duty",
            reason,
            requester_kind="scheduler",
            owner_ref=a.assignment_id,
            assignment_id=a.assignment_id,
            scheduled_at=a.active_window.start,
        )

    async def _open_late(self, a: Assignment, late: timedelta) -> TransitionOutcome | None:
        policy = a.missed_window_policy
        if policy == "require_operator_review":
            self._emit_review(a)
            return None
        if policy == "start_late_within_grace" and late <= a.graceful_window:
            return await self._open(a, reasons.DUTY_WINDOW_STARTED_LATE)
        # 'skip', or 'start_late_within_grace' past the grace window.
        self._emit_skipped(a)
        return None

    async def _close(self, a: Assignment) -> TransitionOutcome:
        return await self._coordinator.request_transition(
            a.agent_id,
            "ambient",
            reasons.DUTY_WINDOW_CLOSED,
            requester_kind="scheduler",
            owner_ref=a.assignment_id,
            assignment_id=a.assignment_id,
            scheduled_at=a.active_window.end,
        )

    def _enact_missed(self, a: Assignment) -> None:
        if a.missed_window_policy == "require_operator_review":
            self._emit_review(a)
        else:
            self._emit_skipped(a)

    def _emit_skipped(self, a: Assignment) -> None:
        if self._events is not None:
            self._events.emit(
                events.ASSIGNMENT_WINDOW_SKIPPED,
                agent_id=a.agent_id,
                reason_code=reasons.DUTY_WINDOW_MISSED,
                payload={"assignment_id": a.assignment_id},
            )

    def _emit_review(self, a: Assignment) -> None:
        if self._events is not None:
            self._events.emit(
                events.ASSIGNMENT_WINDOW_REVIEW_REQUIRED,
                agent_id=a.agent_id,
                reason_code=reasons.DUTY_WINDOW_MISSED_OPERATOR_REVIEW,
                payload={"assignment_id": a.assignment_id},
            )

    # -- poll loop (started by bootstrap only when enabled) --

    async def start(self) -> None:
        """Launch the background poll loop. Idempotent."""
        if self._task is None:
            self._task = asyncio.create_task(self._run())

    async def stop(self) -> None:
        """Cancel the poll loop and await its clean shutdown."""
        if self._task is not None:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task
            self._task = None

    async def _run(self) -> None:
        while True:
            try:
                await self.tick()
            except Exception:  # one bad tick must not kill the loop
                logger.exception("duty scheduler tick failed")
            await asyncio.sleep(self._poll_interval_seconds)
