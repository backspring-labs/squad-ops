"""#2177 against real Postgres: migration 1780's tables hold a record, its revisions as whole documents
and its status changes, and a chat session gains its project binding. The unit tests run the memory
twin; only this proves the columns, the JSONB round trip through the pool's codecs, and the
revision-number race refused by the table's key."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
import pytest_asyncio

from adapters.memory.records import PostgresMemoryRecords
from adapters.persistence.pool import create_pool
from squadops.memory.records import (
    InstructionApplicability,
    Reference,
    Revision,
    Source,
    StatusChange,
    new_record,
    revised,
)
from squadops.ports.memory.records import RecordConflict
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

T0 = datetime(2026, 10, 19, 15, 0, tzinfo=UTC)


@pytest_asyncio.fixture
async def store():
    from squadops.api.runtime.migrations import apply_migrations

    pool = await create_pool(POSTGRES_URL, min_size=1, max_size=4)
    await apply_migrations(pool, Path(__file__).parents[3] / "infra" / "migrations")
    async with pool.acquire() as conn:
        await conn.execute(
            "TRUNCATE TABLE memory_record_status_changes, memory_record_revisions, memory_records"
        )
    yield PostgresMemoryRecords(pool=pool), pool
    await pool.close()


async def test_a_record_its_revisions_and_its_withdrawal_read_back_as_written(store):
    records, _ = store
    instruction = new_record(
        record_id="mrec_pg_1", kind="instruction", scope="project", project_id="group_run",
        owner_id="ada",
        revision=Revision(
            number=1, body="cover capacity 1", author="ada", created_at=T0,
            source=Source("chat_message", {"session_id": "s1", "message_id": "m2"}),
            confirmed_by="ada",
            applicability=InstructionApplicability(("qa.test",), ("*",), ("*",)),
            references=(Reference("manifest:decision:capacity@2", True),),
        ),
    )  # fmt: skip
    await records.create(instruction)
    second = revised(instruction, instruction.current)
    await records.append_revision("mrec_pg_1", second.current)
    await records.append_status(
        "mrec_pg_1", StatusChange("withdrawn", "ada", T0, "now a task instruction")
    )

    read = await records.get("mrec_pg_1")

    assert read is not None
    assert read.revisions[0] == instruction.revisions[0]
    assert [(r.number, r.supersedes) for r in read.revisions] == [(1, None), (2, 1)]
    assert read.status == "withdrawn"
    assert [r.record_id for r in await records.list_project("group_run")] == ["mrec_pg_1"]


async def test_a_lost_race_and_a_taken_id_are_refused(store):
    records, _ = store
    note = new_record(
        record_id="mrec_pg_2", kind="note", scope="user", project_id=None, owner_id="bo",
        revision=Revision(number=1, body="b", author="bo", created_at=T0, source=Source("api_call")),
    )  # fmt: skip
    await records.create(note)

    with pytest.raises(RecordConflict):
        await records.create(note)
    with pytest.raises(RecordConflict, match="next revision is 2"):
        await records.append_revision(
            "mrec_pg_2", revised(revised(note, note.current), note.current).current
        )
    with pytest.raises(KeyError):
        await records.append_revision("mrec_missing", note.current)
    assert [r.record_id for r in await records.list_owned("bo")] == ["mrec_pg_2"]


async def test_a_chat_session_gains_its_project_binding(store):
    _, pool = store
    async with pool.acquire() as conn:
        column = await conn.fetchval(
            "SELECT data_type FROM information_schema.columns "
            "WHERE table_name = 'chat_sessions' AND column_name = 'project_id'"
        )
    assert column == "text"
