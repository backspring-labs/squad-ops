"""#1720 against real Postgres: migration 1050's table takes a deploy record and gives it back.

The unit tests run the memory twin; only this proves the adapter's column list, the JSONB round
trip of the services and models, the newest-first read and the write-once key agree with the
table the migration creates.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
import pytest_asyncio

from adapters.cycles.postgres_deploy_registry import PostgresDeployRegistry
from adapters.persistence.pool import create_pool
from squadops.cycles.deploy_record import DeployRecord, ModelWeights, ServiceImage
from tests.integration.conftest import integration_postgres_dsn

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

_NOW = datetime(2026, 9, 29, 23, 0, tzinfo=UTC)


@pytest_asyncio.fixture
async def registry():
    from squadops.api.runtime.migrations import apply_migrations

    pool = await create_pool(POSTGRES_URL, min_size=1, max_size=4)
    await apply_migrations(pool, Path(__file__).parents[3] / "infra" / "migrations")
    async with pool.acquire() as conn:
        await conn.execute("TRUNCATE TABLE deploy_records")
    yield PostgresDeployRegistry(pool=pool)
    await pool.close()


def _record(deploy_id: str, hours: int) -> DeployRecord:
    return DeployRecord(
        deploy_id=deploy_id,
        recorded_at=_NOW + timedelta(hours=hours),
        recorded_by="rebuild_and_deploy.sh all",
        source_revision=None,
        services=(
            ServiceImage("neo", "sha256:neo", "7acc2bc1-dirty"),
            ServiceImage("postgres", "sha256:pg", None),
        ),
        models=(ModelWeights("qwen3.8:27b", "22130167c4c2"), ModelWeights("llama3.1:8b", None)),
    )


async def test_the_newest_record_reads_back_whole(registry):
    await registry.record(_record("dep_earlier00000", 0))
    await registry.record(_record("dep_latest000000", 2))

    assert await registry.latest() == _record("dep_latest000000", 2)
    assert await registry.get("dep_earlier00000") == _record("dep_earlier00000", 0)
    assert await registry.get("dep_absent0000000") is None


async def test_a_deploy_id_is_written_once(registry):
    await registry.record(_record("dep_once00000000", 0))

    with pytest.raises(asyncpg.UniqueViolationError):
        await registry.record(_record("dep_once00000000", 1))

    assert (await registry.latest()).recorded_at == _NOW
