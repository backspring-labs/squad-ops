"""Postgres-backed runtime-state adapter (SIP-0089 §1.3).

Implements `RuntimeStatePort` via the existing asyncpg connection pool used
by the cycle registry. All writes hit `agent_runtime_state` (migration
`1100_agent_runtime_state.sql`).

`ensure_state` and `update_heartbeat` preserve D17's non-authoritative
semantics: heartbeat never overwrites coordinator-owned fields
(`mode`, `focus`, `current_assignment_ref`, `current_runtime_activity_id`).
"""

from __future__ import annotations

from datetime import UTC, datetime

import asyncpg

from squadops.ports.runtime.state import RuntimeStatePort
from squadops.runtime.models import AgentRuntimeState

_DEFAULT_MODE = "ambient"
_DEFAULT_RUNTIME_STATUS = "online"
_DEFAULT_INTERRUPTIBILITY = "high"
_DEFAULT_FOCUS = ""


class PostgresRuntimeState(RuntimeStatePort):
    """Postgres-backed `RuntimeStatePort` implementation."""

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def get_state(self, agent_id: str) -> AgentRuntimeState | None:
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT agent_id, mode, runtime_status, focus, "
                "current_runtime_activity_id, interruptibility, "
                "last_heartbeat_at, current_assignment_ref "
                "FROM agent_runtime_state WHERE agent_id = $1",
                agent_id,
            )
        return _row_to_state(row) if row else None

    async def upsert_state(self, state: AgentRuntimeState) -> AgentRuntimeState:
        async with self._pool.acquire() as conn:
            await conn.execute(
                "INSERT INTO agent_runtime_state ("
                "agent_id, mode, runtime_status, focus, "
                "current_runtime_activity_id, interruptibility, "
                "last_heartbeat_at, current_assignment_ref"
                ") VALUES ($1,$2,$3,$4,$5,$6,$7,$8) "
                "ON CONFLICT (agent_id) DO UPDATE SET "
                "mode = EXCLUDED.mode, "
                "runtime_status = EXCLUDED.runtime_status, "
                "focus = EXCLUDED.focus, "
                "current_runtime_activity_id = EXCLUDED.current_runtime_activity_id, "
                "interruptibility = EXCLUDED.interruptibility, "
                "last_heartbeat_at = EXCLUDED.last_heartbeat_at, "
                "current_assignment_ref = EXCLUDED.current_assignment_ref, "
                "updated_at = now()",
                state.agent_id,
                state.mode,
                state.runtime_status,
                state.focus,
                state.current_runtime_activity_id,
                state.interruptibility,
                state.last_heartbeat_at,
                state.current_assignment_ref,
            )
        return state

    async def ensure_state(self, agent_id: str) -> AgentRuntimeState:
        now = datetime.now(UTC)
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                "INSERT INTO agent_runtime_state ("
                "agent_id, mode, runtime_status, focus, interruptibility, "
                "last_heartbeat_at"
                ") VALUES ($1,$2,$3,$4,$5,$6) "
                "ON CONFLICT (agent_id) DO UPDATE SET agent_id = EXCLUDED.agent_id "
                "RETURNING agent_id, mode, runtime_status, focus, "
                "current_runtime_activity_id, interruptibility, "
                "last_heartbeat_at, current_assignment_ref",
                agent_id,
                _DEFAULT_MODE,
                _DEFAULT_RUNTIME_STATUS,
                _DEFAULT_FOCUS,
                _DEFAULT_INTERRUPTIBILITY,
                now,
            )
        return _row_to_state(row)

    async def update_heartbeat(
        self,
        agent_id: str,
        *,
        runtime_status: str | None = None,
    ) -> AgentRuntimeState:
        await self.ensure_state(agent_id)
        now = datetime.now(UTC)
        async with self._pool.acquire() as conn:
            if runtime_status is not None:
                row = await conn.fetchrow(
                    "UPDATE agent_runtime_state "
                    "SET last_heartbeat_at = $2, runtime_status = $3, "
                    "updated_at = now() "
                    "WHERE agent_id = $1 "
                    "RETURNING agent_id, mode, runtime_status, focus, "
                    "current_runtime_activity_id, interruptibility, "
                    "last_heartbeat_at, current_assignment_ref",
                    agent_id,
                    now,
                    runtime_status,
                )
            else:
                row = await conn.fetchrow(
                    "UPDATE agent_runtime_state "
                    "SET last_heartbeat_at = $2, updated_at = now() "
                    "WHERE agent_id = $1 "
                    "RETURNING agent_id, mode, runtime_status, focus, "
                    "current_runtime_activity_id, interruptibility, "
                    "last_heartbeat_at, current_assignment_ref",
                    agent_id,
                    now,
                )
        return _row_to_state(row)


def _row_to_state(row: asyncpg.Record) -> AgentRuntimeState:
    return AgentRuntimeState(
        agent_id=row["agent_id"],
        mode=row["mode"],
        runtime_status=row["runtime_status"],
        focus=row["focus"],
        current_runtime_activity_id=row["current_runtime_activity_id"],
        interruptibility=row["interruptibility"],
        last_heartbeat_at=row["last_heartbeat_at"],
        current_assignment_ref=row["current_assignment_ref"],
    )
