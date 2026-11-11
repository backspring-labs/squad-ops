"""The worker registry's rows in Postgres (SIP-0117 R5.4), over the runtime's one pool.

Migration 2300 creates its tables. A lease is the operation's own row, so it outlives the
runtime that granted it (R3.3: "a durable token of its own, because a lease outlives a runtime
restart").

``exclusive()`` is one database transaction under one advisory lock, so no two callers decide
about the registry's rows at once, on this runtime or another. The registry is small and its
calls are short: a worker claims every few seconds at most.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Sequence
from contextlib import asynccontextmanager

import asyncpg

from squadops.ports.remote_execution import WorkerRegistryStorePort, WorkerRegistryTransaction
from squadops.remote_execution.wire import (
    request_from_wire,
    request_to_wire,
    result_from_wire,
    result_to_wire,
)
from squadops.remote_execution.workers import (
    Attempt,
    AttemptOutcome,
    Fence,
    FenceRefusal,
    OperationState,
    QueuedOperation,
    RecordedRefusal,
    ServedOperation,
    WorkerSession,
)

#: The advisory lock's class, apart from the migrations' single-key lock and SIP-0112's 112.
_LOCK_CLASS = 117

_SESSION_COLUMNS = (
    "session_id, worker_id, platform, tool_versions, operations, runtime_status, "
    "registered_at, last_heartbeat_at, ended_at"
)
_OPERATION_COLUMNS = (
    "operation_id, provider, operation, request, origin, max_attempts, state, created_at, "
    "attempt, lease_id, session_id, lease_expires_at, cancel_requested, result, settled_at"
)
_ATTEMPT_COLUMNS = (
    "operation_id, attempt, session_id, worker_id, lease_id, claimed_at, ended_at, outcome"
)


class PostgresWorkerRegistryStore(WorkerRegistryStorePort):
    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    @asynccontextmanager
    async def exclusive(self) -> AsyncIterator[WorkerRegistryTransaction]:
        async with self._pool.acquire() as conn, conn.transaction():
            await conn.execute("SELECT pg_advisory_xact_lock($1, 0)", _LOCK_CLASS)
            yield _PostgresTransaction(conn)


class _PostgresTransaction(WorkerRegistryTransaction):
    def __init__(self, conn: asyncpg.Connection) -> None:
        self._conn = conn

    async def session(self, session_id: str) -> WorkerSession | None:
        row = await self._conn.fetchrow(
            f"SELECT {_SESSION_COLUMNS} FROM remote_worker_sessions WHERE session_id = $1",
            session_id,
        )
        return _session(row) if row else None

    async def live_sessions(self) -> list[WorkerSession]:
        rows = await self._conn.fetch(
            f"SELECT {_SESSION_COLUMNS} FROM remote_worker_sessions "
            "WHERE ended_at IS NULL ORDER BY registered_at, session_id"
        )
        return [_session(row) for row in rows]

    async def save_session(self, session: WorkerSession) -> None:
        await self._conn.execute(
            f"INSERT INTO remote_worker_sessions ({_SESSION_COLUMNS}) "
            "VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9) "
            "ON CONFLICT (session_id) DO UPDATE SET runtime_status = EXCLUDED.runtime_status, "
            "last_heartbeat_at = EXCLUDED.last_heartbeat_at, ended_at = EXCLUDED.ended_at",
            session.session_id,
            session.worker_id,
            session.platform,
            dict(session.tool_versions),
            [{"provider": s.provider, "operation": s.operation} for s in session.operations],
            session.runtime_status,
            session.registered_at,
            session.last_heartbeat_at,
            session.ended_at,
        )

    async def operation(self, operation_id: str) -> QueuedOperation | None:
        row = await self._conn.fetchrow(
            f"SELECT {_OPERATION_COLUMNS} FROM remote_operations WHERE operation_id = $1",
            operation_id,
        )
        return _operation(row) if row else None

    async def claimed_operations(self) -> list[QueuedOperation]:
        rows = await self._conn.fetch(
            f"SELECT {_OPERATION_COLUMNS} FROM remote_operations "
            "WHERE state = $1 ORDER BY created_at, operation_id",
            OperationState.CLAIMED.value,
        )
        return [_operation(row) for row in rows]

    async def queued_operations(self, served: Sequence[ServedOperation]) -> list[QueuedOperation]:
        rows = await self._conn.fetch(
            f"SELECT {_OPERATION_COLUMNS} FROM remote_operations "
            "WHERE state = $1 AND (provider, operation) IN "
            "(SELECT * FROM unnest($2::text[], $3::text[])) "
            "ORDER BY created_at, operation_id",
            OperationState.QUEUED.value,
            [s.provider for s in served],
            [s.operation for s in served],
        )
        return [_operation(row) for row in rows]

    async def save_operation(self, operation: QueuedOperation) -> None:
        await self._conn.execute(
            f"INSERT INTO remote_operations ({_OPERATION_COLUMNS}) "
            "VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15) "
            "ON CONFLICT (operation_id) DO UPDATE SET state = EXCLUDED.state, "
            "attempt = EXCLUDED.attempt, lease_id = EXCLUDED.lease_id, "
            "session_id = EXCLUDED.session_id, lease_expires_at = EXCLUDED.lease_expires_at, "
            "cancel_requested = EXCLUDED.cancel_requested, result = EXCLUDED.result, "
            "settled_at = EXCLUDED.settled_at",
            operation.operation_id,
            operation.request.provider,
            operation.request.operation,
            request_to_wire(operation.request),
            dict(operation.origin),
            operation.max_attempts,
            operation.state.value,
            operation.created_at,
            operation.attempt,
            operation.lease_id,
            operation.session_id,
            operation.lease_expires_at,
            operation.cancel_requested,
            result_to_wire(operation.result) if operation.result is not None else None,
            operation.settled_at,
        )

    async def attempt(self, operation_id: str, attempt: int) -> Attempt | None:
        row = await self._conn.fetchrow(
            f"SELECT {_ATTEMPT_COLUMNS} FROM remote_operation_attempts "
            "WHERE operation_id = $1 AND attempt = $2",
            operation_id,
            attempt,
        )
        return _attempt(row) if row else None

    async def attempts_of(self, worker_id: str) -> list[Attempt]:
        rows = await self._conn.fetch(
            f"SELECT {_ATTEMPT_COLUMNS} FROM remote_operation_attempts WHERE worker_id = $1 "
            "ORDER BY claimed_at DESC, operation_id DESC, attempt DESC",
            worker_id,
        )
        return [_attempt(row) for row in rows]

    async def save_attempt(self, attempt: Attempt) -> None:
        await self._conn.execute(
            f"INSERT INTO remote_operation_attempts ({_ATTEMPT_COLUMNS}) "
            "VALUES ($1,$2,$3,$4,$5,$6,$7,$8) "
            "ON CONFLICT (operation_id, attempt) DO UPDATE SET ended_at = EXCLUDED.ended_at, "
            "outcome = EXCLUDED.outcome",
            attempt.operation_id,
            attempt.attempt,
            attempt.session_id,
            attempt.worker_id,
            attempt.lease_id,
            attempt.claimed_at,
            attempt.ended_at,
            attempt.outcome.value if attempt.outcome is not None else None,
        )

    async def record_refusal(self, refusal: RecordedRefusal) -> None:
        await self._conn.execute(
            "INSERT INTO remote_operation_refusals "
            "(operation_id, attempt, session_id, lease_id, refusal, received_at) "
            "VALUES ($1,$2,$3,$4,$5,$6)",
            refusal.fence.operation_id,
            refusal.fence.attempt,
            refusal.fence.session_id,
            refusal.fence.lease_id,
            refusal.refusal.value,
            refusal.received_at,
        )

    async def refusals(self, operation_id: str) -> list[RecordedRefusal]:
        rows = await self._conn.fetch(
            "SELECT operation_id, attempt, session_id, lease_id, refusal, received_at "
            "FROM remote_operation_refusals WHERE operation_id = $1 ORDER BY refusal_id",
            operation_id,
        )
        return [
            RecordedRefusal(
                Fence(row["operation_id"], row["attempt"], row["session_id"], row["lease_id"]),
                FenceRefusal(row["refusal"]),
                row["received_at"],
            )
            for row in rows
        ]


def _session(row: asyncpg.Record) -> WorkerSession:
    return WorkerSession(
        session_id=row["session_id"],
        worker_id=row["worker_id"],
        platform=row["platform"],
        tool_versions=dict(row["tool_versions"]),
        operations=tuple(
            ServedOperation(served["provider"], served["operation"]) for served in row["operations"]
        ),
        runtime_status=row["runtime_status"],
        registered_at=row["registered_at"],
        last_heartbeat_at=row["last_heartbeat_at"],
        ended_at=row["ended_at"],
    )


def _operation(row: asyncpg.Record) -> QueuedOperation:
    return QueuedOperation(
        operation_id=row["operation_id"],
        request=request_from_wire(row["request"]),
        origin=dict(row["origin"]),
        max_attempts=row["max_attempts"],
        state=OperationState(row["state"]),
        created_at=row["created_at"],
        attempt=row["attempt"],
        lease_id=row["lease_id"],
        session_id=row["session_id"],
        lease_expires_at=row["lease_expires_at"],
        cancel_requested=row["cancel_requested"],
        result=result_from_wire(row["result"]) if row["result"] is not None else None,
        settled_at=row["settled_at"],
    )


def _attempt(row: asyncpg.Record) -> Attempt:
    return Attempt(
        operation_id=row["operation_id"],
        attempt=row["attempt"],
        session_id=row["session_id"],
        worker_id=row["worker_id"],
        lease_id=row["lease_id"],
        claimed_at=row["claimed_at"],
        ended_at=row["ended_at"],
        outcome=AttemptOutcome(row["outcome"]) if row["outcome"] is not None else None,
    )
