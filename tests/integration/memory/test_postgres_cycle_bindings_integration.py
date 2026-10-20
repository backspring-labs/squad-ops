"""A campaign cycle's own bindings, stored by the Postgres memory store (SIP-0110 §5ad; #2179 T16):
migration ``1792``'s table, written at a launch, replaced by a re-binding, and read back by a dispatch.

What bugs would these catch? A binding that loses a reference's digest on its way through JSON; a re-binding that adds a second row instead of replacing the cycle's one; a cycle with no
binding read as an empty one.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
import pytest_asyncio

from adapters.memory.cross_cycle import PostgresCrossCycleMemoryStore
from adapters.persistence.pool import create_pool
from squadops.memory.cycle_bindings import CycleBinding, replacing
from squadops.memory.records import InstructionApplicability, PinnedInstruction, Reference
from tests.integration.conftest import integration_postgres_dsn

pytestmark = [pytest.mark.docker, pytest.mark.domain_memory]

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

T0 = datetime(2026, 10, 20, 19, 0, tzinfo=UTC)
WHERE = InstructionApplicability(("development.design_plan",), ("*",), ("*",))


@pytest_asyncio.fixture
async def pool():
    from squadops.api.runtime.migrations import apply_migrations

    pool = await create_pool(POSTGRES_URL, min_size=1, max_size=4)
    await apply_migrations(pool, Path(__file__).parents[3] / "infra" / "migrations")
    async with pool.acquire() as conn:
        await conn.execute("TRUNCATE TABLE memory_cycle_bindings")
    yield pool
    await pool.close()


def _pinned(revision: int, ref: str, digest: str) -> PinnedInstruction:
    return PinnedInstruction(
        "mrec_ref", revision, "Read the spec.", WHERE,
        (Reference(ref, True, digest=digest),),
    )  # fmt: skip


async def test_a_cycles_binding_round_trips_and_a_rebinding_replaces_it(pool):
    store = PostgresCrossCycleMemoryStore(pool=pool)
    first = CycleBinding(
        "cyc_a",
        "campaign",
        "cmp_1",
        (_pinned(1, "repo:file:SPEC.md@" + "a" * 40, "sha256:aa"),),
        T0,
    )

    await store.record_cycle_binding(first)
    read = await store.get_cycle_binding("cyc_a")
    await store.record_cycle_binding(
        replacing(first, "mrec_ref", (_pinned(2, "repo:file:SPEC.md@" + "b" * 40, "sha256:bb"),))
    )
    rebound = await store.get_cycle_binding("cyc_a")

    assert read == first
    assert [(p.revision, p.references[0].digest) for p in rebound.instructions] == [
        (2, "sha256:bb")
    ]
    assert await store.get_cycle_binding("cyc_none") is None
    async with pool.acquire() as conn:
        assert await conn.fetchval("SELECT count(*) FROM memory_cycle_bindings") == 1
