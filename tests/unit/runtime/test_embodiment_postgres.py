"""Unit tests for SIP-0090 §5 — PostgresEmbodimentState adapter (slice 1b).

Each test answers: what bug would it catch?

Bug classes guarded:
- Row→dataclass mapping drift: the JSONB `capability_set` must decode to a **tuple**
  (a list would silently break the frozen dataclass's equality/hashing), and the
  enum columns must round-trip;
- write-side JSONB drift: `capability_set` must be `json.dumps`'d, not passed as a
  Python list;
- the `get_active_embodiment` query filtering on the wrong states (§5.5 semantics);
- a missing-row update returning None instead of surfacing (KeyError).
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from adapters.persistence.runtime.embodiment_postgres import (
    PostgresEmbodimentState,
    _loads_jsonb,
)
from squadops.runtime.embodiment import Embodiment

pytestmark = [pytest.mark.domain_runtime]


class _AcquireCtx:
    def __init__(self, conn):
        self._conn = conn

    async def __aenter__(self):
        return self._conn

    async def __aexit__(self, *_):
        return False


def _make_pool(conn):
    pool = MagicMock()
    pool.acquire.return_value = _AcquireCtx(conn)
    return pool


def _embodiment(**overrides):
    base = dict(
        embodiment_id="emb-1",
        agent_id="max",
        embodiment_type="discord",
        platform="discord.com",
        attachment_state="unattached",
        health="healthy",
    )
    base.update(overrides)
    return Embodiment(**base)


def _row(**overrides):
    base = {
        "embodiment_id": "emb-1",
        "agent_id": "max",
        "embodiment_type": "discord",
        "platform": "discord.com",
        "attachment_state": "attached",
        "health": "healthy",
        "capability_set": '["send_message", "read_channel"]',
        "location_ref": "guild/1/chan/2",
        "last_health_check_at": None,
        "credentials_ref": "secret://discord/token",
    }
    base.update(overrides)
    return base


async def test_create_serializes_capability_set_as_json():
    conn = AsyncMock()
    adapter = PostgresEmbodimentState(_make_pool(conn))

    await adapter.create_embodiment(_embodiment(capability_set=("send_message", "read_channel")))

    params = conn.execute.call_args.args
    # params[0] is the SQL; the capability_set arg must be a JSON string, not a list
    cap_arg = next(p for p in params[1:] if isinstance(p, str) and p.startswith("["))
    assert json.loads(cap_arg) == ["send_message", "read_channel"]


async def test_get_embodiment_maps_row_and_decodes_capability_set_to_tuple():
    conn = AsyncMock()
    conn.fetchrow.return_value = _row(attachment_state="attached")
    adapter = PostgresEmbodimentState(_make_pool(conn))

    emb = await adapter.get_embodiment("emb-1")

    assert emb is not None
    assert emb.capability_set == ("send_message", "read_channel")  # JSONB → tuple, frozen-safe
    assert isinstance(emb.capability_set, tuple)
    assert emb.attachment_state == "attached"
    assert emb.is_active is True  # mapped state drives the §5.5 helper


async def test_get_embodiment_returns_none_when_absent():
    conn = AsyncMock()
    conn.fetchrow.return_value = None
    adapter = PostgresEmbodimentState(_make_pool(conn))
    assert await adapter.get_embodiment("nope") is None


async def test_get_active_embodiment_filters_on_the_live_states():
    conn = AsyncMock()
    conn.fetchrow.return_value = None
    adapter = PostgresEmbodimentState(_make_pool(conn))

    await adapter.get_active_embodiment("max")

    sql, agent_id, states = conn.fetchrow.call_args.args
    assert agent_id == "max"
    assert states == ["attached", "desynced", "reconnecting"]  # §5.5 active set only
    assert "attachment_state = ANY" in sql


async def test_transition_state_raises_when_row_absent():
    conn = AsyncMock()
    conn.fetchrow.return_value = None
    adapter = PostgresEmbodimentState(_make_pool(conn))
    with pytest.raises(KeyError, match="nope"):
        await adapter.transition_state("nope", "attaching")


async def test_transition_state_updates_the_attachment_state_column():
    conn = AsyncMock()
    conn.fetchrow.return_value = _row(attachment_state="attaching")
    adapter = PostgresEmbodimentState(_make_pool(conn))

    result = await adapter.transition_state("emb-1", "attaching")

    sql, embodiment_id, value = conn.fetchrow.call_args.args
    assert "SET attachment_state = $2" in sql
    assert (embodiment_id, value) == ("emb-1", "attaching")
    assert result.attachment_state == "attaching"


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (None, []),  # NULL column
        ('["a", "b"]', ["a", "b"]),  # asyncpg default: JSONB as str
        (["a"], ["a"]),  # a driver that already decoded it
    ],
)
def test_loads_jsonb_is_robust_to_str_null_and_list(value, expected):
    assert _loads_jsonb(value) == expected
