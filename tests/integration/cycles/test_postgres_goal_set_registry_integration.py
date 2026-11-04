"""A Project's goal-set revisions against real Postgres (SIP-0115 §4, migration 2100; #2884).

The routes' tests hold what reaches the store. Only a database proves what the store claims:
revisions follow one another and read back whole, newest first; a stale write is refused; a
retry replays and another body under its key is refused; two writers on one Project can't both
take a revision; a closed write gate writes nothing.
"""

from __future__ import annotations

import asyncio
import dataclasses
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlparse

import pytest
import pytest_asyncio

from adapters.cycles.postgres_goal_set_registry import PostgresGoalSetRegistry
from adapters.persistence.pool import create_pool
from squadops.cycles.models import (
    GoalSetNotFoundError,
    ProjectNotFoundError,
    ProjectRegistryReadOnlyError,
    RegistrationKeyConflictError,
    StaleGoalSetRevisionError,
)
from squadops.projects.goal_set import Change, ChangeKind, GoalSetRevision, parse_goal_set
from tests.fixtures.goal_set import goal_set_document
from tests.integration.conftest import integration_postgres_dsn

pytestmark = [pytest.mark.docker, pytest.mark.domain_orchestration]

POSTGRES_URL = integration_postgres_dsn()  # #1099: never the deployment DB
PROJECT = "goalset_it_lantern"

asyncpg = pytest.importorskip("asyncpg")


def _pg_available() -> bool:
    import socket

    url = urlparse(POSTGRES_URL)
    try:
        with socket.create_connection((url.hostname or "localhost", url.port or 5432), timeout=2):
            return True
    except OSError:
        return False


if not _pg_available():
    pytest.skip("Postgres not reachable at the integration DSN", allow_module_level=True)


async def _clear(pool) -> None:
    async with pool.acquire() as conn:
        await conn.execute("DELETE FROM project_goal_set_revisions WHERE project_id = $1", PROJECT)
        await conn.execute("DELETE FROM project_records WHERE project_id = $1", PROJECT)


@pytest_asyncio.fixture
async def pool():
    from squadops.api.runtime.migrations import apply_migrations

    pool = await create_pool(POSTGRES_URL, min_size=1, max_size=4)
    await apply_migrations(pool, Path(__file__).parents[3] / "infra" / "migrations")
    await _clear(pool)
    now = datetime.now(UTC)
    async with pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO project_records (project_id, name, description, tags, lifecycle_status, "
            "record_version, provenance, created_at, updated_at) "
            "VALUES ($1, 'Lantern', '', '{}', 'READY', 1, 'seeded', $2, $2)",
            PROJECT,
            now,
        )
    yield pool
    await _clear(pool)
    await pool.close()


def _revision(n: int, *, reason: str = "the owner's edit", project_id: str = PROJECT):
    doc = goal_set_document()
    doc["backlog"] = doc["backlog"][:n]  # each revision's content differs
    return GoalSetRevision(
        project_id=project_id,
        revision=n,
        goal_set=parse_goal_set(doc),
        author="owner",
        reason=reason,
        created_at=datetime(2026, 11, 3, 12, n, tzinfo=UTC),
        source_ref=f"https://chat.example.invalid/thread/{n}" if n == 2 else None,
        # Slice 3 (#2886, migration 2101): revision 2 was an action; 1 a whole-document edit.
        change=(
            Change(ChangeKind.ITEM_SPLIT, "B-0", split_into=("B-1", "B-2"), campaign_id="cmp_1")
            if n == 2
            else None
        ),
    )


async def test_revisions_follow_one_another_and_read_back_whole_newest_first(pool):
    """Bugs caught: a field lost in the JSONB round trip (a candidate's time, a surface's
    reason, an action's ``change`` with the ids a split produced); the active read returning the
    first revision; the history oldest first."""
    store = PostgresGoalSetRegistry(pool)
    with pytest.raises(GoalSetNotFoundError):
        await store.get_revision(PROJECT)
    assert await store.list_revisions(PROJECT) == []

    first, _ = await store.record_revision(_revision(1), idempotency_key="it-1", request_hash="h1")
    second, _ = await store.record_revision(_revision(2), idempotency_key="it-2", request_hash="h2")

    assert await store.get_revision(PROJECT) == second
    assert await store.get_revision(PROJECT, 1) == first == _revision(1)
    assert await store.list_revisions(PROJECT) == [second, first]
    with pytest.raises(GoalSetNotFoundError):
        await store.get_revision(PROJECT, 9)


async def test_a_stale_write_is_refused_and_a_retry_replays_what_was_written(pool):
    """Bugs caught: a second writer that read revision 1 overwriting or forking revision 2; a
    retry after a dropped answer writing again; a key reused for another body replayed."""
    store = PostgresGoalSetRegistry(pool)
    await store.record_revision(_revision(1), idempotency_key="it-1", request_hash="h1")
    await store.record_revision(_revision(2), idempotency_key="it-2", request_hash="h2")

    with pytest.raises(StaleGoalSetRevisionError):
        await store.record_revision(
            _revision(2, reason="a late edit"), idempotency_key="it-3", request_hash="h3"
        )
    with pytest.raises(StaleGoalSetRevisionError):
        await store.record_revision(_revision(4), idempotency_key="it-4", request_hash="h4")
    replayed, was_replay = await store.record_revision(
        dataclasses.replace(_revision(2), created_at=datetime.now(UTC)),
        idempotency_key="it-2",
        request_hash="h2",
    )
    with pytest.raises(RegistrationKeyConflictError):
        await store.record_revision(_revision(3), idempotency_key="it-2", request_hash="other")

    assert (replayed, was_replay) == (_revision(2), True)
    assert [r.revision for r in await store.list_revisions(PROJECT)] == [2, 1]


async def test_writers_racing_for_one_revision_write_it_once(pool):
    """Bug caught: edits that read the same latest revision each write the next one; every
    loser must be refused as stale, not answered 500 by the primary key. A warm pool of its own,
    one connection per writer: on a cold one, opening each connection serializes the writers and
    the race never happens (checked: without the Project's lock this fails, UniqueViolation)."""
    racing = await create_pool(POSTGRES_URL, min_size=8, max_size=8)
    store = PostgresGoalSetRegistry(racing)
    try:
        results = await asyncio.gather(
            *[
                store.record_revision(
                    _revision(1, reason=f"writer {i}"),
                    idempotency_key=f"it-{i}",
                    request_hash=str(i),
                )
                for i in range(8)
            ],
            return_exceptions=True,
        )
    finally:
        await racing.close()

    assert sorted(type(r).__name__ for r in results) == ["StaleGoalSetRevisionError"] * 7 + [
        "tuple"
    ]
    assert len(await PostgresGoalSetRegistry(pool).list_revisions(PROJECT)) == 1


async def test_an_unknown_project_and_a_closed_gate_write_nothing(pool):
    """Bugs caught: a goal set written for a Project with no record (an FK error answered 500);
    the read-only gate (R3's rollback, and the config provider) letting a write through."""
    with pytest.raises(ProjectNotFoundError):
        await PostgresGoalSetRegistry(pool).record_revision(
            _revision(1, project_id="goalset_it_missing"), idempotency_key="it-x", request_hash="x"
        )
    with pytest.raises(ProjectRegistryReadOnlyError):
        await PostgresGoalSetRegistry(pool, writable=False).record_revision(
            _revision(1), idempotency_key="it-1", request_hash="h1"
        )

    assert await PostgresGoalSetRegistry(pool, writable=False).list_revisions(PROJECT) == []
