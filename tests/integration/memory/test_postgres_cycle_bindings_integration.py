"""A campaign cycle's own bindings, stored by the Postgres memory store (SIP-0110 §5ad; #2179 T16):
migration ``1792``'s table, one row per cycle, record and revision, written once at a launch, by a
re-binding and by the sweep's fill, and read back by a dispatch.

What bugs would these catch? A binding that loses a reference's digest on its way through JSON; a
stale write (the sweep, or a re-binding that read the snapshot before another) replacing the newer
revision's row, or a second write of a revision rewriting a row a dispatch was handed; one record's
write erasing another's; a cycle with no binding read as an empty one.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
import pytest_asyncio

from adapters.memory.cross_cycle import PostgresCrossCycleMemoryStore
from adapters.persistence.pool import create_pool
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


def _pinned(record_id: str, revision: int, digest: str) -> PinnedInstruction:
    return PinnedInstruction(
        record_id, revision, "Read the spec.", WHERE,
        (Reference(f"repo:file:SPEC.md@{revision:040d}", True, digest=digest),),
    )  # fmt: skip


async def test_each_revision_is_its_own_row_and_a_row_is_written_once(pool):
    store = PostgresCrossCycleMemoryStore(pool=pool)

    for record_id, revision, digest in (
        ("mrec_x", 3, "sha256:x3"),
        ("mrec_x", 2, "sha256:x2"),  # a stale write lands beside the newer revision
        ("mrec_x", 3, "sha256:x3-again"),  # a second write of a held revision changes nothing
        ("mrec_y", 1, "sha256:y1"),
    ):
        await store.record_cycle_bindings(
            "cyc_a", "campaign", "cmp_1", (_pinned(record_id, revision, digest),), T0
        )
    held = await store.get_cycle_binding("cyc_a")

    assert [(p.record_id, p.revision, p.references[0].digest) for p in held.instructions] == [
        ("mrec_x", 2, "sha256:x2"), ("mrec_x", 3, "sha256:x3"), ("mrec_y", 1, "sha256:y1"),
    ]  # fmt: skip
    assert (held.unit_kind, held.unit_id) == ("campaign", "cmp_1")
    assert await store.get_cycle_binding("cyc_none") is None
