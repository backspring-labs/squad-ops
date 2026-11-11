"""The lease rules for a remote operation, as pure decisions (SIP-0117 R3.3, R5.4).

Each function takes what is stored and the time, and returns what should be stored or why a
request is refused. None reads a clock or a store, so the rules are the same whatever keeps
the rows, and a test states a time and reads an answer.

The rules:

- **One lease per operation, and it is the fence.** A heartbeat or a result presents the
  operation, attempt, session and lease ids. All four are the current ones and the lease has
  not run out, or it is refused with the reason.
- **A lease that runs out ends its attempt.** The operation is queued again for a new attempt,
  with the attempt number advanced at the next claim. On the last attempt it settles as
  ``interrupted``: a worker held it, so it may have started, and that is never a failure or a
  pass.
- **A cancel** settles a queued operation as ``not_executed``, and marks a claimed one for its
  worker to see at its next heartbeat. A marked operation whose lease then runs out settles
  as ``interrupted``, whatever attempts it had left: nobody wants it run again (R5.6).
- **Health is what the worker last reported, while it is being heard from.** A session silent
  past ``SESSION_SILENT_SECONDS`` reads ``offline``. Busy is the lease, never a health value.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import replace
from datetime import datetime, timedelta
from typing import cast, get_args

from squadops.remote_execution.models import OperationStatus, RemoteOperationResult
from squadops.remote_execution.workers import (
    Fence,
    FenceRefusal,
    NoWorker,
    OperationState,
    QueuedOperation,
    WorkerRegistration,
    WorkerSession,
)
from squadops.runtime.models import RuntimeStatus

#: How long a lease lasts from a claim or a renewal. A worker is told it when it registers,
#: with the interval to renew at, so it carries neither number itself.
LEASE_SECONDS = 60
HEARTBEAT_SECONDS = 15
#: A session not heard from for this long reads as offline: three missed heartbeats.
SESSION_SILENT_SECONDS = 45

RUNTIME_STATUSES: tuple[str, ...] = get_args(RuntimeStatus)

REASON_CANCELLED_UNCLAIMED = "cancelled before a worker claimed it"


def runtime_status(value: str) -> RuntimeStatus:
    """``value`` as a health value, or ``ValueError`` when it is outside the vocabulary. Busy
    is one such word: it is the lease, never a health value."""
    if value not in RUNTIME_STATUSES:
        raise ValueError(f"runtime_status {value!r} is none of {', '.join(RUNTIME_STATUSES)}")
    return cast(RuntimeStatus, value)


def registration_errors(registration: WorkerRegistration) -> list[str]:
    """Everything wrong with a registration, or ``[]``. A worker that names nothing it serves,
    or names one operation twice, is refused: it could never be matched, or would be matched
    ambiguously."""
    errors: list[str] = []
    if not registration.worker_id.strip():
        errors.append("worker_id is empty")
    if not registration.platform.strip():
        errors.append("platform is empty")
    if not registration.operations:
        errors.append("the worker names no operation it serves")
    seen: set[tuple[str, str]] = set()
    for served in registration.operations:
        key = (served.provider, served.operation)
        if not served.provider.strip() or not served.operation.strip():
            errors.append(f"an operation with an empty provider or name: {key!r}")
        elif key in seen:
            errors.append(f"{served.provider}/{served.operation} is named more than once")
        seen.add(key)
    for tool, version in registration.tool_versions.items():
        if not str(tool).strip() or not str(version).strip():
            errors.append(f"a tool version with an empty name or value: {tool!r}: {version!r}")
    return errors


def health(session: WorkerSession, now: datetime) -> RuntimeStatus:
    """The session's health now: ``offline`` once it has ended or gone silent, and otherwise
    what it last reported."""
    if session.ended_at is not None:
        return "offline"
    if now - session.last_heartbeat_at > timedelta(seconds=SESSION_SILENT_SECONDS):
        return "offline"
    return session.runtime_status


def lease_ran_out(operation: QueuedOperation, now: datetime) -> bool:
    """Whether a claimed operation's lease has run out. ``False`` for one nobody holds."""
    if operation.state is not OperationState.CLAIMED:
        return False
    if operation.lease_expires_at is None:
        raise ValueError(f"operation {operation.operation_id} is claimed and has no lease expiry")
    return now > operation.lease_expires_at


def claimable_by(operation: QueuedOperation, session: WorkerSession) -> bool:
    """Whether ``session`` may claim ``operation``: it is queued, nobody asked for it to stop,
    and the session serves it."""
    return (
        operation.state is OperationState.QUEUED
        and not operation.cancel_requested
        and session.serves(operation.request.provider, operation.request.operation)
    )


def claimed(
    operation: QueuedOperation, session: WorkerSession, lease_id: str, now: datetime
) -> QueuedOperation:
    """``operation`` as claimed by ``session``: the next attempt, under a new lease."""
    if not claimable_by(operation, session):
        raise ValueError(
            f"operation {operation.operation_id} can't be claimed by session {session.session_id}"
        )
    return replace(
        operation,
        state=OperationState.CLAIMED,
        attempt=operation.attempt + 1,
        lease_id=lease_id,
        session_id=session.session_id,
        lease_expires_at=now + timedelta(seconds=LEASE_SECONDS),
    )


