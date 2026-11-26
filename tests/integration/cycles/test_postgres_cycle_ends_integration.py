"""SIP-0109 §12a against real Postgres (#1803): migration 1670's cycle endings, written by the
registry and read back.

The unit tests run the memory twin. Only this proves the adapter's columns and the migration's
agree: an ending round-trips with its stop reason, the latest is the cycle's, none recorded reads
as none, and the endings refuse a rewrite.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlparse

import pytest
import pytest_asyncio

from adapters.cycles.postgres_cycle_registry import PostgresCycleRegistry
from adapters.persistence.pool import create_pool
from adapters.persistence.transient import TransientRetry
from squadops.cycles.cycle_end import CycleStopReason, RecordedEnd
from squadops.cycles.models import Cycle, CycleNotFoundError, TaskFlowPolicy
from tests.integration.conftest import integration_postgres_dsn

#: #1976: one try, so a test sees the registry's own behaviour, never a retry.
ONE_TRY = TransientRetry(attempts=1, backoff_seconds=0.0)

pytestmark = [pytest.mark.docker, pytest.mark.domain_orchestration]

POSTGRES_URL = integration_postgres_dsn()  # #1099: never the deployment DB

asyncpg = pytest.importorskip("asyncpg")

PROJECT = "cycle_ends_it"


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


@pytest_asyncio.fixture
async def registry():
    from squadops.api.runtime.migrations import apply_migrations

    pool = await create_pool(POSTGRES_URL, min_size=1, max_size=4)
    await apply_migrations(pool, Path(__file__).parents[3] / "infra" / "migrations")
    async with pool.acquire() as conn:
        await conn.execute("TRUNCATE TABLE cycle_ends")
        await conn.execute("DELETE FROM cycle_registry WHERE project_id = $1", PROJECT)
    reg = PostgresCycleRegistry(pool=pool, retry=ONE_TRY)
    await reg.create_cycle(
        Cycle(
            cycle_id="cyc_ce1",
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


@pytest.mark.parametrize("reason", list(CycleStopReason))
async def test_every_stop_reason_round_trips(registry, reason):
    """Bug caught: a reason the migration's CHECK refuses — that ending never recorded, and its
    campaign never re-heard."""
    reg, _ = registry
    end = RecordedEnd("cyc_ce1", "run_1", reason)

    assert await reg.record_cycle_end(end) == 1
    assert await reg.get_cycle_end("cyc_ce1") == end


async def test_an_endings_detail_round_trips_and_reads_none_where_the_stop_names_nothing(registry):
    """#3128 (migration 2203): the artifact a gate couldn't read is on the cycle's ending, by
    the single read and the batch read alike. Bug caught: the column written and never selected,
    so the ending a Campaign re-hears from names no artifact."""
    reg, _ = registry
    unread = "the run's plan (artifact art_9) couldn't be read from the vault (artifact_missing)"
    named = RecordedEnd("cyc_ce1", "run_1", CycleStopReason.GATE_INPUT_UNAVAILABLE, unread)

    await reg.record_cycle_end(RecordedEnd("cyc_ce1", "run_1", CycleStopReason.RUN_PAUSED))
    assert (await reg.get_cycle_end("cyc_ce1")).detail is None
    await reg.record_cycle_end(named)

    assert await reg.get_cycle_end("cyc_ce1") == named
    assert await reg.get_cycle_ends(["cyc_ce1"]) == {"cyc_ce1": named}


async def test_the_latest_is_the_cycles_and_an_unknown_cycle_is_refused(registry):
    reg, _ = registry
    assert await reg.get_cycle_end("cyc_ce1") is None

    await reg.record_cycle_end(RecordedEnd("cyc_ce1", "run_1", CycleStopReason.RUN_PAUSED))
    later = RecordedEnd("cyc_ce1", "run_1", CycleStopReason.SEQUENCE_COMPLETED)
    assert await reg.record_cycle_end(later) == 2
    assert await reg.get_cycle_end("cyc_ce1") == later
    with pytest.raises(CycleNotFoundError):
        await reg.record_cycle_end(RecordedEnd("cyc_none", "run_1", CycleStopReason.RUN_FAILED))


async def test_the_endings_refuse_a_rewrite(registry):
    reg, pool = registry
    await reg.record_cycle_end(RecordedEnd("cyc_ce1", "run_1", CycleStopReason.RUN_FAILED))
    async with pool.acquire() as conn:
        with pytest.raises(asyncpg.RaiseError, match="append-only"):
            await conn.execute("UPDATE cycle_ends SET last_run_id = 'run_x'")
        with pytest.raises(asyncpg.RaiseError, match="append-only"):
            await conn.execute("DELETE FROM cycle_ends")


async def test_the_batch_read_names_each_cycle_s_latest_ending_and_omits_the_unended(registry):
    """#3201: the cycle list reads every cycle's ending in one query. Bug caught: the batch
    returning a cycle's first ending rather than its latest (a resumed cycle that ended again),
    or naming a cycle that recorded none."""
    reg, _ = registry
    await reg.record_cycle_end(RecordedEnd("cyc_ce1", "run_1", CycleStopReason.RUN_PAUSED))
    await reg.record_cycle_end(RecordedEnd("cyc_ce1", "run_1", CycleStopReason.RUN_FAILED))

    ends = await reg.get_cycle_ends(["cyc_ce1", "cyc_never_ended"])

    assert ends == {"cyc_ce1": RecordedEnd("cyc_ce1", "run_1", CycleStopReason.RUN_FAILED)}
    assert await reg.get_cycle_ends([]) == {}


async def test_the_status_filter_reads_the_recorded_ending_as_the_cycles_row_does(registry):
    """#3224 against real Postgres: a cycle whose only run completed and whose gate then
    rejected its plan. Bug caught: the filter's query reading the latest run alone, so the cycle
    is listed as ``completed`` and never as ``failed``, which is what its row reads. Only this
    proves the adapter's batch reads (runs, gate decisions, holds, halts, endings) agree with
    the columns the migrations made."""
    from squadops.cycles.lifecycle import CycleStatus, cycle_reading
    from squadops.cycles.models import Run, RunStatus

    reg, _ = registry
    run = await reg.create_run(
        Run(
            run_id="run_ce_gate",
            cycle_id="cyc_ce1",
            run_number=1,
            status="queued",
            initiated_by="it",
            resolved_config_hash="h",
        )
    )
    await reg.update_run_status(run.run_id, RunStatus.RUNNING)
    await reg.update_run_status(run.run_id, RunStatus.COMPLETED)

    before = [c.cycle_id for c in await reg.list_cycles(PROJECT, status=CycleStatus.COMPLETED)]
    await reg.record_cycle_end(RecordedEnd("cyc_ce1", run.run_id, CycleStopReason.PLAN_REJECTED))
    failed = [c.cycle_id for c in await reg.list_cycles(PROJECT, status=CycleStatus.FAILED)]
    completed = [c.cycle_id for c in await reg.list_cycles(PROJECT, status=CycleStatus.COMPLETED)]
    row = cycle_reading(
        await reg.get_cycle("cyc_ce1"),
        await reg.list_runs("cyc_ce1"),
        await reg.get_cycle_end("cyc_ce1"),
    )

    assert before == ["cyc_ce1"]  # the control: without an ending, its run decides
    assert (failed, completed) == (["cyc_ce1"], [])
    assert row.status is CycleStatus.FAILED
