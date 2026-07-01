"""Postgres-backed RuntimeActivity adapter (SIP-0089 §4.3).

Implements `RuntimeActivityPort` via the asyncpg pool shared with the cycle
registry and the other runtime adapters. All rows hit `runtime_activities`
(migration `1130_runtime_activities.sql`).

`start_activity` inserts a `running` activity; the §4.2 partial unique index
enforces the single-active-activity invariant (D9), so a second active start for
the same agent raises `UniqueViolationError` — the §4.4 instrumentation treats
activity calls as best-effort and swallows it so observability never breaks a
real task. `update_state` manages the lifecycle timestamps; the terminal helpers
are thin wrappers over it (their reason/evidence is event-surfaced, not stored).

JSONB columns (`completion_conditions`/`evidence_requirements`) follow the cycle
registry convention: `json.dumps` on write, decode on read.
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from typing import Any

import asyncpg

from adapters.persistence.runtime._conn import acquire
from squadops.ports.runtime.activity import RuntimeActivityPort
from squadops.runtime.models import (
    ActivitySourceKind,
    ActivityState,
    RuntimeActivity,
    RuntimeMode,
    is_terminal_activity_state,
)

_COLUMNS = (
    "runtime_activity_id, agent_id, mode, activity_type, goal, priority, state, "
    "source_kind, cycle_id, workload_id, task_id, source_ref, can_pause, can_resume, "
    "can_abort, completion_conditions, evidence_requirements, started_at, paused_at, ended_at"
)


class PostgresRuntimeActivity(RuntimeActivityPort):
    """Postgres-backed `RuntimeActivityPort` implementation."""

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def start_activity(
        self,
        agent_id: str,
        *,
        mode: RuntimeMode,
        activity_type: str,
        goal: str,
        source_kind: ActivitySourceKind,
        source_ref: str,
        priority: int = 0,
        cycle_id: str | None = None,
        workload_id: str | None = None,
        task_id: str | None = None,
        can_pause: bool = False,
        can_resume: bool = False,
        can_abort: bool = True,
        completion_conditions: tuple[dict, ...] = (),
        evidence_requirements: tuple[dict, ...] = (),
    ) -> RuntimeActivity:
        activity_id = uuid.uuid4().hex
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                "INSERT INTO runtime_activities ("
                "runtime_activity_id, agent_id, mode, activity_type, goal, priority, state, "
                "source_kind, cycle_id, workload_id, task_id, source_ref, can_pause, can_resume, "
                "can_abort, completion_conditions, evidence_requirements, started_at"
                ") VALUES ($1,$2,$3,$4,$5,$6,'running',$7,$8,$9,$10,$11,$12,$13,$14,$15,$16,$17) "
                f"RETURNING {_COLUMNS}",
                activity_id,
                agent_id,
                mode,
                activity_type,
                goal,
                priority,
                source_kind,
                cycle_id,
                workload_id,
                task_id,
                source_ref,
                can_pause,
                can_resume,
                can_abort,
                json.dumps(list(completion_conditions)),
                json.dumps(list(evidence_requirements)),
                datetime.now(UTC),
            )
        return _row_to_activity(row)

    async def update_state(
        self, activity_id: str, state: ActivityState, *, conn: Any = None
    ) -> RuntimeActivity | None:
        # Timestamp management is intrinsic to the state being entered: pausing
        # stamps paused_at, a terminal state stamps ended_at, and (re)entering
        # running ensures started_at is set without clobbering the original.
        sets = ["state = $2", "updated_at = now()"]
        if state == "paused":
            sets.append("paused_at = now()")
        elif is_terminal_activity_state(state):
            sets.append("ended_at = now()")
        elif state == "running":
            sets.append("started_at = COALESCE(started_at, now())")
        # Only an ACTIVE activity may transition: terminal states are final, so a
        # terminal row never moves again. This makes terminalization race-safe —
        # if the owning handler completes an activity the coordinator just aborted
        # (or vice versa), the second writer matches no row and gets None.
        async with acquire(self._pool, conn) as conn:
            row = await conn.fetchrow(
                f"UPDATE runtime_activities SET {', '.join(sets)} "
                "WHERE runtime_activity_id = $1 "
                "AND state IN ('pending', 'running', 'paused') "
                f"RETURNING {_COLUMNS}",
                activity_id,
                state,
            )
        return _row_to_activity(row) if row else None

    async def complete_activity(
        self, activity_id: str, *, evidence_ref: str | None = None
    ) -> RuntimeActivity | None:
        return await self.update_state(activity_id, "completed")

    async def fail_activity(self, activity_id: str, reason_code: str) -> RuntimeActivity | None:
        return await self.update_state(activity_id, "failed")

    async def abort_activity(
        self, activity_id: str, reason_code: str, *, conn: Any = None
    ) -> RuntimeActivity | None:
        return await self.update_state(activity_id, "aborted", conn=conn)

    async def get_current_activity(
        self, agent_id: str, *, conn: Any = None
    ) -> RuntimeActivity | None:
        async with acquire(self._pool, conn) as conn:
            row = await conn.fetchrow(
                f"SELECT {_COLUMNS} FROM runtime_activities "
                "WHERE agent_id = $1 AND state IN ('pending', 'running', 'paused')",
                agent_id,
            )
        return _row_to_activity(row) if row else None


def _loads_jsonb(value) -> list:
    """Decode a JSONB column value (asyncpg returns str by default)."""
    if value is None:
        return []
    if isinstance(value, str):
        return json.loads(value)
    return value  # already decoded (e.g. with a custom codec)


def _row_to_activity(row: asyncpg.Record) -> RuntimeActivity:
    return RuntimeActivity(
        runtime_activity_id=row["runtime_activity_id"],
        agent_id=row["agent_id"],
        mode=row["mode"],
        activity_type=row["activity_type"],
        goal=row["goal"],
        priority=row["priority"],
        state=row["state"],
        source_kind=row["source_kind"],
        source_ref=row["source_ref"],
        cycle_id=row["cycle_id"],
        workload_id=row["workload_id"],
        task_id=row["task_id"],
        can_pause=row["can_pause"],
        can_resume=row["can_resume"],
        can_abort=row["can_abort"],
        completion_conditions=tuple(_loads_jsonb(row["completion_conditions"])),
        evidence_requirements=tuple(_loads_jsonb(row["evidence_requirements"])),
        started_at=row["started_at"],
        paused_at=row["paused_at"],
        ended_at=row["ended_at"],
    )
