"""A scripted cycle's answer positions in a real Redis (#3005).

What bugs would these catch?
- The Lua script counting an occurrence or a call wrong, which no fake can catch, since a fake
  would re-implement the script.
- Two processes (an agent and its restarted self) reading different places for one cycle.
- A cycle's binding replaced by a later script.
- Keys left to live for ever.

Runs on database 15 with this run's own cycle ids, and deletes only its own keys, so it never
touches a deploy's data on a box whose Redis is the stack's.
"""

from __future__ import annotations

import uuid

import pytest
import redis.asyncio as redis

from adapters.llm.script_positions import RedisScriptPositions

pytestmark = [pytest.mark.redis, pytest.mark.service_redis]

TTL = 3600


@pytest.fixture
async def client(redis_container):
    url = f"redis://localhost:{redis_container.get_exposed_port(6379)}/15"
    connection = redis.from_url(url)
    cycle = f"cyc_test_{uuid.uuid4().hex[:12]}"
    yield connection, cycle, url
    keys = [k async for k in connection.scan_iter(match=f"llm:script:*{cycle}*")]
    if keys:
        await connection.delete(*keys)
    await connection.aclose()


async def test_two_processes_read_one_cycle_s_occurrences_and_calls(client):
    connection, cycle, url = client
    agent = RedisScriptPositions(connection, TTL)
    restarted = RedisScriptPositions.from_url(url, TTL)  # a new process: its own connection

    seen = [
        await agent.next_call(cycle, "development.develop", "task-a"),
        await agent.next_call(cycle, "development.develop", "task-a"),
        await restarted.next_call(cycle, "development.develop", "task-b"),
        await restarted.next_call(cycle, "development.develop", "task-a"),
        await restarted.next_call(cycle, "qa.test", "task-q"),
    ]
    await restarted.close()

    assert seen == [(1, 1), (1, 2), (2, 1), (1, 3), (1, 1)]


async def test_a_cycle_keeps_the_first_script_it_was_bound_to_and_every_key_expires(client):
    connection, cycle, _ = client
    positions = RedisScriptPositions(connection, TTL)

    before = await positions.bind_script(cycle, None)
    first = await positions.bind_script(cycle, "shelf@0123456789ab")
    later = await positions.bind_script(cycle, "other@0123456789ab")
    unnamed = await positions.bind_script(cycle, None)
    await positions.next_call(cycle, "qa.test", "task-q")

    assert (before, first, later, unnamed) == (
        None,
        "shelf@0123456789ab",
        "shelf@0123456789ab",
        "shelf@0123456789ab",
    )
    keys = [k async for k in connection.scan_iter(match=f"llm:script:*{cycle}*")]
    ttls = [await connection.ttl(k) for k in keys]
    assert len(keys) == 3
    assert all(0 < t <= TTL for t in ttls)


def test_a_store_that_would_expire_at_once_is_refused():
    with pytest.raises(ValueError, match="must outlive a cycle"):
        RedisScriptPositions(object(), 0)
