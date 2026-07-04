"""Integration tests for SIP-0090 §5 — PostgresEmbodimentState against live Postgres.

Requires a running Postgres (docker-compose up -d postgres). Proves what an
in-memory fake can't: the `embodiments` migration applies, records round-trip with
fields intact (the §13 "records exist" acceptance), and the partial unique index
`uq_embodiments_one_active_per_agent` is the **hard backstop** for the single-active
rule (§5.5) — a second *live* embodiment for one agent is rejected at the DB, while
detached history and a second agent's active embodiment are fine.
"""

from __future__ import annotations

import os
import socket
import uuid
from pathlib import Path

import pytest
import pytest_asyncio

from squadops.runtime.embodiment import Embodiment

pytestmark = [pytest.mark.docker, pytest.mark.domain_runtime]

POSTGRES_URL = os.getenv(
    "POSTGRES_URL", "postgresql://squadops:squadops-dev@localhost:5432/squadops"
)

try:
    import asyncpg
except ImportError:
    pytest.skip("asyncpg not installed", allow_module_level=True)


def _pg_available() -> bool:
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(2)
        s.connect(("localhost", 5432))
        s.close()
        return True
    except OSError:
        return False


if not _pg_available():
    pytest.skip(
        "Postgres not reachable on localhost:5432 — start with docker-compose up -d postgres",
        allow_module_level=True,
    )


@pytest_asyncio.fixture
async def adapter():
    from adapters.persistence.runtime.embodiment_postgres import PostgresEmbodimentState
    from squadops.api.runtime.migrations import apply_migrations

    pool = await asyncpg.create_pool(POSTGRES_URL, min_size=1, max_size=5)
    await apply_migrations(pool, Path(__file__).parents[3] / "infra" / "migrations")
    yield PostgresEmbodimentState(pool)
    await pool.close()


def _emb(agent_id: str, state: str, **overrides) -> Embodiment:
    base = dict(
        embodiment_id=f"emb_{uuid.uuid4().hex[:10]}",
        agent_id=agent_id,
        embodiment_type="discord",
        platform="discord.com",
        attachment_state=state,
        health="healthy",
    )
    base.update(overrides)
    return Embodiment(**base)


async def _cleanup(adapter, agent_id: str) -> None:
    async with adapter._pool.acquire() as conn:
        await conn.execute("DELETE FROM embodiments WHERE agent_id = $1", agent_id)


async def test_record_round_trips_with_fields_intact(adapter):
    agent = f"agent_{uuid.uuid4().hex[:8]}"
    emb = _emb(
        agent,
        "attaching",
        capability_set=("send_message", "read_channel"),
        location_ref="guild/1/chan/2",
        credentials_ref="secret://discord/token",
    )
    try:
        await adapter.create_embodiment(emb)
        got = await adapter.get_embodiment(emb.embodiment_id)
        assert got == emb  # frozen-dataclass equality: every field, incl. the tuple capability_set
    finally:
        await _cleanup(adapter, agent)


async def test_second_active_embodiment_for_agent_is_rejected_by_the_index(adapter):
    agent = f"agent_{uuid.uuid4().hex[:8]}"
    try:
        await adapter.create_embodiment(_emb(agent, "attached"))
        with pytest.raises(asyncpg.UniqueViolationError):
            await adapter.create_embodiment(_emb(agent, "desynced"))  # 2nd live → rejected
    finally:
        await _cleanup(adapter, agent)


async def test_detached_history_and_other_agents_do_not_block_a_new_active(adapter):
    agent = f"agent_{uuid.uuid4().hex[:8]}"
    other = f"agent_{uuid.uuid4().hex[:8]}"
    try:
        await adapter.create_embodiment(_emb(agent, "detached"))
        await adapter.create_embodiment(_emb(agent, "detached"))  # history accumulates freely
        await adapter.create_embodiment(_emb(other, "attached"))  # different agent is fine
        await adapter.create_embodiment(_emb(agent, "attached"))  # one active for `agent` — ok

        active = await adapter.get_active_embodiment(agent)
        assert active is not None and active.attachment_state == "attached"
        assert len(await adapter.list_for_agent(agent)) == 3
    finally:
        await _cleanup(adapter, agent)
        await _cleanup(adapter, other)


async def test_transition_moves_state_and_active_query_reflects_it(adapter):
    agent = f"agent_{uuid.uuid4().hex[:8]}"
    emb = _emb(agent, "attaching")
    try:
        await adapter.create_embodiment(emb)
        assert await adapter.get_active_embodiment(agent) is None  # attaching is not live

        await adapter.transition_state(emb.embodiment_id, "attached")
        active = await adapter.get_active_embodiment(agent)
        assert active is not None and active.embodiment_id == emb.embodiment_id
    finally:
        await _cleanup(adapter, agent)
