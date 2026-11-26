"""The worker registry: register, heartbeat, claim, result (SIP-0117 R3.3, R5.4).

It applies ``leasing``'s rules to the rows a ``WorkerRegistryStorePort`` keeps, each call in
one exclusive transaction. The rules are in one place and the rows in another, so the registry
behaves the same over memory and Postgres, and what a test proves over one holds over both.

What it guarantees:

- a worker has one live session and at most one claim;
- a result is accepted only under the current fence, and a refused one is recorded;
- the same fence submitting its accepted result again is answered as accepted, once stored;
- a lease that ran out ends its attempt before anything else is decided about the operation.
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Mapping
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

from squadops.core.lineage import new_id
from squadops.remote_execution import leasing
from squadops.remote_execution.models import (
    RAN_WITH_SERVED_BY,
    OperationStatus,
    RemoteOperationRequest,
    RemoteOperationResult,
)
from squadops.remote_execution.workers import (
    ORIGIN_CAMPAIGN,
    ORIGIN_CYCLE,
    OWNER_KEYS,
    Attempt,
    AttemptOutcome,
    CancelEffect,
    CancelledOperation,
    Claim,
    Enqueued,
    Fence,
    FenceRefusal,
    LeaseReading,
    NoWorker,
    OperationOwner,
    OperationState,
    OwnerCancelled,
    QueuedOperation,
    RecordedRefusal,
    ResultReading,
    SendConflict,
    UnknownOperation,
    UnknownSession,
    WorkerReading,
    WorkerRegistration,
    WorkerSession,
)
from squadops.runtime.models import RuntimeStatus

if TYPE_CHECKING:
    from squadops.ports.remote_execution import (
        WorkerRegistryStorePort,
        WorkerRegistryTransaction,
    )


logger = logging.getLogger(__name__)

#: How many of a worker's refused results an operator's reading shows (#3047).
RECENT_REFUSALS = 10


def _utc_now() -> datetime:
    return datetime.now(UTC)


class WorkerRegistry:
    def __init__(
        self, store: WorkerRegistryStorePort, *, clock: Callable[[], datetime] = _utc_now
    ) -> None:
        self._store = store
        self._clock = clock

    # ------------------------------------------------------------------ the worker's calls

    async def register(self, registration: WorkerRegistration) -> WorkerSession:
        """A new session for the worker. Raises ``ValueError`` naming every defect of a
        registration that can't be matched to work.

        A worker that registers again has restarted: its earlier session ends, and an attempt
        that session held ends with it, since nothing is left running it.
        """
        errors = leasing.registration_errors(registration)
        if errors:
            raise ValueError("; ".join(errors))
        now = self._clock()
        async with self._store.exclusive() as tx:
            for earlier in await tx.live_sessions():
                if earlier.worker_id != registration.worker_id:
                    continue
                await self._end_attempt_held_by(tx, earlier.session_id, now)
                await tx.save_session(replace(earlier, ended_at=now))
            session = WorkerSession(
                session_id=new_id("wks"),
                worker_id=registration.worker_id,
                platform=registration.platform,
                tool_versions=dict(registration.tool_versions),
                operations=tuple(registration.operations),
                runtime_status="online",
                registered_at=now,
                last_heartbeat_at=now,
            )
            await tx.save_session(session)
            return session

    async def heartbeat(
        self, session_id: str, runtime_status: RuntimeStatus, fence: Fence | None
    ) -> LeaseReading | None:
        """Record that the session is alive and what it reports. With a fence, renew that
        lease and say whether it is still held; without one, return ``None``."""
        reported = leasing.runtime_status(runtime_status)
        now = self._clock()
        async with self._store.exclusive() as tx:
            session = await self._live_session(tx, session_id)
            await tx.save_session(replace(session, runtime_status=reported, last_heartbeat_at=now))
            if fence is None:
                return None
            if fence.session_id != session_id:
                return LeaseReading(FenceRefusal.STALE_SESSION)
            operation = await tx.operation(fence.operation_id)
            refusal = leasing.fence_refusal(operation, fence, now)
            if refusal is FenceRefusal.LEASE_EXPIRED:
                await self._end_attempt(tx, _held(operation), now)
            if refusal is not None:
                return LeaseReading(refusal)
            renewed = leasing.renewed(_held(operation), now)
            await tx.save_operation(renewed)
            return LeaseReading(None, renewed.lease_expires_at, renewed.cancel_requested)

    async def claim(self, session_id: str) -> Claim | None:
        """The oldest queued operation the session serves, claimed for it, or ``None`` when
        there is none or the worker already holds one."""
        now = self._clock()
        async with self._store.exclusive() as tx:
            session = await self._live_session(tx, session_id)
            await tx.save_session(replace(session, last_heartbeat_at=now))
            await self._end_lapsed_attempts(tx, now)
            history = await tx.attempts_of(session.worker_id)
            if any(attempt.ended_at is None for attempt in history):
                return None
            for candidate in await tx.queued_operations(session.operations):
                if not leasing.claimable_by(candidate, session):
                    continue
                operation = leasing.claimed(candidate, session, new_id("lease"), now)
                fence = _fence(operation)
                await tx.save_operation(operation)
                await tx.save_attempt(
                    Attempt(
                        operation_id=fence.operation_id,
                        attempt=fence.attempt,
                        session_id=fence.session_id,
                        worker_id=session.worker_id,
                        lease_id=fence.lease_id,
                        claimed_at=now,
                    )
                )
                return Claim(
                    fence=fence,
                    request=operation.request,
                    lease_expires_at=_expiry(operation),
                    reconcile_first=bool(history) and history[0].outcome is AttemptOutcome.EXPIRED,
                )
            return None

    async def submit_result(self, fence: Fence, result: RemoteOperationResult) -> ResultReading:
        """Accept ``result`` under ``fence``, or refuse it and record the refusal."""
        now = self._clock()
        async with self._store.exclusive() as tx:
            operation = await tx.operation(fence.operation_id)
            refusal = leasing.fence_refusal(operation, fence, now)
            if refusal is None:
                held = _held(operation)
                result = await self._served(tx, fence, result)
                if held.cancel_requested and result.status is not OperationStatus.INTERRUPTED:
                    # #3236: the cancel was recorded first, so it wins. The worker's result is
                    # received and kept, and is no evidence. A worker that saw the cancel
                    # answers ``interrupted`` itself, and that is the operation's result.
                    await tx.save_operation(leasing.settled_after_cancel(held, result, now))
                    await self._close_attempt(tx, fence, AttemptOutcome.CANCELLED, now)
                    logger.info(
                        "remote_operation_result_after_cancel",
                        extra={
                            "operation_id": fence.operation_id,
                            "attempt": fence.attempt,
                            "late_status": result.status.value,
                        },
                    )
                    return ResultReading(None)
                await tx.save_operation(leasing.settled(held, result, now))
                await self._close_attempt(tx, fence, AttemptOutcome.ACCEPTED, now)
                return ResultReading(None)
            if refusal is FenceRefusal.ALREADY_SETTLED and await self._was_received(tx, fence):
                return ResultReading(None, replayed=True)
            if refusal is FenceRefusal.LEASE_EXPIRED:
                await self._end_attempt(tx, _held(operation), now)
            await tx.record_refusal(RecordedRefusal(fence, refusal, now))
            return ResultReading(refusal)

    async def _served(self, tx, fence: Fence, result: RemoteOperationResult):
        """``result`` with who served it written by the registry (#3200, R5.32): the worker
        whose session submitted it under the accepted ``fence``. A worker's own word under that
        key is dropped first, whatever follows, so it never stands as the registry's. A session
        the store doesn't hold is a defect, since the fence was just accepted under it: raised,
        never settled without the name."""
        ran_with = {k: v for k, v in result.ran_with.items() if k != RAN_WITH_SERVED_BY}
        session = await tx.session(fence.session_id)
        if session is None:
            raise RuntimeError(
                f"operation {fence.operation_id}: its result was accepted under session "
                f"{fence.session_id}, which the store doesn't hold, so who served it can't be "
                "written"
            )
        return replace(result, ran_with={**ran_with, RAN_WITH_SERVED_BY: session.worker_id})

    # ------------------------------------------------------------------ the requester's calls

    async def enqueue(
        self,
        request: RemoteOperationRequest,
        origin: Mapping[str, str],
        *,
        max_attempts: int,
        only_with_worker: bool,
    ) -> Enqueued | NoWorker | OwnerCancelled:
        """Queue ``request`` for a worker that serves it: once per send of its task (R5.6).

        ``origin`` names whose operation it is (``OperationOwner``), or the call is a defect and
        raises: an operation nobody owns is one no cancel reaches (#3236).

        - **The send already asked:** the operation it asked for then, as it stands now, so a
          requester that lost the answer or restarted reads the one it has. The same send with
          a different request is refused (``SendConflict``).
        - **An older send of the task asked:** each of its operations still without a result
          is asked to stop. Only the current send's result is read, so an older one's would
          run for nobody.
        - **No worker can run it now,** when ``only_with_worker``: nothing is queued, and the
          reason is returned. A requester always asks this way. Without it, the operation
          waits in the queue for a worker to register.
        - **Its owner was cancelled:** nothing is queued, and the reason is returned. A send
          that had already asked still reads the operation it asked for.
        """
        if max_attempts < 1:
            raise ValueError(f"max_attempts is {max_attempts}; an operation needs at least one")
        owner = OperationOwner.from_origin(origin)
        now = self._clock()
        async with self._store.exclusive() as tx:
            earlier = await tx.operation_for_send(request.task_id, request.dispatch_id)
            if earlier is not None:
                if earlier.request != request:
                    raise SendConflict(
                        f"send {request.dispatch_id} of task {request.task_id} asked for "
                        f"operation {earlier.operation_id} with a different request"
                    )
                if leasing.lease_ran_out(earlier, now):
                    earlier = await self._end_attempt(tx, earlier, now)
                return Enqueued(earlier, repeated=True)
            for key, value in _owner_keys(owner):
                cancelled_at = await tx.owner_cancelled_at(key, value)
                if cancelled_at is not None:
                    return OwnerCancelled(
                        f"{leasing.owner_ended(key, value)} at "
                        f"{cancelled_at.isoformat(timespec='seconds')}, so nothing is run for it"
                    )
            superseded = []
            reason = leasing.superseded_reason(request.dispatch_id)
            for older in await tx.unsettled_operations_of(request.task_id):
                if leasing.lease_ran_out(older, now):
                    older = await self._end_attempt(tx, older, now)
                await tx.save_operation(leasing.cancelled(older, now, reason=reason))
                superseded.append(older.operation_id)
            no_worker = (
                leasing.no_worker_for(
                    request.provider, request.operation, await tx.live_sessions(), now
                )
                if only_with_worker
                else None
            )
            if no_worker is None:
                operation = QueuedOperation(
                    operation_id=new_id("rop"),
                    request=request,
                    origin=dict(origin),
                    max_attempts=max_attempts,
                    state=OperationState.QUEUED,
                    created_at=now,
                )
                await tx.save_operation(operation)
        if superseded:
            # Named: each was stopped in favour of this send, and its result says so.
            logger.info(
                "remote_operation_superseded",
                extra={
                    "task_id": request.task_id,
                    "dispatch_id": request.dispatch_id,
                    "superseded": superseded,
                },
            )
        if no_worker is not None:
            return no_worker
        return Enqueued(operation, repeated=False, superseded=tuple(superseded))

    async def operation(self, operation_id: str) -> QueuedOperation:
        """The operation as it stands now: a lease that ran out is ended first, so a reader
        never sees an operation held by a worker that stopped renewing it."""
        now = self._clock()
        async with self._store.exclusive() as tx:
            operation = await tx.operation(operation_id)
            if operation is None:
                raise UnknownOperation(operation_id)
            if leasing.lease_ran_out(operation, now):
                return await self._end_attempt(tx, operation, now)
            return operation

    async def cancel(self, operation_id: str) -> QueuedOperation:
        """Ask for the operation to stop (``leasing.cancelled``)."""
        now = self._clock()
        async with self._store.exclusive() as tx:
            operation = await tx.operation(operation_id)
            if operation is None:
                raise UnknownOperation(operation_id)
            if leasing.lease_ran_out(operation, now):
                operation = await self._end_attempt(tx, operation, now)
            cancelled = leasing.cancelled(operation, now, reason=leasing.REASON_CANCELLED_UNCLAIMED)
            await tx.save_operation(cancelled)
            return cancelled

    async def cancel_owned(
        self, key: str, value: str, *, because: str, final: bool
    ) -> list[CancelledOperation]:
        """Ask every operation the owner has that is still without a result to stop (#3236).
        ``key`` is the cycle's or the Campaign's origin key, and ``because`` says what ended.

        - **Queued:** settled now, as ``leasing.cancelled`` settles it.
        - **Claimed:** marked. Its worker is told at its next renewal, and a result it sends
          before then is kept as the late result (``submit_result``).
        - **Already with its result:** not touched. The result came first, and stands.

        ``final`` says the owner itself has ended: a cycle's cancel, a Campaign's abort. It is
        recorded, and nothing new is queued for the owner afterwards (``enqueue``). A run's
        cancel isn't final, since its cycle may go on to another run.

        The answer names each operation reached and what was done to it. Asking again is safe:
        nothing settled changes, and a marked operation stays marked.
        """
        if key not in OWNER_KEYS:
            raise ValueError(f"an owner is named by one of {', '.join(OWNER_KEYS)}, not {key!r}")
        now = self._clock()
        reached: list[CancelledOperation] = []
        async with self._store.exclusive() as tx:
            if final:
                await tx.record_owner_cancelled(key, value, now)
            for operation in await tx.unsettled_operations_owned(key, value):
                if leasing.lease_ran_out(operation, now):
                    operation = await self._end_attempt(tx, operation, now)
                    if operation.state is OperationState.SETTLED:
                        continue
                cancelled = leasing.cancelled(
                    operation, now, reason=f"{leasing.REASON_CANCELLED_UNCLAIMED}: {because}"
                )
                await tx.save_operation(cancelled)
                effect = (
                    CancelEffect.SETTLED
                    if cancelled.state is OperationState.SETTLED
                    else CancelEffect.STOP_REQUESTED
                )
                reached.append(
                    CancelledOperation(operation.operation_id, operation.request.task_id, effect)
                )
        if reached:
            logger.info(
                "remote_operations_cancelled_with_owner",
                extra={
                    "owner": f"{key}={value}",
                    "because": because,
                    "operations": [f"{c.operation_id}:{c.effect.value}" for c in reached],
                },
            )
        return reached

    async def no_worker_for(self, provider: str, operation: str) -> NoWorker | None:
        """Why no registered worker can run the operation now, or ``None`` when one can."""
        async with self._store.exclusive() as tx:
            return leasing.no_worker_for(
                provider, operation, await tx.live_sessions(), self._clock()
            )

    # ------------------------------------------------------------------ reads

    async def sessions(self) -> list[tuple[WorkerSession, RuntimeStatus]]:
        """Every live session with its health now."""
        now = self._clock()
        async with self._store.exclusive() as tx:
            return [(s, leasing.health(s, now)) for s in await tx.live_sessions()]

    async def refusals(self, operation_id: str) -> list[RecordedRefusal]:
        async with self._store.exclusive() as tx:
            return await tx.refusals(operation_id)

    async def readings(self, *, refusals: int = RECENT_REFUSALS) -> list[WorkerReading]:
        """Every live session as an operator reads it (#3047), oldest registration first. As
        ``operation`` does, a lease that ran out is ended first, so an operation is never shown
        held by a worker that stopped renewing it."""
        now = self._clock()
        async with self._store.exclusive() as tx:
            await self._end_lapsed_attempts(tx, now)
            claimed = await tx.claimed_operations()
            readings = []
            for session in await tx.live_sessions():
                held = tuple(o for o in claimed if o.session_id == session.session_id)
                readings.append(
                    WorkerReading(
                        session,
                        leasing.health(session, now),
                        held,
                        tuple(await tx.refusals_of(session.worker_id, refusals)),
                    )
                )
            return readings

    # ------------------------------------------------------------------ within a transaction

    async def _live_session(self, tx: WorkerRegistryTransaction, session_id: str) -> WorkerSession:
        session = await tx.session(session_id)
        if session is None or session.ended_at is not None:
            raise UnknownSession(session_id)
        return session

    async def _end_lapsed_attempts(self, tx: WorkerRegistryTransaction, now: datetime) -> None:
        for operation in await tx.claimed_operations():
            if leasing.lease_ran_out(operation, now):
                await self._end_attempt(tx, operation, now)

    async def _end_attempt_held_by(
        self, tx: WorkerRegistryTransaction, session_id: str, now: datetime
    ) -> None:
        for operation in await tx.claimed_operations():
            if operation.session_id == session_id:
                await self._end_attempt(tx, operation, now)

    async def _end_attempt(
        self, tx: WorkerRegistryTransaction, operation: QueuedOperation, now: datetime
    ) -> QueuedOperation:
        """End the operation's current attempt with no result, and store what follows."""
        fence = _fence(operation)
        after = leasing.after_expiry(operation, now)
        await tx.save_operation(after)
        await self._close_attempt(tx, fence, AttemptOutcome.EXPIRED, now)
        return after

    async def _close_attempt(
        self, tx: WorkerRegistryTransaction, fence: Fence, outcome: AttemptOutcome, now: datetime
    ) -> None:
        attempt = await tx.attempt(fence.operation_id, fence.attempt)
        if attempt is None:
            raise LookupError(
                f"operation {fence.operation_id} is claimed on attempt {fence.attempt}, "
                "and no attempt row records that claim"
            )
        await tx.save_attempt(replace(attempt, ended_at=now, outcome=outcome))

    async def _was_received(self, tx: WorkerRegistryTransaction, fence: Fence) -> bool:
        """Whether this fence's result was already taken in: as the operation's result, or as
        its late one (#3236). A worker that sends it again is answered as before."""
        attempt = await tx.attempt(fence.operation_id, fence.attempt)
        return (
            attempt is not None
            and attempt.fence == fence
            and attempt.outcome in (AttemptOutcome.ACCEPTED, AttemptOutcome.CANCELLED)
        )


def _owner_keys(owner: OperationOwner) -> list[tuple[str, str]]:
    """The owner as the keys a cancel is asked by: its cycle, and its Campaign when it has one."""
    keys = [(ORIGIN_CYCLE, owner.cycle_id)]
    if owner.campaign_id is not None:
        keys.append((ORIGIN_CAMPAIGN, owner.campaign_id))
    return keys


def _held(operation: QueuedOperation | None) -> QueuedOperation:
    """The operation a fence was just judged against, which is then known to exist."""
    if operation is None:
        raise LookupError("a fence was judged current for an operation that doesn't exist")
    return operation


def _fence(operation: QueuedOperation) -> Fence:
    fence = operation.fence
    if fence is None:
        raise ValueError(f"operation {operation.operation_id} is not claimed")
    return fence


def _expiry(operation: QueuedOperation) -> datetime:
    if operation.lease_expires_at is None:
        raise ValueError(f"operation {operation.operation_id} is claimed and has no lease expiry")
    return operation.lease_expires_at


def cadence() -> tuple[timedelta, timedelta]:
    """The interval to heartbeat at and how long a lease lasts. A worker is told both when it
    registers, so it carries neither number itself."""
    return (
        timedelta(seconds=leasing.HEARTBEAT_SECONDS),
        timedelta(seconds=leasing.LEASE_SECONDS),
    )
