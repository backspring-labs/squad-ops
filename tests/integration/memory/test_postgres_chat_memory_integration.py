"""#2180 against real Postgres: migration 1781 and the chat substrate's three stores. The note search
filters by scope and status before it ranks by full-text match and recency (§A.3.10); a session's
deletion keeps its row, marked, and removes its messages (Q29); a chat turn's exposure round-trips. The
unit tests run the memory twins; only this proves the SQL."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
import pytest_asyncio

from adapters.memory.cross_cycle import PostgresCrossCycleMemoryStore
from adapters.memory.records import PostgresMemoryRecords
from adapters.persistence.chat_repository import ChatRepository
from adapters.persistence.pool import create_pool
from squadops.comms.models import ChatMessage, ChatSession, SessionNotFoundError
from squadops.memory.chat import ChatExposure
from squadops.memory.context import Disposition, Need, RecordRef, Section, SectionKind
from squadops.memory.records import Revision, Source, StatusChange, new_record
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
async def pool():
    from squadops.api.runtime.migrations import apply_migrations

    pool = await create_pool(POSTGRES_URL, min_size=1, max_size=4)
    await apply_migrations(pool, Path(__file__).parents[3] / "infra" / "migrations")
    async with pool.acquire() as conn:
        await conn.execute(
            "TRUNCATE TABLE memory_record_status_changes, memory_record_revisions, memory_records, "
            "chat_exposures, chat_messages, chat_sessions"
        )
    yield pool
    await pool.close()


def _note(record_id, body, *, scope="user", project_id=None, owner="ada", at=T0):
    return new_record(
        record_id=record_id, kind="note", scope=scope, project_id=project_id, owner_id=owner,
        revision=Revision(number=1, body=body, author=owner, created_at=at, source=Source("api_call")),
    )  # fmt: skip


async def test_the_search_filters_by_scope_and_status_then_ranks_by_match_and_recency(pool):
    """Bug caught: another person's or another project's note returned, a withdrawn one kept, or
    the rank cutting before the filter (#571's starvation); or ``plainto_tsquery`` handed syntax."""
    records = PostgresMemoryRecords(pool=pool)
    for note in (
        _note("mrec_old", "the join stays idempotent", at=T0),
        _note("mrec_new", "capacity is checked before the join", at=T0 + timedelta(hours=1)),
        _note("mrec_none", "unrelated", at=T0 + timedelta(hours=2)),
        _note(
            "mrec_proj", "the join returns 409 when full", scope="project", project_id="group_run"
        ),
        _note("mrec_p2", "the join in another project", scope="project", project_id="play_game"),
        _note("mrec_bo", "bo's join note", owner="bo"),
        _note("mrec_gone", "a withdrawn join note"),
    ):
        await records.create(note)
    await records.append_status("mrec_gone", StatusChange("withdrawn", "ada", T0, "wrong"))

    bound = await records.search_notes(owner_id="ada", project_id="group_run", text="the join & !")
    unbound = await records.search_notes(owner_id="ada", project_id=None, text="join")

    assert {r.record_id for r in bound} == {"mrec_old", "mrec_new", "mrec_none", "mrec_proj"}
    assert bound[-1].record_id == "mrec_none"  # no match ranks last
    assert [r.record_id for r in unbound] == ["mrec_new", "mrec_old", "mrec_none"]


async def test_a_deleted_session_keeps_its_row_marked_and_loses_its_messages(pool):
    """Q29. Bug caught: the session row removed (so a record confirmed from it can't say so), its
    messages kept, a deleted session still listed, or deleting twice reading as success."""
    chats = ChatRepository(pool)
    session = ChatSession("s_q29", "comms-agent", "ada", T0, project_id="group_run")
    await chats.create_session(session)
    await chats.store_message(ChatMessage("m_q29", "s_q29", "user", "keep this", T0))

    await chats.delete_session("s_q29", T0 + timedelta(minutes=5))

    held = await chats.get_session("s_q29")
    assert (held.project_id, held.deleted_at is not None) == ("group_run", True)
    assert await chats.get_session_messages("s_q29") == []
    assert await chats.get_message("m_q29") is None
    assert await chats.list_sessions("comms-agent", "ada") == []
    with pytest.raises(SessionNotFoundError):
        await chats.delete_session("s_q29", T0)


async def test_a_chat_exposure_reads_back_as_recorded_once(pool):
    """Bug caught: a section's failure or an omission's limit lost through JSONB, or a turn's
    exposure recorded twice."""
    store = PostgresCrossCycleMemoryStore(pool=pool)
    exposure = ChatExposure(
        session_id="s_x", message_id="m_x", user_id="ada", agent_id="comms-agent",
        project_id="group_run", assembled_at=T0,
        sections=(
            Section(SectionKind.NOTES, Need.OPTIONAL, Disposition.FAILED),
            Section(
                SectionKind.PREFERENCES, Need.OPTIONAL, Disposition.SUPPLIED,
                supplied=(RecordRef("mrec_p", "1"),), omitted=((RecordRef("mrec_q", "2"), "budget"),),
                effective_budget=1500,
            ),
        ),
    )  # fmt: skip

    assert await store.record_chat_exposure(exposure) is True
    assert await store.record_chat_exposure(exposure) is False
    assert await store.list_chat_exposures("s_x") == [exposure]
