"""#2413 against real Postgres: migration 1900's tables hold a suite and a campaign's pin.

The unit tests run the memory twin; only this proves the adapter's columns, the JSONB round trip
of a suite's content, the digest recomputed on read, the pin's foreign key and the approval's
check constraint agree with the tables the migration creates.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

import pytest
import pytest_asyncio

from adapters.persistence.pool import create_pool
from adapters.scenarios.postgres_scenario_store import PostgresScenarioStore
from squadops.scenarios.models import CampaignSuitePin, SuiteState, parse_suite
from squadops.scenarios.suites import approve_suite, draft_suite, pin_campaign_suite
from tests.integration.conftest import integration_postgres_dsn
from tests.unit.scenarios.suite_fixtures import SUITE

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

T0 = datetime(2026, 10, 18, 20, 0, tzinfo=UTC)


@pytest_asyncio.fixture
async def store():
    from squadops.api.runtime.migrations import apply_migrations

    pool = await create_pool(POSTGRES_URL, min_size=1, max_size=4)
    await apply_migrations(pool, Path(__file__).parents[3] / "infra" / "migrations")
    async with pool.acquire() as conn:
        await conn.execute("TRUNCATE TABLE campaign_scenario_suites, scenario_suites")
    yield PostgresScenarioStore(pool=pool), pool
    await pool.close()


async def test_a_suite_is_drafted_approved_and_pinned_and_reads_back_whole(store):
    scenarios, _ = store
    suite = parse_suite(SUITE)

    await draft_suite(scenarios, suite, actor="supervisor", at=T0)
    approved = await approve_suite(scenarios, suite.digest, actor="owner", at=T0)
    pin = await pin_campaign_suite(
        scenarios, "cmp_pg0000000001", suite.digest, actor="owner", at=T0
    )

    assert await scenarios.get_suite(suite.digest) == approved
    assert approved.state is SuiteState.APPROVED and approved.suite == suite
    assert [r.digest for r in await scenarios.list_suites()] == [suite.digest]
    assert await scenarios.get_pin("cmp_pg0000000001") == pin


async def test_a_row_whose_content_no_longer_hashes_to_its_key_is_refused(store):
    """Bug caught: a suite edited in place in the table served under its old digest, so a
    pinned campaign ran checks its digest no longer names."""
    scenarios, pool = store
    suite = parse_suite(SUITE)
    await draft_suite(scenarios, suite, actor="supervisor", at=T0)
    edited = suite.content()
    edited["scenarios"][1]["checks"][0]["equals"] = 422
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE scenario_suites SET content = $1 WHERE digest = $2", edited, suite.digest
        )

    with pytest.raises(ValueError, match="no longer hashes to its key"):
        await scenarios.get_suite(suite.digest)


async def test_the_tables_refuse_a_pin_to_nothing_and_an_approval_without_its_approver(store):
    """The migration's own constraints, beneath the rules: a pin naming no stored suite, and an
    approved row that names no approver."""
    scenarios, _ = store
    suite = parse_suite(SUITE)
    record = await draft_suite(scenarios, suite, actor="supervisor", at=T0)

    with pytest.raises(asyncpg.ForeignKeyViolationError):
        await scenarios.save_pin(CampaignSuitePin("cmp_pg0000000002", "f" * 64, "owner", T0))
    with pytest.raises(asyncpg.CheckViolationError):
        await scenarios.save_suite(replace(record, state=SuiteState.APPROVED))
