"""The operator's assessments against real Postgres (SIP-0115 §5.7, migration 2103; #2888).

The routes' tests hold what reaches the store. Only a database proves what the store claims:
assessments read back whole in sequence, the sequence is per goal set, racing writers each take
one, a retry replays, another body under its key is refused, a closed write gate writes nothing,
and the table itself refuses what the domain refuses.
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
from squadops.cycles.models import ProjectRegistryReadOnlyError, RegistrationKeyConflictError
from squadops.projects.goal_set import GoalSetRevision, parse_goal_set
from squadops.projects.goal_set_assessments import (
    Assessment,
    AssessmentEvidence,
    Cause,
    CitedEvaluation,
    Reading,
)
from tests.fixtures.goal_set import goal_set_document
from tests.integration.conftest import integration_postgres_dsn

pytestmark = [pytest.mark.docker, pytest.mark.domain_orchestration]

POSTGRES_URL = integration_postgres_dsn()  # #1099: never the deployment DB
PROJECT = "assessment_it_lantern"
OTHER = "assessment_it_ember"
CAMPAIGNS = {PROJECT: "cmp_assess_it_1", OTHER: "cmp_assess_it_2"}

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
        for project in CAMPAIGNS:
            await conn.execute(
                "DELETE FROM project_goal_set_assessments WHERE project_id = $1", project
            )
            await conn.execute(
                "DELETE FROM project_goal_set_revisions WHERE project_id = $1", project
            )
            await conn.execute("DELETE FROM campaigns WHERE project_id = $1", project)
            await conn.execute("DELETE FROM project_records WHERE project_id = $1", project)


@pytest_asyncio.fixture
async def pool():
    from squadops.api.runtime.migrations import apply_migrations

    pool = await create_pool(POSTGRES_URL, min_size=1, max_size=6)
    await apply_migrations(pool, Path(__file__).parents[3] / "infra" / "migrations")
    await _clear(pool)
    now = datetime.now(UTC)
    store = PostgresGoalSetRegistry(pool)
    async with pool.acquire() as conn:
        for project, campaign in CAMPAIGNS.items():
            await conn.execute(
                "INSERT INTO project_records (project_id, name, description, tags, "
                "lifecycle_status, record_version, provenance, created_at, updated_at) "
                "VALUES ($1, 'Lantern', '', '{}', 'READY', 1, 'seeded', $2, $2)",
                project,
                now,
            )
            await conn.execute(
                "INSERT INTO campaigns (campaign_id, project_id, objective, policy, state, "
                "created_at, created_by, updated_at) "
                "VALUES ($1, $2, $3, $4, 'draft', $5, 'owner', $5)",
                campaign,
                project,
                {},
                {},
                now,
            )
    for project in CAMPAIGNS:
        await store.record_revision(
            GoalSetRevision(
                project_id=project,
                revision=1,
                goal_set=parse_goal_set(goal_set_document()),
                author="owner",
                reason="the first",
                created_at=now,
            ),
            idempotency_key=f"rev:{project}",
            request_hash="h",
        )
    yield pool
    await _clear(pool)
    await pool.close()


def _assessment(project_id: str = PROJECT, **fields) -> Assessment:
    values = {
        "project_id": project_id,
        "campaign_id": CAMPAIGNS[project_id],
        "expected_result": "ER-week",
        "goals_revision": 1,
        "reading": Reading.NOT_MET,
        "cause": Cause.FRAMEWORK_GAP,
        "issue": 2901,
        "evidence": AssessmentEvidence(
            cycles=("cyc_1",),
            rulings=("ctl_7",),
            evaluations=(CitedEvaluation("eval_3", 2, 1),),
        ),
        "reason": "the framework can't reach the page",
        "author": "operator-client",
        "created_at": datetime(2026, 11, 4, 12, 0, tzinfo=UTC),
        "source_ref": "ext://campaigns/thread-7/statement-3",
        "log_seq": 11,
    }
    return Assessment(**{**values, **fields})


async def test_an_assessment_reads_back_whole_and_in_sequence_per_goal_set(pool):
    """Bugs caught: a field lost in the round trip (the evidence's counts, ``supersedes``, the
    cause's enum); the sequence counted across Projects, so one goal set's numbering skips; a read
    not narrowed to the Campaign or the result, or the page taken before the filter."""
    store = PostgresGoalSetRegistry(pool)
    first, replayed = await store.record_assessment(
        _assessment(), idempotency_key="k-1", request_hash="h-1"
    )
    assert (first.sequence, replayed) == (1, False)
    elsewhere, _ = await store.record_assessment(
        _assessment(OTHER), idempotency_key="k-2", request_hash="h-2"
    )
    assert elsewhere.sequence == 1
    second, _ = await store.record_assessment(
        _assessment(
            expected_result="ER-log",
            reading=Reading.MET,
            cause=None,
            issue=None,
            source_ref=None,
            supersedes=(1,),
        ),
        idempotency_key="k-3",
        request_hash="h-3",
    )
    assert second.sequence == 2

    assert await store.list_assessments(PROJECT) == [first, second]
    assert await store.list_assessments(PROJECT, expected_result="ER-log") == [second]
    assert await store.list_assessments(PROJECT, campaign_id=CAMPAIGNS[OTHER]) == []
    assert await store.list_assessments(PROJECT, limit=1, offset=1) == [second]


async def test_a_retry_replays_and_another_body_under_its_key_is_refused(pool):
    """Bugs caught: a retry appending a second row; a key reused for another request, or on
    another Project, replaying the first."""
    store = PostgresGoalSetRegistry(pool)
    first, _ = await store.record_assessment(_assessment(), idempotency_key="k", request_hash="h")

    again, replayed = await store.record_assessment(
        _assessment(reason="retried"), idempotency_key="k", request_hash="h"
    )

    assert (again, replayed) == (first, True)
    with pytest.raises(RegistrationKeyConflictError):
        await store.record_assessment(_assessment(), idempotency_key="k", request_hash="other")
    with pytest.raises(RegistrationKeyConflictError):
        await store.record_assessment(_assessment(OTHER), idempotency_key="k", request_hash="h")
    assert len(await store.list_assessments(PROJECT)) == 1


async def test_racing_writers_each_take_a_sequence(pool):
    """Bug caught: two writers reading the same maximum, one failing on the primary key, so an
    assessment the operator was told nothing about is lost."""
    store = PostgresGoalSetRegistry(pool)

    written = await asyncio.gather(
        *(
            store.record_assessment(_assessment(), idempotency_key=f"k-{i}", request_hash=f"h-{i}")
            for i in range(8)
        )
    )

    assert sorted(a.sequence for a, _ in written) == list(range(1, 9))


async def test_a_closed_write_gate_writes_nothing_and_still_reads(pool):
    """Bug caught: the rollback gate (SIP-0112 R3) covering revisions and not assessments."""
    closed = PostgresGoalSetRegistry(pool, writable=False)

    with pytest.raises(ProjectRegistryReadOnlyError):
        await closed.record_assessment(_assessment(), idempotency_key="k", request_hash="h")

    assert await closed.list_assessments(PROJECT) == []


@pytest.mark.parametrize(
    "fields",
    [
        {"cause": None, "issue": None},
        {"reading": Reading.MET},
        {"cause": Cause.APP_WORK},
        {"issue": None},
        {"goals_revision": 9},
        {"campaign_id": "cmp_nobody"},
    ],
    ids=[
        "a shortfall with no cause",
        "a cause on a met",
        "an issue on app work",
        "a framework cause with no issue",
        "a revision the goal set doesn't hold",
        "a Campaign that doesn't exist",
    ],
)
async def test_the_table_refuses_what_the_domain_refuses(pool, fields):
    """Bugs caught: migration 2103's constraints not saying what §5.7 says, so a row written around
    the domain reads as a judgement it isn't. Each is a CHECK or a foreign key."""
    store = PostgresGoalSetRegistry(pool)
    bad = dataclasses.replace(_assessment(), **fields)

    with pytest.raises((asyncpg.CheckViolationError, asyncpg.ForeignKeyViolationError)):
        await store.record_assessment(bad, idempotency_key="k", request_hash="h")
