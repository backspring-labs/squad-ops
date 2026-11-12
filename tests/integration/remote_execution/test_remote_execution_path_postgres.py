"""The remote-execution path end to end, with its faults, on Postgres (#3050, slice 1).

``remote_path.RemotePathContract``'s cases with the registry on the Postgres store, as a
deployed runtime keeps it: the lease, the fence and the one-operation-per-send rule held by its
rows, not by a process's memory.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import pytest_asyncio

from adapters.persistence.pool import create_pool
from adapters.remote_execution.factory import create_worker_registry_store
from tests.integration.conftest import integration_postgres_dsn
from tests.unit.remote_execution.remote_path import RemotePathContract

pytestmark = [pytest.mark.docker, pytest.mark.domain_orchestration, pytest.mark.auth]

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


class TestRemoteExecutionPathInPostgres(RemotePathContract):
    @pytest.fixture
    def store(self, pool):
        return create_worker_registry_store("postgres", pool=pool)
