"""Unit tests for SIP-0089 Phase 4 — RuntimeActivity model + adapter.

Bug classes guarded:
- `is_active_/is_terminal_activity_state` mis-bucketing a state (e.g. `paused`
  treated as terminal) — would corrupt the single-active-activity invariant (D9)
  and the get_current_activity filter;
- `start_activity` not opening in `running` / not stamping `started_at` — the
  activity would be invisible as the agent's current work;
- `update_state` stamping the wrong lifecycle timestamp (pause→ended_at, etc.);
- a terminal helper mapping to the wrong state (complete→failed);
- `get_current_activity` returning a terminal activity as "current";
- JSONB payloads silently dropped on the row→dataclass round-trip.

asyncpg fakes mirror `test_focus_lease.py`.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from adapters.persistence.runtime.activity_postgres import PostgresRuntimeActivity
from squadops.runtime.models import (
    RuntimeActivity,
    is_active_activity_state,
    is_terminal_activity_state,
)

pytestmark = [pytest.mark.domain_runtime]

NOW = datetime(2026, 6, 28, 12, 0, tzinfo=UTC)


# ---------------------------------------------------------------------------
# state classifiers
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("state", "active", "terminal"),
    [
        ("pending", True, False),
        ("running", True, False),
        ("paused", True, False),
        ("completed", False, True),
        ("aborted", False, True),
        ("failed", False, True),
    ],
)
def test_activity_state_classifiers(state, active, terminal):
    """Bug class: a mis-bucketed state breaks the D9 single-active invariant and
    the active/terminal split. active and terminal must partition the 6 states."""
    assert is_active_activity_state(state) is active
    assert is_terminal_activity_state(state) is terminal
    assert active != terminal  # exactly one bucket


# ---------------------------------------------------------------------------
# asyncpg fakes
# ---------------------------------------------------------------------------


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


def _activity_row(**overrides) -> dict:
    base = {
        "runtime_activity_id": "act-1",
        "agent_id": "max",
        "mode": "cycle",
        "activity_type": "design",
        "goal": "build the thing",
        "priority": 5,
        "state": "running",
        "source_kind": "cycle_task",
        "cycle_id": "cyc-1",
        "workload_id": None,
        "task_id": "task-7",
        "source_ref": "task-7",
        "can_pause": True,
        "can_resume": True,
        "can_abort": True,
        "completion_conditions": "[]",
        "evidence_requirements": "[]",
        "started_at": NOW,
        "paused_at": None,
        "ended_at": None,
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# start_activity
# ---------------------------------------------------------------------------


async def test_start_activity_opens_running_with_started_at_and_minted_id():
    """Bug class: a new activity must open in `running` with a stamped
    `started_at` and a minted id, or it won't register as the agent's current
    work. JSONB payloads are serialized via json.dumps."""
    conn = AsyncMock()
    conn.fetchrow.return_value = _activity_row()
    adapter = PostgresRuntimeActivity(_make_pool(conn))

    activity = await adapter.start_activity(
        "max",
        mode="cycle",
        activity_type="design",
        goal="build the thing",
        source_kind="cycle_task",
        source_ref="task-7",
        task_id="task-7",
        cycle_id="cyc-1",
        completion_conditions=({"kind": "tests_pass"},),
    )

    assert isinstance(activity, RuntimeActivity)
    args = conn.fetchrow.await_args.args
    query = args[0]
    assert "INSERT INTO runtime_activities" in query
    assert "'running'" in query  # state literal, not a bind param
    assert len(args[1]) == 32  # uuid4().hex minted id
    # completion_conditions serialized as JSON text (param order: ...,$15,$16,$17)
    assert json.loads(args[15]) == [{"kind": "tests_pass"}]
    assert isinstance(args[-1], datetime)  # started_at stamped


# ---------------------------------------------------------------------------
# update_state — timestamp management
# ---------------------------------------------------------------------------


async def test_update_state_pause_stamps_paused_at_only():
    """Bug class: pausing must stamp paused_at, NOT ended_at (a paused activity
    isn't terminal). started_at must be left alone."""
    conn = AsyncMock()
    conn.fetchrow.return_value = _activity_row(state="paused", paused_at=NOW)
    adapter = PostgresRuntimeActivity(_make_pool(conn))

    await adapter.update_state("act-1", "paused")

    set_clause = conn.fetchrow.await_args.args[0].split("SET", 1)[1].split("WHERE", 1)[0]
    assert "paused_at = now()" in set_clause
    assert "ended_at" not in set_clause
    assert "started_at" not in set_clause


async def test_update_state_terminal_stamps_ended_at():
    """Bug class: a terminal transition must stamp ended_at so duration/terminality
    is recorded, and must not stamp paused_at."""
    conn = AsyncMock()
    conn.fetchrow.return_value = _activity_row(state="completed", ended_at=NOW)
    adapter = PostgresRuntimeActivity(_make_pool(conn))

    await adapter.update_state("act-1", "completed")

    set_clause = conn.fetchrow.await_args.args[0].split("SET", 1)[1].split("WHERE", 1)[0]
    assert "ended_at = now()" in set_clause
    assert "paused_at" not in set_clause


async def test_update_state_running_preserves_original_started_at():
    """Bug class: resuming to running must NOT reset started_at (it's the original
    start) — COALESCE keeps the stored value while initializing if somehow null."""
    conn = AsyncMock()
    conn.fetchrow.return_value = _activity_row(state="running")
    adapter = PostgresRuntimeActivity(_make_pool(conn))

    await adapter.update_state("act-1", "running")

    set_clause = conn.fetchrow.await_args.args[0].split("SET", 1)[1].split("WHERE", 1)[0]
    assert "started_at = COALESCE(started_at, now())" in set_clause
    assert "ended_at" not in set_clause


async def test_update_state_returns_none_when_activity_absent():
    """Bug class: updating an unknown activity must report None, not raise — the
    instrumentation path is best-effort."""
    conn = AsyncMock()
    conn.fetchrow.return_value = None
    adapter = PostgresRuntimeActivity(_make_pool(conn))

    assert await adapter.update_state("ghost", "completed") is None


# ---------------------------------------------------------------------------
# terminal helpers
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("method", "kwargs", "expected_state"),
    [
        ("complete_activity", {"evidence_ref": "art-9"}, "completed"),
        ("fail_activity", {"reason_code": "boom"}, "failed"),
        ("abort_activity", {"reason_code": "preempted"}, "aborted"),
    ],
)
async def test_terminal_helpers_map_to_correct_state(method, kwargs, expected_state):
    """Bug class: a terminal helper wired to the wrong state (complete→failed)
    would mislabel outcomes. Each helper must drive its own terminal state."""
    conn = AsyncMock()
    conn.fetchrow.return_value = _activity_row(state=expected_state, ended_at=NOW)
    adapter = PostgresRuntimeActivity(_make_pool(conn))

    result = await getattr(adapter, method)("act-1", **kwargs)

    assert result is not None and result.state == expected_state
    # state bind param (the 2nd positional after the query) carries the terminal state
    assert conn.fetchrow.await_args.args[2] == expected_state


