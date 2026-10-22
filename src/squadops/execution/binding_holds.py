"""A run held on a task's binding sections, and its release (SIP-0110 Appendix A §3.6; #2178).

A task whose task or project instructions can't be read or fitted is never dispatched on a partial
binding (§3.6). Its run is held where the binding failed, not failed: at provisioning, before its
first dispatch, since a run supplies every authoring task then (§5w), or where the loop dispatches
a task again or composes a repair. The run goes ``PAUSED``, the hold is recorded on it
(``Run.binding_holds``), and ``RUN_PAUSED`` carries it.

It is released by re-supply alone. The held step polls, as a gate does, and composes again; when
the binding is complete the hold is released with its cause, the run goes ``RUNNING`` and the step
carries on with what the re-supply composed. The cause is read from what held it:

- ``store_answered``: the store didn't answer, and now does;
- ``rebound``: only project instructions held, and the unit was re-bound (§5v) or the campaign
  cycle's own binding was filled (§5ad);
- ``instruction_changed``: a task instruction held, and was revised, narrowed or withdrawn (§5w).

A cancel releases it ``cancelled``. A Campaign cycle's hold is escalated through SIP-0109's queue
(§24bw, ``open_binding_hold``), and the Campaign's ruling bound may release it ``expired`` and
cancel the run. The release is the registry's compare-and-set, so exactly one of a re-supply, a
cancel and an expiry ends a hold.

A held run holds no box lease: it is ``PAUSED``, so not in flight (``runs_in_flight``), and a
supervisor may take the box while it waits. Its release is its start, so it waits on the box as a
run start does (``await_box``) before it dispatches anything.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import Any

from squadops.campaigns.binding_hold import open_binding_hold
from squadops.cycles.models import BindingHold, Cycle, HoldCause, HoldKind, RunStatus
from squadops.events.types import EventType
from squadops.execution.execution_errors import _CancellationError
from squadops.memory.context import SectionKind
from squadops.memory.task_instructions import TaskInstructionsUnavailable

logger = logging.getLogger(__name__)

#: How often a held step composes again, as a gate's poll reads its decision.
HOLD_POLL_S = 5.0

#: The launcher's fill of a campaign cycle's own bindings (§5ad), by cycle id.
BindingFill = Callable[[str], Awaitable[Any]]


async def held_or_supplied[T](
    hold: Callable[..., Awaitable[T]] | None,
    run_id: str,
    cycle: Cycle,
    supply: Callable[[], Awaitable[T]],
) -> T:
    """``supply()`` through the executor's hold (``BindingHolds.supplied``). A collaborator built
    outside an executor has none: there is no run to hold, and an incomplete binding raises."""
    if hold is None:
        return await supply()
    return await hold(run_id, cycle, supply)


def release_cause(hold: BindingHold) -> HoldCause:
    """What released ``hold``, read from what held it: the store, when it failed any record (as
    the Campaign's expiry reads its class); a re-binding, when only project instructions held;
    otherwise a change to the task instruction, which a held task instruction always needs and
    which a project instruction it crowded out of the budget needs too."""
    if any(kind == HoldKind.STORE for _, _, kind in hold.unresolved):
        return HoldCause.STORE_ANSWERED
    if set(hold.sections) == {SectionKind.PROJECT_INSTRUCTIONS.value}:
        return HoldCause.REBOUND
    return HoldCause.INSTRUCTION_CHANGED


def _identity(task_id: str, unresolved: tuple[tuple[str, str, str], ...]) -> tuple:
    """What a hold is on: the task and each record with its kind. A reason's wording (a token
    count) may change while the same records hold the same task."""
    return task_id, tuple((ref, str(kind)) for ref, _, kind in unresolved)


class BindingHolds:
    """The held step: hold the run, poll, re-supply, release."""

    def __init__(
        self,
        *,
        cycle_registry: Any,
        campaign_registry: Any,
        event_bus: Any,
        is_cancelled: Callable[[str], Awaitable[bool]],
        await_box: Callable[[str, str], Awaitable[None]],
        fill: BindingFill | None,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
        poll_s: float = HOLD_POLL_S,
    ) -> None:
        self._cycles = cycle_registry
        self._campaigns = campaign_registry
        self._events = event_bus
        self._is_cancelled = is_cancelled
        self._await_box = await_box
        #: §5ad: the launcher's fill of a campaign cycle's own bindings, the one binder. ``None``
        #: where no launcher runs: a standalone cycle binds at its admission alone.
        self._fill = fill
        self._clock = clock
        self._poll_s = poll_s

    async def supplied[T](self, run_id: str, cycle: Cycle, supply: Callable[[], Awaitable[T]]) -> T:
        """``supply()``'s answer once every binding section it composes is complete, holding the
        run until then. A run resumed while held re-enters here, and the supply that completes
        releases its hold."""
        try:
            answer = await supply()
        except TaskInstructionsUnavailable as held:
            return await self._held(run_id, cycle, supply, held)
        reentered = (await self._cycles.get_run(run_id)).open_hold
        if reentered is not None:
            await self._release(run_id, reentered)
        return answer

    async def _held[T](
        self,
        run_id: str,
        cycle: Cycle,
        supply: Callable[[], Awaitable[T]],
        held: TaskInstructionsUnavailable,
    ) -> T:
        hold = await self._hold(run_id, cycle, held)
        while True:
            await asyncio.sleep(self._poll_s)
            if await self._is_cancelled(run_id):
                await self._cycles.release_binding_hold(
                    run_id, hold.hold_id, released_at=self._clock(), cause=HoldCause.CANCELLED
                )
                raise _CancellationError(run_id)
            current = (await self._cycles.get_run(run_id)).open_hold
            if current is None or current.hold_id != hold.hold_id:
                # Released by the Campaign's ruling bound, which cancels the run next.
                continue
            await self._filled(cycle)
            try:
                answer = await supply()
            except TaskInstructionsUnavailable as again:
                if _identity(again.task_id, again.unresolved) != _identity(
                    hold.task_id, hold.unresolved
                ) and await self._release(run_id, hold):
                    # What held it was answered, and something else holds the run now.
                    hold = await self._hold(run_id, cycle, again)
                continue
            if not await self._release(run_id, hold):
                continue  # the ruling bound released it first: the run is cancelled next
            await self._cycles.update_run_status(run_id, RunStatus.RUNNING)
            self._events.emit(
                EventType.RUN_RESUMED,
                entity_type="run",
                entity_id=run_id,
                context={"cycle_id": cycle.cycle_id, "run_id": run_id},
                payload={"binding_hold": hold.hold_id, "cause": str(release_cause(hold))},
            )
            await self._await_box(run_id, cycle.cycle_id)
            return answer

    async def _hold(
        self, run_id: str, cycle: Cycle, held: TaskInstructionsUnavailable
    ) -> BindingHold:
        """Record the hold (or find the one a resumed run re-enters), pause the run, say why, and
        escalate a Campaign cycle's."""
        run = await self._cycles.get_run(run_id)
        hold = run.open_hold
        if hold is None or _identity(hold.task_id, hold.unresolved) != _identity(
            held.task_id, held.unresolved
        ):
            if hold is not None:
                await self._release(run_id, hold)
            hold = BindingHold(
                hold_id=f"hold_{len(run.binding_holds) + 1}",
                task_id=held.task_id,
                task_type=held.task_type,
                unresolved=held.unresolved,
                held_at=self._clock(),
                sections=held.sections,
            )
            await self._cycles.record_binding_hold(run_id, hold)
        if run.status != RunStatus.PAUSED.value:
            await self._cycles.update_run_status(run_id, RunStatus.PAUSED)
        self._events.emit(
            EventType.RUN_PAUSED,
            entity_type="run",
            entity_id=run_id,
            context={"cycle_id": cycle.cycle_id, "run_id": run_id},
            payload={
                "binding_hold": {
                    "hold_id": hold.hold_id,
                    "task_id": hold.task_id,
                    "task_type": hold.task_type,
                    "unresolved": [
                        {"ref": ref, "reason": reason, "kind": str(kind)}
                        for ref, reason, kind in hold.unresolved
                    ],
                }
            },
        )
        logger.warning("run_held_on_binding run=%s hold=%s: %s", run_id, hold.hold_id, held)
        if self._campaigns is not None:
            try:
                await open_binding_hold(self._campaigns, cycle, run_id, hold, self._clock())
            except Exception:
                # The run stays held either way: its record and its poll don't need the queue.
                logger.exception(
                    "binding_hold_escalation_not_opened run=%s hold=%s", run_id, hold.hold_id
                )
        return hold

    async def _release(self, run_id: str, hold: BindingHold) -> bool:
        cause = release_cause(hold)
        landed = await self._cycles.release_binding_hold(
            run_id, hold.hold_id, released_at=self._clock(), cause=cause
        )
        logger.info(
            "run_binding_hold_released run=%s hold=%s cause=%s landed=%s",
            run_id,
            hold.hold_id,
            cause,
            landed,
        )
        return landed

    async def _filled(self, cycle: Cycle) -> None:
        """A campaign cycle's missing bindings filled by the launcher's own fill (§5ad), so a
        release never waits on the next sweep and binds exactly as the launch would have."""
        if self._fill is None or not cycle.campaign_id:
            return
        try:
            await self._fill(cycle.cycle_id)
        except Exception:
            logger.warning("binding_hold_fill_failed cycle=%s", cycle.cycle_id, exc_info=True)
