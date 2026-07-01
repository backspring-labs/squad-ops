"""Integration tests for SIP-0089 §4.5/D25 — coordinator RuntimeTransaction rollback.

Requires a running Postgres (docker-compose up -d postgres). Proves the real
atomicity an in-memory fake can't model: a failure at the mode write (step 6)
rolls back BOTH the FocusLease acquired in step 4 and the RuntimeActivity abort in
step 5 — no stranded lease, no orphaned activity state. Plus a positive control
that the committed path writes the lease and mode together.
"""

from __future__ import annotations

import os
import socket
import uuid
from pathlib import Path

import pytest
import pytest_asyncio

from squadops.runtime import reasons
from squadops.runtime.coordinator import RuntimeCoordinator

pytestmark = [pytest.mark.docker, pytest.mark.domain_runtime]

POSTGRES_URL = os.getenv(
    "POSTGRES_URL", "postgresql://squadops:squadops-dev@localhost:5432/squadops"
)

try:
    import asyncpg  # noqa: F401
except ImportError:
    pytest.skip("asyncpg not installed", allow_module_level=True)


def _pg_available() -> bool:
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(2)
        s.connect(("localhost", 5432))
        s.close()
        return True
    except OSError:
        return False


if not _pg_available():
    pytest.skip(
        "Postgres not reachable on localhost:5432 — start with docker-compose up -d postgres",
        allow_module_level=True,
    )


@pytest_asyncio.fixture
async def pool():
    from squadops.api.runtime.migrations import apply_migrations

    p = await asyncpg.create_pool(POSTGRES_URL, min_size=1, max_size=5)
    await apply_migrations(p, Path(__file__).parents[3] / "infra" / "migrations")
    yield p
    await p.close()


async def _cleanup(p, agent_id: str) -> None:
    async with p.acquire() as conn:
        await conn.execute("DELETE FROM focus_leases WHERE agent_id = $1", agent_id)
        await conn.execute("DELETE FROM runtime_activities WHERE agent_id = $1", agent_id)
        await conn.execute("DELETE FROM agent_runtime_state WHERE agent_id = $1", agent_id)


def _ports(p):
    from adapters.persistence.runtime import (
        PostgresFocusLease,
        PostgresRuntimeActivity,
        PostgresRuntimeState,
        PostgresRuntimeTransaction,
    )

    return (
        PostgresRuntimeState(p),
        PostgresFocusLease(p),
        PostgresRuntimeActivity(p),
        PostgresRuntimeTransaction(p),
    )


async def test_mode_write_failure_rolls_back_lease_and_activity(pool):
    from adapters.persistence.runtime import PostgresRuntimeState

    agent = f"itest-{uuid.uuid4().hex[:8]}"
    state, fl, act, txn = _ports(pool)
    await _cleanup(pool, agent)
    try:
        # Seed: agent ambient, holding an orphaned `duty` activity (running).
        await state.ensure_state(agent)
        orphan = await act.start_activity(
            agent,
            mode="duty",
            activity_type="x",
            goal="g",
            source_kind="cycle_task",
            source_ref="r",
        )

        # A coordinator whose mode write always fails — after the lease is acquired
        # and the activity aborted on the same transaction connection.
        class _FailingState(PostgresRuntimeState):
            async def upsert_state(self, s, *, conn=None):
                raise RuntimeError("simulated mode-write failure")

        coord = RuntimeCoordinator(
            _FailingState(pool), focus_lease=fl, activity=act, transaction=txn
        )

        with pytest.raises(RuntimeError, match="mode-write failure"):
            await coord.request_transition(
                agent,
                "cycle",
                reasons.CYCLE_RECRUITED,
                requester_kind="external",
                owner_ref="run-1",
            )

        # D25: the FocusLease acquired in step 4 rolled back — no active lease.
        assert await fl.get_current_lease(agent) is None
        # The activity abort in step 5 rolled back — the orphan is still running.
        current = await act.get_current_activity(agent)
        assert current is not None
        assert current.runtime_activity_id == orphan.runtime_activity_id
        assert current.state == "running"
        # And the mode was never written.
        st = await state.get_state(agent)
        assert st is not None and st.mode == "ambient"
    finally:
        await _cleanup(pool, agent)


async def test_committed_transition_writes_lease_and_mode_together(pool):
    agent = f"itest-{uuid.uuid4().hex[:8]}"
    state, fl, act, txn = _ports(pool)
    await _cleanup(pool, agent)
    try:
        await state.ensure_state(agent)  # ambient
        coord = RuntimeCoordinator(state, focus_lease=fl, activity=act, transaction=txn)

        outcome = await coord.request_transition(
            agent,
            "cycle",
            reasons.CYCLE_RECRUITED,
            requester_kind="external",
            owner_ref="run-1",
        )

        assert outcome.applied is True
        lease = await fl.get_current_lease(agent)
        assert lease is not None and lease.owner_type == "cycle"
        st = await state.get_state(agent)
        assert st is not None and st.mode == "cycle"
    finally:
        await _cleanup(pool, agent)