# ---------------------------------------------------------------------------
# get_current_activity + row mapping
# ---------------------------------------------------------------------------


async def test_get_current_activity_filters_to_active_states():
    """Bug class: 'current' must mean an ACTIVE activity. The query must restrict
    to pending/running/paused so a finished activity is never returned as current."""
    conn = AsyncMock()
    conn.fetchrow.return_value = None
    adapter = PostgresRuntimeActivity(_make_pool(conn))

    assert await adapter.get_current_activity("idle") is None
    query = conn.fetchrow.await_args.args[0]
    assert "state IN ('pending', 'running', 'paused')" in query


async def test_row_to_activity_decodes_jsonb_and_maps_all_fields():
    """Bug class: a row→dataclass mapper that drops a field or fails to decode the
    JSONB payloads would degrade observability silently."""
    conn = AsyncMock()
    conn.fetchrow.return_value = _activity_row(
        completion_conditions='[{"kind": "tests_pass"}]',
        evidence_requirements='[{"artifact": "report"}]',
        workload_id="wl-3",
    )
    adapter = PostgresRuntimeActivity(_make_pool(conn))

    activity = await adapter.get_current_activity("max")

    assert activity == RuntimeActivity(
        runtime_activity_id="act-1",
        agent_id="max",
        mode="cycle",
        activity_type="design",
        goal="build the thing",
        priority=5,
        state="running",
        source_kind="cycle_task",
        source_ref="task-7",
        cycle_id="cyc-1",
        workload_id="wl-3",
        task_id="task-7",
        can_pause=True,
        can_resume=True,
        can_abort=True,
        completion_conditions=({"kind": "tests_pass"},),
        evidence_requirements=({"artifact": "report"},),
        started_at=NOW,
        paused_at=None,
        ended_at=None,
    )
