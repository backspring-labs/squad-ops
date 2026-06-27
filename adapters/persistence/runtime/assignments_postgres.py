"""Postgres-backed Assignment adapter (SIP-0089 §2.3).

Implements `AssignmentPort` via the asyncpg pool shared with the cycle registry
and runtime-state adapter. All rows hit `agent_assignments` (migration
`1110_assignments.sql`).

The flat `window_start`/`window_end`/`timezone` columns are reassembled into the
nested `DutyWindow` on read; INTERVAL columns map to `timedelta` and the
`allowed_off_window_modes` TEXT[] maps to a tuple (the dataclass is frozen).
The reserve-buffer interval arithmetic for the active/claimable queries runs in
SQL so callers never over-fetch.
"""

from __future__ import annotations

from datetime import datetime

import asyncpg

from squadops.ports.runtime.assignments import AssignmentPort
from squadops.runtime.models import Assignment, DutyWindow

_COLUMNS = (
    "assignment_id, agent_id, assignment_type, assigned_role, priority, "
    "strictness, window_start, window_end, timezone, reserve_before_window, "
    "reserve_after_window, recall_policy, graceful_window, missed_window_policy, "
    "allowed_off_window_modes, active"
)


class PostgresAssignment(AssignmentPort):
    """Postgres-backed `AssignmentPort` implementation."""

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def get_assignment(self, assignment_id: str) -> Assignment | None:
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                f"SELECT {_COLUMNS} FROM agent_assignments WHERE assignment_id = $1",
                assignment_id,
            )
        return _row_to_assignment(row) if row else None

    async def list_assignments_for_agent(self, agent_id: str) -> list[Assignment]:
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                f"SELECT {_COLUMNS} FROM agent_assignments "
                "WHERE agent_id = $1 ORDER BY window_start",
                agent_id,
            )
        return [_row_to_assignment(r) for r in rows]

    async def list_active_assignments(self, now: datetime) -> list[Assignment]:
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                f"SELECT {_COLUMNS} FROM agent_assignments "
                "WHERE active = TRUE "
                "AND $1 >= window_start - reserve_before_window "
                "AND $1 <  window_end + reserve_after_window "
                "ORDER BY window_start",
                now,
            )
        return [_row_to_assignment(r) for r in rows]

    async def list_claimable_windows(self, now: datetime) -> list[Assignment]:
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                f"SELECT {_COLUMNS} FROM agent_assignments "
                "WHERE active = TRUE "
                "AND assignment_type = 'duty' "
                "AND $1 >= window_start - reserve_before_window "
                "AND $1 <  window_end "
                "ORDER BY window_start",
                now,
            )
        return [_row_to_assignment(r) for r in rows]

    async def upsert_assignment(self, assignment: Assignment) -> Assignment:
        a = assignment
        async with self._pool.acquire() as conn:
            await conn.execute(
                "INSERT INTO agent_assignments ("
                "assignment_id, agent_id, assignment_type, assigned_role, priority, "
                "strictness, window_start, window_end, timezone, reserve_before_window, "
                "reserve_after_window, recall_policy, graceful_window, missed_window_policy, "
                "allowed_off_window_modes, active"
                ") VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16) "
                "ON CONFLICT (assignment_id) DO UPDATE SET "
                "agent_id = EXCLUDED.agent_id, "
                "assignment_type = EXCLUDED.assignment_type, "
                "assigned_role = EXCLUDED.assigned_role, "
                "priority = EXCLUDED.priority, "
                "strictness = EXCLUDED.strictness, "
                "window_start = EXCLUDED.window_start, "
                "window_end = EXCLUDED.window_end, "
                "timezone = EXCLUDED.timezone, "
                "reserve_before_window = EXCLUDED.reserve_before_window, "
                "reserve_after_window = EXCLUDED.reserve_after_window, "
                "recall_policy = EXCLUDED.recall_policy, "
                "graceful_window = EXCLUDED.graceful_window, "
                "missed_window_policy = EXCLUDED.missed_window_policy, "
                "allowed_off_window_modes = EXCLUDED.allowed_off_window_modes, "
                "active = EXCLUDED.active, "
                "updated_at = now()",
                a.assignment_id,
                a.agent_id,
                a.assignment_type,
                a.assigned_role,
                a.priority,
                a.strictness,
                a.active_window.start,
                a.active_window.end,
                a.active_window.timezone,
                a.reserve_before_window,
                a.reserve_after_window,
                a.recall_policy,
                a.graceful_window,
                a.missed_window_policy,
                list(a.allowed_off_window_modes),
                a.active,
            )
        return a


def _row_to_assignment(row: asyncpg.Record) -> Assignment:
    return Assignment(
        assignment_id=row["assignment_id"],
        agent_id=row["agent_id"],
        assignment_type=row["assignment_type"],
        assigned_role=row["assigned_role"],
        priority=row["priority"],
        strictness=row["strictness"],
        active_window=DutyWindow(
            start=row["window_start"],
            end=row["window_end"],
            timezone=row["timezone"],
        ),
        reserve_before_window=row["reserve_before_window"],
        reserve_after_window=row["reserve_after_window"],
        recall_policy=row["recall_policy"],
        graceful_window=row["graceful_window"],
        missed_window_policy=row["missed_window_policy"],
        allowed_off_window_modes=tuple(row["allowed_off_window_modes"]),
        active=row["active"],
    )
