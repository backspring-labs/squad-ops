"""Unit tests for SIP-0089 Phase 1 runtime-state primitives.

Covers:
- `runtime_status_from_lifecycle` mapper (pure logic — every branch).
- `PostgresRuntimeState` adapter behaviors that protect D17
  non-authoritative heartbeat semantics (the real concurrency bug class
  this design exists to prevent).

Each test answers: what bug would it catch?
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from adapters.persistence.runtime.state_postgres import PostgresRuntimeState
from squadops.runtime.lifecycle_status import runtime_status_from_lifecycle
from squadops.runtime.models import AgentRuntimeState

pytestmark = [pytest.mark.domain_runtime]

NOW = datetime(2026, 5, 17, 12, 0, 0, tzinfo=UTC)


# ---------------------------------------------------------------------------
# lifecycle_status mapper — parametrized
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("lifecycle", "expected"),
    [
        ("STARTING", "recovering"),
        ("READY", "online"),
        ("WORKING", "online"),
        ("BLOCKED", "degraded"),
        ("CRASHED", "offline"),
        ("STOPPING", "recovering"),
    ],
)
def test_lifecycle_status_known_values_map_correctly(lifecycle, expected):
    """Bug class: silent drift if a lifecycle_state maps to the wrong health bucket."""
    assert runtime_status_from_lifecycle(lifecycle) == expected


@pytest.mark.parametrize("lifecycle", ["", "UNKNOWN", "running", "online", "duty"])
def test_lifecycle_status_unknown_returns_none(lifecycle):
    """Bug class: defaulting unknown values to a real status would mask drift
    (e.g. a typo or future lifecycle vocab change writing `online` for everything).
    Returning None forces the caller to skip the update."""
    assert runtime_status_from_lifecycle(lifecycle) is None


# ---------------------------------------------------------------------------
# asyncpg pool/connection fakes — pattern matches test_postgres_cycle_registry
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


def _state_row(**overrides) -> dict:
    base = {
        "agent_id": "max",
        "mode": "ambient",
        "runtime_status": "online",
        "focus": "",
        "current_runtime_activity_id": None,
        "interruptibility": "high",
        "last_heartbeat_at": NOW,
        "current_assignment_ref": None,
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# Adapter behaviors that protect D17
# ---------------------------------------------------------------------------


async def test_get_state_returns_none_when_no_row():
    """Bug class: callers must distinguish 'agent has never heartbeated' from 'agent
    is in default state'. Raising or returning a synthetic default would erase that
    distinction."""
    conn = AsyncMock()
    conn.fetchrow.return_value = None
    adapter = PostgresRuntimeState(_make_pool(conn))

    assert await adapter.get_state("missing-agent") is None


async def test_get_state_maps_row_to_dataclass():
    """Bug class: a row→dataclass mapper that silently drops fields would degrade
    observability without failing tests."""
    conn = AsyncMock()
    conn.fetchrow.return_value = _state_row(
        mode="duty",
        focus="customer_support",
        current_assignment_ref="assign-42",
    )
    adapter = PostgresRuntimeState(_make_pool(conn))

    state = await adapter.get_state("max")

    assert state == AgentRuntimeState(
        agent_id="max",
        mode="duty",
        runtime_status="online",
        focus="customer_support",
        current_runtime_activity_id=None,
        interruptibility="high",
        last_heartbeat_at=NOW,
        current_assignment_ref="assign-42",
    )


async def test_update_heartbeat_without_status_sends_only_last_heartbeat_at():
    """Bug class (D17): if update_heartbeat's no-status branch slipped a status default
    into the UPDATE, every heartbeat would overwrite the coordinator's runtime_status.
    The query string must contain `last_heartbeat_at` but not `runtime_status`."""
    conn = AsyncMock()
    # First call (inside ensure_state) returns a row; second call (UPDATE) returns row.
    conn.fetchrow.side_effect = [_state_row(), _state_row()]
    adapter = PostgresRuntimeState(_make_pool(conn))

    await adapter.update_heartbeat("max")

    update_call = conn.fetchrow.call_args_list[1]
    query = update_call.args[0]
    # Split on RETURNING so the column list it specifies (read-side) isn't
    # confused with the SET clause (write-side).
    set_clause = query.split("RETURNING", 1)[0]
    assert "last_heartbeat_at = $2" in set_clause
    assert "runtime_status" not in set_clause, (
        "Heartbeat without explicit status must not write runtime_status (D17)"
    )
    # Two positional args after the query: agent_id, now
    assert len(update_call.args) == 3


async def test_update_heartbeat_with_status_does_not_touch_coordinator_fields():
    """Bug class (D17 — the load-bearing one): if anyone adds mode/focus/
    current_assignment_ref/current_runtime_activity_id to the UPDATE, heartbeat
    can race the coordinator and corrupt state. This is the regression test."""
    conn = AsyncMock()
    conn.fetchrow.side_effect = [_state_row(), _state_row(runtime_status="degraded")]
    adapter = PostgresRuntimeState(_make_pool(conn))

    await adapter.update_heartbeat("max", runtime_status="degraded")

    update_call = conn.fetchrow.call_args_list[1]
    query = update_call.args[0]
    set_clause = query.split("RETURNING", 1)[0]
    # Each forbidden column listed as `column =` (the SET-clause assignment
    # form) — bare names appear in the RETURNING list and are legitimate.
    forbidden = (
        "mode =",
        "focus =",
        "current_assignment_ref =",
        "current_runtime_activity_id =",
    )
    for tok in forbidden:
        assert tok not in set_clause, f"Heartbeat UPDATE must not write {tok!r} (D17)"


async def test_update_heartbeat_calls_ensure_state_first():
    """Bug class: removing the ensure_state call would mean an agent that never
    had a row simply never gets one — heartbeats would no-op silently and
    `squadops agent state` would 404 forever."""
    conn = AsyncMock()
    conn.fetchrow.side_effect = [_state_row(), _state_row()]
    adapter = PostgresRuntimeState(_make_pool(conn))

    await adapter.update_heartbeat("max")

    # Two fetchrow calls: first is the ensure_state INSERT...ON CONFLICT,
    # second is the heartbeat UPDATE. The INSERT must come first.
    first_query = conn.fetchrow.call_args_list[0].args[0]
    assert "INSERT INTO agent_runtime_state" in first_query


async def test_ensure_state_returns_existing_row_unchanged():
    """Bug class: if ensure_state used INSERT...ON CONFLICT DO NOTHING + a separate
    SELECT, a race could return None for an existing row. INSERT...ON CONFLICT DO
    UPDATE agent_id RETURNING * fetches the row in one statement either way."""
    conn = AsyncMock()
    conn.fetchrow.return_value = _state_row(
        mode="duty",
        focus="nightly_research",
    )
    adapter = PostgresRuntimeState(_make_pool(conn))

    state = await adapter.ensure_state("max")

    # The mock row reflects the *existing* state; ensure_state must surface
    # that rather than the ambient/online defaults baked into the INSERT.
    assert state.mode == "duty"
    assert state.focus == "nightly_research"


async def test_upsert_state_writes_all_fields_including_coordinator_owned():
    """Bug class: upsert is the coordinator's path for transitions. If the UPDATE
    branch silently omits a field (typo, copy-paste), a transition would persist
    partially. The test asserts the SQL parameter count and the EXCLUDED clauses."""
    conn = AsyncMock()
    adapter = PostgresRuntimeState(_make_pool(conn))
    state = AgentRuntimeState(
        agent_id="max",
        mode="duty",
        runtime_status="online",
        focus="customer_support",
        current_runtime_activity_id="act-1",
        interruptibility="low",
        last_heartbeat_at=NOW,
        current_assignment_ref="assign-1",
    )

    await adapter.upsert_state(state)

    args = conn.execute.call_args.args
    # 1 query + 8 columns of AgentRuntimeState
    assert len(args) == 9
    query = args[0]
    for col in (
        "mode = EXCLUDED.mode",
        "focus = EXCLUDED.focus",
        "current_runtime_activity_id = EXCLUDED.current_runtime_activity_id",
        "current_assignment_ref = EXCLUDED.current_assignment_ref",
        "interruptibility = EXCLUDED.interruptibility",
    ):
        assert col in query, f"upsert UPDATE branch missing: {col}"
