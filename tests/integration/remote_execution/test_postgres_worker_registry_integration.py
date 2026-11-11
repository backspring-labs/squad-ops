"""The worker registry against real Postgres (SIP-0117 R3.3, R5.4): migration 2300's tables.

The unit tests run the contract over the memory store. Only this proves the same contract over
the adapter's columns, the JSONB round trip of a request and a result, the advisory lock that
keeps two claims apart, a failed transaction's rollback, and the table's own constraints.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import pytest_asyncio

from adapters.persistence.pool import create_pool
from adapters.remote_execution.factory import create_worker_registry_store
from squadops.remote_execution.registry import WorkerRegistry
from tests.integration.conftest import integration_postgres_dsn
from tests.unit.remote_execution.registry_contract import (
    ORIGIN,
    Clock,
    WorkerRegistryContract,
    passing,
    registration,
    request,
)

pytestmark = [pytest.mark.docker, pytest.mark.domain_orchestration]

POSTGRES_URL = integration_postgres_dsn()  # #1099: never the deployment DB

asyncpg = pytest.importorskip("asyncpg")


def _pg_available() -> bool:
    import socket

    try:
        with socket.create_connection(("localhost", 5432), timeout=2):
            return True
    except OSError:
        return False


if not _pg_available():
    pytest.skip("Postgres not reachable on localhost:5432", allow_module_level=True)


@pytest_asyncio.fixture
async def pool():
    from squadops.api.runtime.migrations import apply_migrations

    pool = await create_pool(POSTGRES_URL, min_size=1, max_size=6)
    await apply_migrations(pool, Path(__file__).parents[3] / "infra" / "migrations")
    async with pool.acquire() as conn:
        await conn.execute(
            "TRUNCATE TABLE remote_operation_refusals, remote_operation_attempts, "
            "remote_operations, remote_worker_sessions"
        )
    yield pool
    await pool.close()


class TestWorkerRegistryInPostgres(WorkerRegistryContract):
    @pytest.fixture
    def store(self, pool):
        return create_worker_registry_store("postgres", pool=pool)


async def test_a_lease_outlives_the_runtime_that_granted_it(pool):
    """R3.3: "a durable token of its own, because a lease outlives a runtime restart". Bug
    caught: the fence kept in the registry object, so after a restart the worker's result for
    the work it finished is refused, or any result at all is accepted."""
    clock = Clock()
    before = WorkerRegistry(create_worker_registry_store("postgres", pool=pool), clock=clock)
    queued = await before.enqueue(request(), ORIGIN, max_attempts=1)
    session = await before.register(registration())
    claim = await before.claim(session.session_id)

    restarted = WorkerRegistry(create_worker_registry_store("postgres", pool=pool), clock=clock)
    reading = await restarted.heartbeat(session.session_id, "online", claim.fence)
    accepted = await restarted.submit_result(claim.fence, passing())

    assert (reading.refusal, accepted.refusal) == (None, None)
    assert (await restarted.operation(queued.operation_id)).result == passing()


async def test_the_table_itself_refuses_a_second_open_claim_for_a_worker(pool):
    """The index under the rule. Bug caught: a path that writes an attempt without going
    through the registry, leaving a worker holding two operations."""
    registry = WorkerRegistry(create_worker_registry_store("postgres", pool=pool))
    first = await registry.enqueue(request(), ORIGIN, max_attempts=1)
    second = await registry.enqueue(request(), ORIGIN, max_attempts=1)
    session = await registry.register(registration())
    await registry.claim(session.session_id)
    assert (await registry.operation(first.operation_id)).attempt == 1

    with pytest.raises(asyncpg.UniqueViolationError):
        async with pool.acquire() as conn:
            await conn.execute(
                "INSERT INTO remote_operation_attempts "
                "(operation_id, attempt, session_id, worker_id, lease_id, claimed_at) "
                "VALUES ($1, 1, $2, 'macbook', 'lease-by-hand', now())",
                second.operation_id,
                session.session_id,
            )
