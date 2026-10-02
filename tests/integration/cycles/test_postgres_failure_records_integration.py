"""SIP-0109 §14 against real Postgres (#1710): migration 1620's record sets, written by the
registry and read back.

The unit tests run the memory twin. Only this proves the adapter's columns and the migration's
agree: a set and its records commit together, an empty set reads as recorded-empty and no set as
never-recorded, the latest set is the cycle's, an event survives its JSONB round trip, and the
records refuse a rewrite.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlparse

import pytest
import pytest_asyncio

from adapters.cycles.postgres_cycle_registry import PostgresCycleRegistry
from adapters.persistence.pool import create_pool
from squadops.cycles.failure_attribution import FailureEvent
from squadops.cycles.failure_records import failure_records
from squadops.cycles.models import Cycle, TaskFlowPolicy
from tests.integration.conftest import integration_postgres_dsn

pytestmark = [pytest.mark.docker, pytest.mark.domain_orchestration]

POSTGRES_URL = integration_postgres_dsn()  # #1099: never the deployment DB

asyncpg = pytest.importorskip("asyncpg")

PROJECT = "failure_records_it"


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

_EVENTS = (
    FailureEvent(
        run_id="run_1",
        task_id="t-qa",
        round_index=0,
        category="executed_and_failed",
        locus="subject",
    ),
    FailureEvent(
        run_id="run_1",
        task_id="t-qa",
        round_index=1,
        category="emission_absent",
        locus="own_artifact",
        emission_signature="cap_exhausted",
    ),
)


@pytest_asyncio.fixture
async def registry():
    from squadops.api.runtime.migrations import apply_migrations

    pool = await create_pool(POSTGRES_URL, min_size=1, max_size=4)
    await apply_migrations(pool, Path(__file__).parents[3] / "infra" / "migrations")
    async with pool.acquire() as conn:
        await conn.execute("TRUNCATE TABLE cycle_failure_records, cycle_failure_record_sets")
        await conn.execute("DELETE FROM cycle_registry WHERE project_id = $1", PROJECT)
    reg = PostgresCycleRegistry(pool=pool)
    await reg.create_cycle(
        Cycle(
            cycle_id="cyc_fr1",
            project_id=PROJECT,
            created_at=datetime(2026, 10, 2, tzinfo=UTC),
            created_by="it",
            prd_ref=None,
            squad_profile_id="full",
            squad_profile_snapshot_ref="sha256:abc",
            task_flow_policy=TaskFlowPolicy(mode="sequential"),
            build_strategy="fresh",
        )
    )
    yield reg, pool
    await pool.close()


async def test_a_set_round_trips_with_its_events_classes_and_unaskable_records(registry):
    reg, _ = registry
    records = failure_records("cyc_fr1", _EVENTS, ("input_x: not stored",), campaign_id="cmp_1")

    assert await reg.record_failure_records("cyc_fr1", "run_1", records) == 1

    assert await reg.get_failure_records("cyc_fr1") == records


async def test_never_recorded_empty_and_latest_are_three_answers(registry):
    reg, _ = registry
    assert await reg.get_failure_records("cyc_fr1") is None

    await reg.record_failure_records("cyc_fr1", "run_1", ())
    assert await reg.get_failure_records("cyc_fr1") == ()

    later = failure_records("cyc_fr1", _EVENTS[:1], ())
    assert await reg.record_failure_records("cyc_fr1", "run_1", later) == 2
    assert await reg.get_failure_records("cyc_fr1") == later


async def test_the_records_refuse_a_rewrite(registry):
    reg, pool = registry
    await reg.record_failure_records("cyc_fr1", "run_1", failure_records("cyc_fr1", _EVENTS, ()))
    async with pool.acquire() as conn:
        for table in ("cycle_failure_records", "cycle_failure_record_sets"):
            with pytest.raises(asyncpg.RaiseError, match="append-only"):
                await conn.execute(f"UPDATE {table} SET registry_version = 99")
            with pytest.raises(asyncpg.RaiseError, match="append-only"):
                await conn.execute(f"DELETE FROM {table}")


async def test_a_record_violating_the_schema_leaves_no_partial_set(registry):
    """The set row and its records commit together. Bug caught: a set row left behind with
    fewer records than its count, which reads as a complete set with failures missing."""
    reg, pool = registry
    bad = failure_records("cyc_fr1", _EVENTS, ())
    # The second record also names an input, which the table's CHECK refuses: the first record
    # inserts, then this one fails.
    object.__setattr__(bad[1], "unasked_input", "input_x")

    with pytest.raises(asyncpg.CheckViolationError):
        await reg.record_failure_records("cyc_fr1", "run_1", bad)

    assert await reg.get_failure_records("cyc_fr1") is None
    async with pool.acquire() as conn:
        assert await conn.fetchval("SELECT count(*) FROM cycle_failure_records") == 0
