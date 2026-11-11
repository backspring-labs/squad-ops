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

from collections.abc import Callable, Mapping
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

from squadops.core.lineage import new_id
from squadops.remote_execution import leasing
from squadops.remote_execution.models import RemoteOperationRequest, RemoteOperationResult
from squadops.remote_execution.workers import (
    Attempt,
    AttemptOutcome,
    Claim,
    Fence,
    FenceRefusal,
    LeaseReading,
    NoWorker,
    OperationState,
    QueuedOperation,
    RecordedRefusal,
    ResultReading,
    UnknownOperation,
    UnknownSession,
    WorkerRegistration,
    WorkerSession,
)
from squadops.runtime.models import RuntimeStatus

if TYPE_CHECKING:
    from squadops.ports.remote_execution import (
        WorkerRegistryStorePort,
        WorkerRegistryTransaction,
    )


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
                await tx.save_operation(leasing.settled(_held(operation), result, now))
                await self._close_attempt(tx, fence, AttemptOutcome.ACCEPTED, now)
                return ResultReading(None)
            if refusal is FenceRefusal.ALREADY_SETTLED and await self._was_accepted(tx, fence):
                return ResultReading(None, replayed=True)
            if refusal is FenceRefusal.LEASE_EXPIRED:
                await self._end_attempt(tx, _held(operation), now)
            await tx.record_refusal(RecordedRefusal(fence, refusal, now))
            return ResultReading(refusal)

    # ------------------------------------------------------------------ the requester's calls

    async def enqueue(
        self, request: RemoteOperationRequest, origin: Mapping[str, str], *, max_attempts: int
    ) -> QueuedOperation:
        """Queue ``request`` for a worker that serves it."""
        if max_attempts < 1:
            raise ValueError(f"max_attempts is {max_attempts}; an operation needs at least one")
        operation = QueuedOperation(
            operation_id=new_id("rop"),
            request=request,
            origin=dict(origin),
            max_attempts=max_attempts,
            state=OperationState.QUEUED,
            created_at=self._clock(),
        )
        async with self._store.exclusive() as tx:
            await tx.save_operation(operation)
        return operation

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
            cancelled = leasing.cancelled(operation, now)
            await tx.save_operation(cancelled)
            return cancelled

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

    async def _was_accepted(self, tx: WorkerRegistryTransaction, fence: Fence) -> bool:
        attempt = await tx.attempt(fence.operation_id, fence.attempt)
        return (
            attempt is not None
            and attempt.fence == fence
            and attempt.outcome is AttemptOutcome.ACCEPTED
        )


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
