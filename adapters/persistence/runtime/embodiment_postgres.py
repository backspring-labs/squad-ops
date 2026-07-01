"""Postgres-backed embodiment-state adapter (SIP-0090 Phase 1 §5, slice 1b).

Implements `EmbodimentStatePort` via the shared asyncpg pool. All writes hit
`embodiments` (migration `1140_embodiments.sql`). The single-active-embodiment
invariant (§5.5) is enforced in the DB by the partial unique index
`uq_embodiments_one_active_per_agent` — the hard backstop behind the
EmbodimentCoordinator's logic-level guard.

`capability_set` is a JSONB array (`json.dumps` on write, decode on read — the cycle
registry convention). Mutating methods carry the §4.5/D25 `conn` seam so a Phase-3
coordinator can commit an embodiment transition atomically with other writes.
"""

from __future__ import annotations

import json
from typing import Any

import asyncpg

from adapters.persistence.runtime._conn import acquire
from squadops.ports.runtime.embodiment import EmbodimentStatePort
from squadops.runtime.embodiment import AttachmentState, Embodiment, Health

_ACTIVE_STATES = ["attached", "desynced", "reconnecting"]

_COLS = (
    "embodiment_id, agent_id, embodiment_type, platform, attachment_state, health, "
    "capability_set, location_ref, last_health_check_at, credentials_ref"
)


class PostgresEmbodimentState(EmbodimentStatePort):
    """Postgres-backed `EmbodimentStatePort` implementation."""

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def create_embodiment(self, embodiment: Embodiment, *, conn: Any = None) -> Embodiment:
        async with acquire(self._pool, conn) as c:
            await c.execute(
                f"INSERT INTO embodiments ({_COLS}) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10)",
                embodiment.embodiment_id,
                embodiment.agent_id,
                embodiment.embodiment_type,
                embodiment.platform,
                embodiment.attachment_state,
                embodiment.health,
                json.dumps(list(embodiment.capability_set)),
                embodiment.location_ref,
                embodiment.last_health_check_at,
                embodiment.credentials_ref,
            )
        return embodiment

    async def get_embodiment(self, embodiment_id: str) -> Embodiment | None:
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                f"SELECT {_COLS} FROM embodiments WHERE embodiment_id = $1", embodiment_id
            )
        return _row_to_embodiment(row) if row else None

    async def get_active_embodiment(self, agent_id: str) -> Embodiment | None:
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                f"SELECT {_COLS} FROM embodiments "
                "WHERE agent_id = $1 AND attachment_state = ANY($2::text[])",
                agent_id,
                _ACTIVE_STATES,
            )
        return _row_to_embodiment(row) if row else None

    async def list_for_agent(self, agent_id: str) -> tuple[Embodiment, ...]:
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                f"SELECT {_COLS} FROM embodiments WHERE agent_id = $1 ORDER BY created_at",
                agent_id,
            )
        return tuple(_row_to_embodiment(r) for r in rows)

    async def transition_state(
        self, embodiment_id: str, target_state: AttachmentState, *, conn: Any = None
    ) -> Embodiment:
        return await self._update_returning(
            "attachment_state", embodiment_id, target_state, conn=conn
        )

    async def update_health(
        self, embodiment_id: str, health: Health, *, conn: Any = None
    ) -> Embodiment:
        return await self._update_returning("health", embodiment_id, health, conn=conn)

    async def update_location(
        self, embodiment_id: str, location_ref: str | None, *, conn: Any = None
    ) -> Embodiment:
        return await self._update_returning("location_ref", embodiment_id, location_ref, conn=conn)

    async def _update_returning(
        self, column: str, embodiment_id: str, value: Any, *, conn: Any
    ) -> Embodiment:
        # `column` is always an internal literal (never caller input) — no injection.
        async with acquire(self._pool, conn) as c:
            row = await c.fetchrow(
                f"UPDATE embodiments SET {column} = $2, updated_at = now() "
                f"WHERE embodiment_id = $1 RETURNING {_COLS}",
                embodiment_id,
                value,
            )
        if row is None:
            raise KeyError(f"embodiment not found: {embodiment_id}")
        return _row_to_embodiment(row)


def _loads_jsonb(value: Any) -> list:
    """Decode a JSONB column value (asyncpg returns str by default)."""
    if value is None:
        return []
    if isinstance(value, list | tuple):
        return list(value)
    return json.loads(value)


def _row_to_embodiment(row: asyncpg.Record) -> Embodiment:
    return Embodiment(
        embodiment_id=row["embodiment_id"],
        agent_id=row["agent_id"],
        embodiment_type=row["embodiment_type"],
        platform=row["platform"],
        attachment_state=row["attachment_state"],
        health=row["health"],
        capability_set=tuple(_loads_jsonb(row["capability_set"])),
        location_ref=row["location_ref"],
        last_health_check_at=row["last_health_check_at"],
        credentials_ref=row["credentials_ref"],
    )
