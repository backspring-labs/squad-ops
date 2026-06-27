"""Unit tests for SIP-0089 §2.3 — PostgresAssignment adapter.

Two bug classes are guarded:
- Row→dataclass mapping drift: the flat window columns must reassemble into the
  nested `DutyWindow`, and the TEXT[] must become a tuple (a frozen-dataclass
  field) — a list would silently break equality/hashing.
- Time-predicate drift in the scheduler/guard queries: the reserve-buffer
  interval arithmetic is the whole point of pushing these into SQL, so the
  predicates and the `now` binding are asserted directly.

asyncpg-mock pattern mirrors test_agent_runtime_state.py.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest

from adapters.persistence.runtime.assignments_postgres import PostgresAssignment
from squadops.runtime.models import Assignment, DutyWindow

pytestmark = [pytest.mark.domain_runtime]

WIN_START = datetime(2026, 6, 24, 1, 0, tzinfo=UTC)
WIN_END = datetime(2026, 6, 24, 6, 0, tzinfo=UTC)
NOW = datetime(2026, 6, 24, 3, 0, tzinfo=UTC)


class _AcquireCtx:
    def __init__(self, conn):
        self._conn = conn

    async def __aenter__(self):
        return self._conn

    async def __aexit__(self, *_):
        return False


def _make_pool(conn):
    pool = MagicMock()
    pool.acquire.return_value = _AcquireCtx(conn)
    return pool


def _row(**overrides) -> dict:
    base = {
        "assignment_id": "a-1",
        "agent_id": "max",
        "assignment_type": "duty",
        "assigned_role": "support",
        "priority": 10,
        "strictness": "hard",
        "window_start": WIN_START,
        "window_end": WIN_END,
        "timezone": "UTC",
        "reserve_before_window": timedelta(minutes=15),
        "reserve_after_window": timedelta(minutes=10),
        "recall_policy": "graceful",
        "graceful_window": timedelta(minutes=5),
        "missed_window_policy": "require_operator_review",
        "allowed_off_window_modes": ["ambient", "cycle"],  # asyncpg returns a list
        "active": True,
    }
    base.update(overrides)
    return base


def _assignment() -> Assignment:
    return Assignment(
        assignment_id="a-1",
        agent_id="max",
        assignment_type="duty",
        assigned_role="support",
        priority=10,
        strictness="hard",
        active_window=DutyWindow(start=WIN_START, end=WIN_END, timezone="UTC"),
        reserve_before_window=timedelta(minutes=15),
        reserve_after_window=timedelta(minutes=10),
        recall_policy="graceful",
        graceful_window=timedelta(minutes=5),
        missed_window_policy="require_operator_review",
        allowed_off_window_modes=("ambient", "cycle"),
        active=True,
    )


async def test_get_assignment_maps_row_including_nested_window_and_tuple():
    """Bug class: a mapper that left the window columns flat, or kept the TEXT[]
    as a list, would not equal the canonical dataclass — and the list would make
    the frozen Assignment unhashable. This asserts the full reconstruction."""
    conn = AsyncMock()
    conn.fetchrow.return_value = _row()
    adapter = PostgresAssignment(_make_pool(conn))

    assert await adapter.get_assignment("a-1") == _assignment()


async def test_get_assignment_returns_none_when_absent():
    """Bug class: callers must distinguish 'no such assignment' from a default;
    a synthetic default row would corrupt scheduling decisions."""
    conn = AsyncMock()
    conn.fetchrow.return_value = None
    adapter = PostgresAssignment(_make_pool(conn))

    assert await adapter.get_assignment("missing") is None


async def test_list_assignments_for_agent_returns_all_of_an_agents_assignments():
    """Bug class (§10.2 cardinality — an agent may hold MULTIPLE assignments): a
    query that collapsed to one row per agent (e.g. fetchrow, DISTINCT ON
    agent_id, or a stray LIMIT) would silently hide an agent's other commitments,
    so the scheduler would never open the second window. Assert both rows survive,
    keyed to the same agent, filtered by agent_id and ordered by window_start."""
    later_start = WIN_START + timedelta(days=1)
    conn = AsyncMock()
    conn.fetch.return_value = [
        _row(assignment_id="a-1"),
        _row(assignment_id="a-2", window_start=later_start),
    ]
    adapter = PostgresAssignment(_make_pool(conn))

    result = await adapter.list_assignments_for_agent("max")

    assert [a.assignment_id for a in result] == ["a-1", "a-2"]
    assert {a.agent_id for a in result} == {"max"}
    sql, *args = conn.fetch.call_args.args
    assert "WHERE agent_id = $1" in sql
    assert "ORDER BY window_start" in sql
    assert "LIMIT" not in sql.upper()  # never truncate an agent's commitments
    assert args == ["max"]


async def test_list_active_assignments_predicate_and_binding():
    """Bug class: the active set must be `active = TRUE` AND now inside the full
    reserve span [start - before, end + after). Dropping either buffer term would
    make the §2.5 guard miss a reserve conflict."""
    conn = AsyncMock()
    conn.fetch.return_value = [_row()]
    adapter = PostgresAssignment(_make_pool(conn))

    result = await adapter.list_active_assignments(NOW)

    assert [a.assignment_id for a in result] == ["a-1"]
    sql, *args = conn.fetch.call_args.args
    assert "active = TRUE" in sql
    assert "$1 >= window_start - reserve_before_window" in sql
    assert "$1 <  window_end + reserve_after_window" in sql
    assert args == [NOW]  # `now` is the sole bind param


async def test_list_claimable_windows_filters_duty_and_ends_at_window_close():
    """Bug class: claimable must be duty-only and end at window close, NOT at the
    trailing reserve buffer — including the after-buffer would keep requesting a
    transition for a window that has already ended."""
    conn = AsyncMock()
    conn.fetch.return_value = []
    adapter = PostgresAssignment(_make_pool(conn))

    await adapter.list_claimable_windows(NOW)

    sql, *args = conn.fetch.call_args.args
    assert "assignment_type = 'duty'" in sql
    assert "$1 <  window_end " in sql
    assert "window_end + reserve_after_window" not in sql  # claim ends at close
    assert args == [NOW]


async def test_upsert_assignment_flattens_window_and_binds_array_as_list():
    """Bug class: the nested DutyWindow must flatten to the window_start/_end/
    timezone binds, and the tuple field must bind as a list — asyncpg array
    params reject a tuple, so a silent type slip would fail only at runtime."""
    conn = AsyncMock()
    adapter = PostgresAssignment(_make_pool(conn))
    a = _assignment()

    returned = await adapter.upsert_assignment(a)

    assert returned is a
    sql, *args = conn.execute.call_args.args
    assert "ON CONFLICT (assignment_id) DO UPDATE" in sql
    assert args[6] == WIN_START  # $7 window_start
    assert args[7] == WIN_END  # $8 window_end
    assert args[8] == "UTC"  # $9 timezone
    assert args[14] == ["ambient", "cycle"]  # $15 TEXT[] bound as list
    assert isinstance(args[14], list)
