"""The worker registry's rows in memory (SIP-0117 R5.4): for tests, and for a runtime whose
cycle registry is in memory. Its leases are lost at a restart, as that runtime's cycles are."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Sequence
from contextlib import asynccontextmanager
from dataclasses import dataclass, field

from squadops.ports.remote_execution import WorkerRegistryStorePort, WorkerRegistryTransaction
from squadops.remote_execution.workers import (
    Attempt,
    OperationState,
    QueuedOperation,
    RecordedRefusal,
    ServedOperation,
    WorkerSession,
)


@dataclass
class _Rows:
    sessions: dict[str, WorkerSession] = field(default_factory=dict)
    operations: dict[str, QueuedOperation] = field(default_factory=dict)
    attempts: dict[tuple[str, int], Attempt] = field(default_factory=dict)
    refusals: list[RecordedRefusal] = field(default_factory=list)

    def copy(self) -> _Rows:
        return _Rows(
            dict(self.sessions), dict(self.operations), dict(self.attempts), list(self.refusals)
        )


class MemoryWorkerRegistryStore(WorkerRegistryStorePort):
    def __init__(self) -> None:
        self._rows = _Rows()
        self._lock = asyncio.Lock()

    @asynccontextmanager
    async def exclusive(self) -> AsyncIterator[WorkerRegistryTransaction]:
        async with self._lock:
            # The transaction writes to a copy, which replaces the rows only when it ends
            # without an exception: all of its writes, or none.
            working = self._rows.copy()
            yield _MemoryTransaction(working)
            self._rows = working


class _MemoryTransaction(WorkerRegistryTransaction):
    def __init__(self, rows: _Rows) -> None:
        self._rows = rows

    async def session(self, session_id: str) -> WorkerSession | None:
        return self._rows.sessions.get(session_id)

    async def live_sessions(self) -> list[WorkerSession]:
        live = [s for s in self._rows.sessions.values() if s.ended_at is None]
        return sorted(live, key=lambda s: (s.registered_at, s.session_id))

    async def save_session(self, session: WorkerSession) -> None:
        self._rows.sessions[session.session_id] = session

    async def operation(self, operation_id: str) -> QueuedOperation | None:
        return self._rows.operations.get(operation_id)

    async def claimed_operations(self) -> list[QueuedOperation]:
        return [o for o in self._rows.operations.values() if o.state is OperationState.CLAIMED]

    async def queued_operations(self, served: Sequence[ServedOperation]) -> list[QueuedOperation]:
        wanted = {(s.provider, s.operation) for s in served}
        queued = [
            o
            for o in self._rows.operations.values()
            if o.state is OperationState.QUEUED
            and (o.request.provider, o.request.operation) in wanted
        ]
        return sorted(queued, key=lambda o: (o.created_at, o.operation_id))

    async def save_operation(self, operation: QueuedOperation) -> None:
        self._rows.operations[operation.operation_id] = operation

    async def attempt(self, operation_id: str, attempt: int) -> Attempt | None:
        return self._rows.attempts.get((operation_id, attempt))

    async def attempts_of(self, worker_id: str) -> list[Attempt]:
        mine = [a for a in self._rows.attempts.values() if a.worker_id == worker_id]
        return sorted(mine, key=lambda a: (a.claimed_at, a.operation_id, a.attempt), reverse=True)

    async def save_attempt(self, attempt: Attempt) -> None:
        self._rows.attempts[(attempt.operation_id, attempt.attempt)] = attempt

    async def record_refusal(self, refusal: RecordedRefusal) -> None:
        self._rows.refusals.append(refusal)

    async def refusals(self, operation_id: str) -> list[RecordedRefusal]:
        return [r for r in self._rows.refusals if r.fence.operation_id == operation_id]
