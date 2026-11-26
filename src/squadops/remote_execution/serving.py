"""The worker's loop: register, claim, run, renew, submit (SIP-0117 R3.3, R5.4, R5.5).

A worker is one process on the machine that hosts a tool. It calls the runtime through
``WorkerApiPort`` and the tool through ``OperationRunnerPort``, and holds at most one claim.

What it does with each thing that can happen while it holds a claim:

- **the operation ends:** its result is submitted, and submitted again while the runtime can't
  be reached and the lease is still held, for one lease's length at most. Submitting twice is
  safe: the runtime answers the same claim's accepted result as accepted.
- **a cancel, seen at a renewal:** the operation is stopped, the tool reset, and ``interrupted``
  submitted (R3.3).
- **the claim is no longer held** (the lease ran out, or a renewal is refused): the operation
  is stopped and the tool reset. Nothing is submitted, since the runtime would refuse it.
- **the operation ended while a renewal was out** (#3185): its result is submitted whatever the
  renewal answered. The tool ran to a returned result, so its state is known and it isn't
  reset, then or when the next claim says "reconcile first". A claim the runtime had already
  given up refuses the result and records the refusal, which is the runtime's record that a
  finished result arrived late.
- **the runtime can't be reached:** the operation keeps running and the renewal is tried again
  at the next interval, until the lease's last known expiry. Then the claim is no longer held.
- **the runtime no longer knows the session:** the operation is stopped, the tool reset, and
  the worker registers again.
- **the tool raises:** ``interrupted`` is submitted with what it raised, since it had started.
- **the worker is stopped:** the operation is stopped and nothing is submitted. The lease runs
  out, and the operation is queued again while it has an attempt left.

**The tool's state is the worker's to know.** After any ending but a returned result the tool
is reset before it runs again. When the reset fails, the next operation is answered
``not_executed`` with why, and the reset is tried again at the claim after.

**The tool is probed only between claims** (#3185). ``OperationRunnerPort.health`` asks whether
the tool can run an operation now, and a tool that is running one can't be asked without
reaching into it. A renewal carries the health as last read between claims, and nothing the
tool does can hold a renewal back: the lease is the runtime's only sign that the operation is
still held. The heartbeat between claims still waits on its probe, which holds no lease.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from contextlib import suppress
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

from squadops.remote_execution.models import (
    OperationStatus,
    RemoteOperationResult,
    evidence_size_defects,
)
from squadops.remote_execution.workers import (
    Claim,
    Enrolment,
    Fence,
    LeaseReading,
    RuntimeAnswerUnreadable,
    RuntimeUnreachable,
    UnknownSession,
    WorkerRegistration,
    WorkerStatus,
)

if TYPE_CHECKING:
    from squadops.ports.remote_execution import OperationRunnerPort, WorkerApiPort
    from squadops.runtime.models import RuntimeStatus

logger = logging.getLogger(__name__)

#: How long the worker waits before it asks again: for work when it holds none, and for the
#: runtime when it can't be reached.
IDLE_POLL = timedelta(seconds=3)

REASON_CANCELLED = "cancelled while the operation was running"


def _utc_now() -> datetime:
    return datetime.now(UTC)


class Worker:
    def __init__(
        self,
        api: WorkerApiPort,
        runner: OperationRunnerPort,
        *,
        worker_id: str,
        platform: str,
        clock: Callable[[], datetime] = _utc_now,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
        idle_poll: timedelta = IDLE_POLL,
        runtime_api_url: str = "",
        report: Callable[[WorkerStatus], None] | None = None,
    ) -> None:
        self._api = api
        self._runner = runner
        self._worker_id = worker_id
        self._platform = platform
        self._clock = clock
        self._sleep = sleep
        self._idle_poll = idle_poll.total_seconds()
        #: Why the tool's state is unknown, or ``None`` when it is known.
        self._unknown_state: str | None = None
        #: The tool was reset and has run nothing since.
        self._fresh = False
        #: The tool's last run ended with a result it returned, so what it left is known (#3185).
        self._returned = False
        #: The tool's health as last read between claims: what a renewal reports (#3185).
        self._health: RuntimeStatus | None = None
        #: Where the worker's own status goes (#3046), and what it is.
        self._report = report
        self._status = WorkerStatus(self._worker_id, runtime_api_url, clock())

    async def serve(self) -> None:
        """Serve until the call is cancelled. ``WorkerRefused`` and ``RuntimeAnswerUnreadable``
        end it: trying again would change neither.

        The tool is reset first, before the worker registers (#3046): what an earlier process
        left in it is unknown, and a worker whose tool isn't up is offline, so nothing would be
        queued for it to claim. A reset that fails is tried again at each claim, as after any
        other unknown state."""
        self._unknown_state = "the worker has just started, and its tool's state is unknown"
        await self._reset()
        while True:
            enrolment = await self._enrol()
            try:
                await self._serve_session(enrolment)
            except UnknownSession:
                logger.warning(
                    "the runtime has no live session %s for worker %s: another process "
                    "registered under this worker id, or the registry was cleared. "
                    "Registering again",
                    enrolment.session_id,
                    self._worker_id,
                )
                await self._sleep(self._idle_poll)

    # ------------------------------------------------------------------ a session

    async def _enrol(self) -> Enrolment:
        registration = WorkerRegistration(
            worker_id=self._worker_id,
            platform=self._platform,
            tool_versions=dict(await self._runner.tool_versions()),
            operations=tuple(self._runner.serves()),
        )
        while True:
            try:
                enrolment = await self._api.register(registration)
            except RuntimeUnreachable as e:
                logger.warning("worker %s can't register yet: %s", self._worker_id, e)
                self._unreachable(e)
                await self._sleep(self._idle_poll)
                continue
            now = self._clock()
            self._record(session_id=enrolment.session_id, registered_at=now, last_answer_at=now)
            logger.info(
                "worker %s registered as session %s, serving %s",
                self._worker_id,
                enrolment.session_id,
                ", ".join(f"{o.provider}/{o.operation}" for o in registration.operations),
            )
            return enrolment

    async def _serve_session(self, enrolment: Enrolment) -> None:
        heartbeat_due = self._clock()
        while True:
            claim: Claim | None = None
            try:
                if self._clock() >= heartbeat_due:
                    self._health = await self._runner.health()
                    await self._api.heartbeat(enrolment.session_id, self._health)
                    heartbeat_due = self._clock() + enrolment.heartbeat
                    self._record(last_answer_at=self._clock())
                claim = await self._api.claim(enrolment.session_id)
            except RuntimeUnreachable as e:
                logger.warning("worker %s can't reach the runtime: %s", self._worker_id, e)
                self._unreachable(e)
            if claim is None:
                await self._sleep(self._idle_poll)
                continue
            await self._serve_claim(enrolment, claim)
            heartbeat_due = self._clock()

    # ------------------------------------------------------------------ a claim

    async def _serve_claim(self, enrolment: Enrolment, claim: Claim) -> None:
        fence, request = claim.fence, claim.request
        logger.info(
            "claimed operation %s attempt %s (%s/%s)",
            fence.operation_id,
            fence.attempt,
            request.provider,
            request.operation,
        )
        unready = await self._unready_for(claim)
        if unready is not None:
            await self._deliver(enrolment, fence, claim.lease_expires_at, unready)
            return
        self._fresh = False
        self._returned = False
        task = asyncio.ensure_future(self._runner.run(request))
        try:
            result, expires = await self._watch(enrolment, claim, task)
        finally:
            if not task.done():
                # The worker is being stopped, or something above raised: nothing is left
                # running on the tool, and its state is unknown to whatever runs next.
                self._unknown_state = "the operation was stopped with the worker"
                await _stop(task)
        if result is not None:
            await self._deliver(enrolment, fence, expires, result)

    async def _unready_for(self, claim: Claim) -> RemoteOperationResult | None:
        """Reset the tool when its state is unknown. Returns the ``not_executed`` to answer the
        claim with when it can't be reset, or ``None`` when the tool is ready."""
        known = self._fresh or self._returned
        if claim.reconcile_first and not known and self._unknown_state is None:
            # The runtime never took the last attempt's result. A tool that returned one has
            # nothing to reconcile (R5.5 rule 3: reset after any ending but a returned result).
            self._unknown_state = "this worker's last attempt ended with no result"
        if self._unknown_state is None:
            return None
        failure = await self._reset()
        if failure is None:
            return None
        return RemoteOperationResult(
            status=OperationStatus.NOT_EXECUTED,
            reason=f"the worker's tool could not be reset ({self._unknown_state}): {failure}",
            dispatch_id=claim.request.dispatch_id,
            # #3192: the worker's own tool, never the request: nothing ran.
            tool_unready=True,
        )

    async def _watch(
        self, enrolment: Enrolment, claim: Claim, task: asyncio.Future
    ) -> tuple[RemoteOperationResult | None, datetime]:
        """Renew the lease until the operation ends. Returns the result to submit, or ``None``
        when the claim is no longer held, with the lease's last known expiry."""
        fence = claim.fence
        expires = claim.lease_expires_at
        while True:
            await self._wait(task, enrolment.heartbeat.total_seconds())
            if task.done():
                return await self._result_of(task, claim.request.dispatch_id), expires
            try:
                lease = await self._api.renew(enrolment.session_id, self._health_held(), fence)
                self._record(last_answer_at=self._clock())
            except RuntimeUnreachable as e:
                self._unreachable(e)
                if task.done():
                    return await self._result_of(task, claim.request.dispatch_id), expires
                if self._clock() < expires:
                    logger.warning("the lease was not renewed, and will be tried again: %s", e)
                    continue
                await self._abandon(
                    task,
                    f"the lease on operation {fence.operation_id} ran out at "
                    f"{expires.isoformat(timespec='seconds')} with the runtime unreachable ({e})",
                )
                return None, expires
            except UnknownSession:
                await self._abandon(task, "the runtime ended this worker's session")
                raise
            if task.done():
                # The operation ended while the renewal was out. Its result is what there is
                # to say, whatever the renewal answered: a refused claim refuses the result
                # and records that, and the tool, having returned, isn't reset.
                if lease.refusal is not None:
                    logger.warning(
                        "operation %s ended while its renewal was out, and the runtime no "
                        "longer holds it for this claim (%s). Its result is submitted for "
                        "the runtime to record",
                        fence.operation_id,
                        lease.refusal.value,
                    )
                else:
                    expires = _expiry(lease)
                return await self._result_of(task, claim.request.dispatch_id), expires
            if lease.refusal is not None:
                await self._abandon(
                    task,
                    f"the runtime no longer holds operation {fence.operation_id} for this "
                    f"claim ({lease.refusal.value})",
                )
                return None, expires
            expires = _expiry(lease)
            if lease.cancel_requested:
                return await self._cancelled(task, claim), expires

    async def _cancelled(self, task: asyncio.Future, claim: Claim) -> RemoteOperationResult:
        """Stop a run whose operation was cancelled (R5.30), reset the tool, and answer
        ``interrupted`` with what the run had established when it was stopped (#3236)."""
        failure, ran, unread = await self._abandon(
            task, f"operation {claim.fence.operation_id} was cancelled"
        )
        reason = REASON_CANCELLED
        if unread is not None:
            reason += f"; what it ran with couldn't be read: {unread}"
        if failure is not None:
            reason += f"; the worker's tool was not reset: {failure}"
        return RemoteOperationResult(
            status=OperationStatus.INTERRUPTED,
            reason=reason,
            ran_with=ran,
            dispatch_id=claim.request.dispatch_id,
        )

    async def _result_of(self, task: asyncio.Future, dispatch_id: str) -> RemoteOperationResult:
        """The ended operation's result. What the tool raised becomes ``interrupted``."""
        raised: BaseException | None
        if task.cancelled():
            raised = asyncio.CancelledError("the tool cancelled its own run")
        else:
            raised = task.exception()
        if raised is None:
            result: RemoteOperationResult = task.result()
            if result.status is OperationStatus.INTERRUPTED:
                self._unknown_state = "the tool reported the operation interrupted"
                await self._reset()
            else:
                self._returned = True
            too_large = evidence_size_defects(result)
            if too_large:
                # #3049: the operation's row and every reading of it carry the evidence, so an
                # item past its limit is never sent, and nothing is cut to fit. The records can't
                # be returned without the evidence they rest on.
                logger.error("the operation's result is too large to submit: %s", too_large)
                return RemoteOperationResult(
                    status=OperationStatus.NOT_EXECUTED,
                    reason="the provider's result can't be returned: " + "; ".join(too_large),
                    provider_version=result.provider_version,
                    ran_with=result.ran_with,
                    dispatch_id=dispatch_id,
                )
            return result
        logger.error("the tool raised while the operation ran", exc_info=raised)
        ran, unread = self._ran_so_far()
        self._unknown_state = f"the tool raised {type(raised).__name__}"
        reason = f"the tool raised while the operation ran: {type(raised).__name__}: {raised}"
        if unread is not None:
            reason += f"; what it ran with couldn't be read: {unread}"
        failure = await self._reset()
        if failure is not None:
            reason += f"; the worker's tool was not reset: {failure}"
        return RemoteOperationResult(
            status=OperationStatus.INTERRUPTED,
            reason=reason,
            # #3236: what the run had established before it raised.
            ran_with=ran,
            dispatch_id=dispatch_id,
        )

    def _unreachable(self, error: Exception) -> None:
        self._record(last_unreachable_at=self._clock(), last_unreachable=str(error))

    def _record(self, **changes: object) -> None:
        """Update the worker's status and report it. A report that fails is logged, and the
        worker serves on: its host then reads a status as old as the last one written, with its
        age."""
        self._status = replace(self._status, **changes)  # type: ignore[arg-type]
        if self._report is None:
            return
        try:
            self._report(self._status)
        except Exception as e:  # noqa: BLE001 - the report is the host's; serving goes on
            logger.error("the worker's status could not be recorded: %s", e)

    def _health_held(self) -> RuntimeStatus:
        """The tool's health as read before the claim. A claim is only ever made after a
        heartbeat that read it, so its absence is a defect in this loop and is raised."""
        if self._health is None:
            raise RuntimeError(
                "the worker holds a claim and never read its tool's health: a claim is made "
                "only after a heartbeat"
            )
        return self._health

    async def _abandon(
        self, task: asyncio.Future, why: str
    ) -> tuple[str | None, dict[str, str], str | None]:
        """Stop the operation and reset the tool. Returns why the reset failed (``None`` when
        it didn't), and what the run had established when it was stopped, read before the reset
        (#3236), with why that couldn't be read."""
        logger.warning("stopping the operation: %s", why)
        await _stop(task)
        ran, unread = self._ran_so_far()
        self._unknown_state = why
        return await self._reset(), ran, unread

    def _ran_so_far(self) -> tuple[dict[str, str], str | None]:
        """What the stopped or failed run had established (``running_with``), and ``None``, or
        nothing and why it couldn't be read. A runner that can't say never stops the answer the
        worker owes: the result is built without it, and its reason says so."""
        try:
            return dict(self._runner.running_with()), None
        except Exception as e:  # noqa: BLE001 - whatever the tool raised is the reason given
            logger.error("what the run had established couldn't be read", exc_info=e)
            return {}, f"{type(e).__name__}: {e}"

    async def _reset(self) -> str | None:
        """Reset the tool. Returns why it couldn't be, or ``None`` once its state is known.
        Each outcome goes on the worker's status (#3184): a tool that couldn't be reset at a
        claim reads not ready there, with why, as one that couldn't at the start does."""
        try:
            await self._runner.reset()
        except Exception as e:  # noqa: BLE001 - whatever the tool raised is the reason given
            logger.error("the tool could not be reset (%s)", self._unknown_state, exc_info=e)
            failure = f"{type(e).__name__}: {e}"
            self._record(tool_ready=False, tool_note=failure)
            return failure
        logger.info("the tool was reset (%s)", self._unknown_state)
        self._unknown_state = None
        self._fresh = True
        self._record(tool_ready=True, tool_note="")
        return None

    async def _deliver(
        self, enrolment: Enrolment, fence: Fence, expires: datetime, result: RemoteOperationResult
    ) -> None:
        """Submit ``result``, again while the runtime can't be reached and the lease is held,
        for one lease's length at most: a result the runtime never takes isn't held forever."""
        give_up_at = self._clock() + enrolment.lease
        while True:
            try:
                reading = await self._api.submit_result(fence, result)
            except RuntimeUnreachable as e:
                if self._clock() >= min(expires, give_up_at):
                    logger.error(
                        "the %s result of operation %s attempt %s was not delivered, and "
                        "the worker has stopped trying: %s",
                        result.status.value,
                        fence.operation_id,
                        fence.attempt,
                        e,
                    )
                    return
                logger.warning("the result was not delivered, and will be tried again: %s", e)
                await self._sleep(self._idle_poll)
                try:
                    lease = await self._api.renew(enrolment.session_id, self._health_held(), fence)
                except RuntimeUnreachable:
                    continue
                if lease.refusal is not None:
                    logger.error(
                        "the %s result of operation %s attempt %s was not delivered: the "
                        "runtime no longer holds it for this claim (%s)",
                        result.status.value,
                        fence.operation_id,
                        fence.attempt,
                        lease.refusal.value,
                    )
                    return
                expires = _expiry(lease)
                continue
            if reading.refusal is not None:
                logger.warning(
                    "the runtime refused the result of operation %s attempt %s (%s) and "
                    "recorded the refusal",
                    fence.operation_id,
                    fence.attempt,
                    reading.refusal.value,
                )
            else:
                logger.info(
                    "operation %s attempt %s: %s, accepted",
                    fence.operation_id,
                    fence.attempt,
                    result.status.value,
                )
            return

    async def _wait(self, task: asyncio.Future, seconds: float) -> None:
        """Until the operation ends or ``seconds`` pass, whichever is first."""
        timer = asyncio.ensure_future(self._sleep(seconds))
        try:
            await asyncio.wait({task, timer}, return_when=asyncio.FIRST_COMPLETED)
        finally:
            if not timer.done():
                timer.cancel()
                with suppress(asyncio.CancelledError):
                    await timer


async def _stop(task: asyncio.Future) -> None:
    """Cancel the operation and wait until it has stopped. What it raises on the way out is
    logged: the operation is being abandoned, and its ending is no result.

    ``asyncio.wait`` and never ``await task``: awaiting a cancelled task raises
    ``CancelledError`` whether the operation stopped or this call was cancelled, and reading
    the first as the second would swallow the worker's own stop.
    """
    task.cancel()
    await asyncio.wait({task})
    if not task.cancelled() and task.exception() is not None:
        logger.warning("the operation raised as it was stopped", exc_info=task.exception())


def _expiry(lease: LeaseReading) -> datetime:
    if lease.expires_at is None:
        raise RuntimeAnswerUnreadable("the runtime says the lease is held and gives no expiry")
    return lease.expires_at