def fence_refusal(
    operation: QueuedOperation | None, fence: Fence, now: datetime
) -> FenceRefusal | None:
    """Why ``fence`` isn't the current one for ``operation``, or ``None`` when it is.

    The order matters to the reason given: an operation that has its result is settled
    whatever the fence says, and an attempt number is read before the session and lease that
    belong to it.
    """
    if operation is None:
        return FenceRefusal.UNKNOWN_OPERATION
    if operation.state is OperationState.SETTLED:
        return FenceRefusal.ALREADY_SETTLED
    if operation.state is OperationState.QUEUED:
        return FenceRefusal.NOT_CLAIMED
    if fence.attempt != operation.attempt:
        return FenceRefusal.STALE_ATTEMPT
    if fence.session_id != operation.session_id:
        return FenceRefusal.STALE_SESSION
    if fence.lease_id != operation.lease_id:
        return FenceRefusal.STALE_LEASE
    if lease_ran_out(operation, now):
        return FenceRefusal.LEASE_EXPIRED
    return None


def renewed(operation: QueuedOperation, now: datetime) -> QueuedOperation:
    """A held lease, extended from ``now``."""
    if operation.state is not OperationState.CLAIMED:
        raise ValueError(f"operation {operation.operation_id} holds no lease to renew")
    return replace(operation, lease_expires_at=now + timedelta(seconds=LEASE_SECONDS))


def settled(
    operation: QueuedOperation, result: RemoteOperationResult, now: datetime
) -> QueuedOperation:
    """``operation`` with its result. The lease is released: a settled operation holds none."""
    if operation.state is OperationState.SETTLED:
        raise ValueError(f"operation {operation.operation_id} already has its result")
    return replace(
        operation,
        state=OperationState.SETTLED,
        lease_id=None,
        session_id=None,
        lease_expires_at=None,
        result=result,
        settled_at=now,
    )


def after_expiry(operation: QueuedOperation, now: datetime) -> QueuedOperation:
    """``operation`` once its current attempt has ended without a result: queued again while
    an attempt is left, and settled as ``interrupted`` on the last. One asked to stop is
    settled too: queued again it could never be claimed (``claimable_by``), and its requester
    would wait on an operation nothing will end."""
    if operation.state is not OperationState.CLAIMED:
        raise ValueError(f"operation {operation.operation_id} has no attempt to end")
    if operation.cancel_requested:
        return settled(
            operation,
            RemoteOperationResult(
                status=OperationStatus.INTERRUPTED,
                reason=(
                    f"cancelled while attempt {operation.attempt} held it, and worker session "
                    f"{operation.session_id} stopped renewing its lease before it answered"
                ),
                dispatch_id=operation.request.dispatch_id,
            ),
            now,
        )
    if operation.attempt < operation.max_attempts:
        return replace(
            operation,
            state=OperationState.QUEUED,
            lease_id=None,
            session_id=None,
            lease_expires_at=None,
        )
    return settled(
        operation,
        RemoteOperationResult(
            status=OperationStatus.INTERRUPTED,
            reason=(
                f"the lease on attempt {operation.attempt} of {operation.max_attempts} ended "
                f"with no result: worker session {operation.session_id} stopped renewing it"
            ),
            dispatch_id=operation.request.dispatch_id,
        ),
        now,
    )


def cancelled(operation: QueuedOperation, now: datetime) -> QueuedOperation:
    """``operation`` after a cancel. Queued: settled as ``not_executed``, since no worker
    began it. Claimed: marked, for its worker to stop and submit ``interrupted``. Settled:
    unchanged, since its result stands."""
    if operation.state is OperationState.SETTLED:
        return operation
    if operation.state is OperationState.CLAIMED:
        return replace(operation, cancel_requested=True)
    return settled(
        replace(operation, cancel_requested=True),
        RemoteOperationResult(
            status=OperationStatus.NOT_EXECUTED,
            reason=REASON_CANCELLED_UNCLAIMED,
            dispatch_id=operation.request.dispatch_id,
        ),
        now,
    )


def no_worker_for(
    provider: str, operation: str, sessions: Iterable[WorkerSession], now: datetime
) -> NoWorker | None:
    """Why no registered worker can run ``provider``'s ``operation`` now, or ``None`` when one
    can. The words go into a ``not_executed`` result, so they say which it is: nobody serves
    the operation, or the workers that do aren't being heard from."""
    serving = [s for s in sessions if s.ended_at is None and s.serves(provider, operation)]
    if not serving:
        return NoWorker(f"no registered worker serves {provider}/{operation}")
    if any(health(s, now) != "offline" for s in serving):
        return None
    unreachable = tuple(sorted({s.worker_id for s in serving}))
    last_heard = max(s.last_heartbeat_at for s in serving)
    return NoWorker(
        f"{', '.join(unreachable)} serves {provider}/{operation} and is offline "
        f"(last heard from at {last_heard.isoformat(timespec='seconds')})",
        unreachable=unreachable,
    )
