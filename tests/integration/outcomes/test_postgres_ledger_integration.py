"""#2417 against real Postgres: migration 1920's tables hold the ledger's classifications and
declared entries. The unit tests run the memory twin; only this proves the columns, the revision
of a classification by its row, and the tables' own checks on reason and severity."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
import pytest_asyncio

from adapters.outcomes.postgres_ledger import PostgresInterventionLedger
from adapters.persistence.pool import create_pool
from squadops.outcomes.ledger import Classification, DeclaredIntervention
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

T0 = datetime(2026, 10, 18, 23, 0, tzinfo=UTC)
CID = "cmp_pgledger00001"


@pytest_asyncio.fixture
async def store():
    from squadops.api.runtime.migrations import apply_migrations

    pool = await create_pool(POSTGRES_URL, min_size=1, max_size=4)
    await apply_migrations(pool, Path(__file__).parents[3] / "infra" / "migrations")
    async with pool.acquire() as conn:
        await conn.execute("TRUNCATE TABLE intervention_classifications, declared_interventions")
    yield PostgresInterventionLedger(pool=pool), pool
    await pool.close()


async def test_a_classification_is_revised_by_its_row_and_declared_entries_read_in_order(store):
    ledger, _ = store
    first = Classification("ent_1", CID, "verification", "unblock", "supervisor", T0)
    revised = Classification("ent_1", CID, "environment", "recovery", "owner", T0, False, "box")
    later = DeclaredIntervention(
        "dcl_2",
        CID,
        "environment",
        "recovery",
        "restarted the runtime API",
        T0 + timedelta(hours=1),
        "owner",
        T0,
    )
    earlier = DeclaredIntervention(
        "dcl_1", CID, "tool", "unblock", "cleared a stuck lease", T0, "owner", T0, True
    )  # fmt: skip

    for c in (first, revised):
        await ledger.save_classification(c)
    for d in (later, earlier):
        await ledger.save_declared(d)

    assert await ledger.classifications(CID) == [revised]
    assert await ledger.declared(CID) == [earlier, later]
    assert await ledger.classifications("cmp_other") == []


async def test_the_tables_refuse_a_reason_outside_the_list(store):
    """The migration's own check, beneath the domain's: a row written around the domain."""
    _, pool = store
    with pytest.raises(asyncpg.CheckViolationError):
        async with pool.acquire() as conn:
            await conn.execute(
                "INSERT INTO intervention_classifications (entry_id, campaign_id, reason, "
                "severity, classified_by, classified_at) VALUES ($1,$2,$3,$4,$5,$6)",
                "ent_x",
                CID,
                "laziness",
                "advisory",
                "s",
                T0,
            )
