"""Postgres-backed FocusLease adapter (SIP-0089 §3.3).

Implements `FocusLeasePort` via the asyncpg pool shared with the cycle registry,
runtime-state, and assignment adapters. All rows hit `focus_leases` (migration
`1120_focus_leases.sql`).

`request_lease` resolves a request to one v1.1 `LeaseDecision` (§11.5). The
single active-lease invariant is enforced by the partial unique index, so the
adapter both (a) checks for a current lease before inserting and (b) treats a
unique-violation on insert as a lost race and re-resolves — making concurrent
acquires safe even though v1.1 runs a single in-process writer.

Preemption is NOT auto-granted: a strictly higher-precedence owner type yields
`LeasePreempting` without writing a lease, leaving the grace period + revoke as
explicit, observable steps for the coordinator (§3.4).
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import asyncpg

from adapters.persistence.runtime._conn import acquire
from squadops.ports.runtime.focus_lease import FocusLeasePort
from squadops.runtime import reasons
from squadops.runtime.models import (
    FocusLease,
    Interruptibility,
    LeaseDecision,
    LeaseGranted,
    LeasePreempting,
    LeaseRejected,
    OwnerType,
    RecallPolicy,
    RenewalPolicy,
    owner_type_outranks,
)

_COLUMNS = (
    "lease_id, agent_id, owner_type, owner_ref, acquired_at, expires_at, "
    "renewal_policy, interruptibility, recall_policy, released_at, idempotency_key"
)


class PostgresFocusLease(FocusLeasePort):
    """Postgres-backed `FocusLeasePort` implementation."""

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def request_lease(
        self,
        agent_id: str,
        owner_type: OwnerType,
        owner_ref: str,
        idempotency_key: str,
        *,
        expires_at: datetime | None = None,
        renewal_policy: RenewalPolicy = "ttl",
        interruptibility: Interruptibility = "high",
        recall_policy: RecallPolicy = "graceful",
        preemption_grace: timedelta = timedelta(),
        wait: bool = False,
        conn: Any = None,
    ) -> LeaseDecision:
        async with acquire(self._pool, conn) as conn:
            # (D12) idempotent replay: a still-active lease with this key wins,
            # so a retried acquire never creates a duplicate.
            existing = await self._active_lease_by_key(conn, idempotency_key)
            if existing is not None:
                return LeaseGranted(
                    existing.lease_id, existing.expires_at, reasons.FOCUS_LEASE_GRANTED
                )

            current = await self._current_lease(conn, agent_id)
            if current is not None:
                if owner_type_outranks(owner_type, current.owner_type):
                    return LeasePreempting(
                        current.owner_ref, preemption_grace, reasons.FOCUS_LEASE_PREEMPTED
                    )
                if wait:
                    return LeaseRejected(
                        current.owner_ref, reasons.FOCUS_LEASE_QUEUEING_NOT_SUPPORTED
                    )
                return LeaseRejected(current.owner_ref, reasons.FOCUS_LEASE_CONFLICT)

            lease_id = uuid.uuid4().hex
            try:
                await conn.execute(
                    f"INSERT INTO focus_leases ({_COLUMNS}) "
                    "VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11)",
                    lease_id,
                    agent_id,
                    owner_type,
                    owner_ref,
                    datetime.now(UTC),
                    expires_at,
                    renewal_policy,
                    interruptibility,
                    recall_policy,
                    None,
                    idempotency_key,
                )
            except asyncpg.UniqueViolationError:
                # Lost the race for the single active-lease slot. Re-resolve: an
                # idempotent replay returns granted, otherwise it is a conflict.
                replay = await self._active_lease_by_key(conn, idempotency_key)
                if replay is not None:
                    return LeaseGranted(
                        replay.lease_id, replay.expires_at, reasons.FOCUS_LEASE_GRANTED
                    )
                current = await self._current_lease(conn, agent_id)
                holder_ref = current.owner_ref if current is not None else owner_ref
                return LeaseRejected(holder_ref, reasons.FOCUS_LEASE_CONFLICT)
            return LeaseGranted(lease_id, expires_at, reasons.FOCUS_LEASE_GRANTED)

    async def renew_lease(self, lease_id: str, *, expires_at: datetime | None = None) -> bool:
        async with self._pool.acquire() as conn:
            if expires_at is not None:
                result = await conn.execute(
                    "UPDATE focus_leases SET expires_at = $2, updated_at = now() "
                    "WHERE lease_id = $1 AND released_at IS NULL",
                    lease_id,
                    expires_at,
                )
            else:
                result = await conn.execute(
                    "UPDATE focus_leases SET updated_at = now() "
                    "WHERE lease_id = $1 AND released_at IS NULL",
                    lease_id,
                )
        # asyncpg returns e.g. "UPDATE 1"; "UPDATE 0" means no active lease matched.
        return result.split()[-1] != "0"

    async def release_lease(self, lease_id: str, reason_code: str, *, conn: Any = None) -> None:
        await self._mark_released(lease_id, conn=conn)

    async def revoke_lease(self, lease_id: str, reason_code: str, *, conn: Any = None) -> None:
        await self._mark_released(lease_id, conn=conn)

    async def get_current_lease(self, agent_id: str, *, conn: Any = None) -> FocusLease | None:
        async with acquire(self._pool, conn) as conn:
            return await self._current_lease(conn, agent_id)

    async def _mark_released(self, lease_id: str, *, conn: Any = None) -> None:
        """Free the active-lease slot. Shared by release (cooperative) and revoke
        (non-cooperative) — the storage effect is identical in v1.1; the audit
        distinction is carried by the coordinator's reason/event, not a column.
        The `released_at IS NULL` guard makes a repeated release/revoke a no-op."""
        async with acquire(self._pool, conn) as conn:
            await conn.execute(
                "UPDATE focus_leases SET released_at = now(), updated_at = now() "
                "WHERE lease_id = $1 AND released_at IS NULL",
                lease_id,
            )

    async def _active_lease_by_key(
        self, conn: asyncpg.Connection, idempotency_key: str
    ) -> FocusLease | None:
        if not idempotency_key:
            return None
        row = await conn.fetchrow(
            f"SELECT {_COLUMNS} FROM focus_leases "
            "WHERE idempotency_key = $1 AND released_at IS NULL "
            "ORDER BY acquired_at DESC LIMIT 1",
            idempotency_key,
        )
        return _row_to_lease(row) if row else None

    async def _current_lease(self, conn: asyncpg.Connection, agent_id: str) -> FocusLease | None:
        row = await conn.fetchrow(
            f"SELECT {_COLUMNS} FROM focus_leases WHERE agent_id = $1 AND released_at IS NULL",
            agent_id,
        )
        return _row_to_lease(row) if row else None


def _row_to_lease(row: asyncpg.Record) -> FocusLease:
    return FocusLease(
        lease_id=row["lease_id"],
        agent_id=row["agent_id"],
        owner_type=row["owner_type"],
        owner_ref=row["owner_ref"],
        acquired_at=row["acquired_at"],
        expires_at=row["expires_at"],
        renewal_policy=row["renewal_policy"],
        interruptibility=row["interruptibility"],
        recall_policy=row["recall_policy"],
        released_at=row["released_at"],
        idempotency_key=row["idempotency_key"],
    )
