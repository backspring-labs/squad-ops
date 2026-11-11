"""A scripted cycle's answer positions, in Redis or in this process (#3005; ``ScriptPositionsPort``).

**Redis** is the stack's own, which every agent already reaches (``comms.redis.url``), as the
delivery record does (#1977). Three keys per cycle, each expiring ``ttl_seconds`` after its last
write:
- ``llm:script:order:{cycle}:{task_type}``: the task ids of that type, in the order of their first
  calls;
- ``llm:script:calls:{cycle}``: each task's call count;
- ``llm:script:bound:{cycle}``: the script the cycle named.

One call is counted in one Lua script, so its occurrence and its call are read and written as one
step whichever agent asks.

**Losing Redis** loses a cycle's positions, as a restart used to. A lookup that can't reach Redis
raises, and the scripted call fails naming why. It is never answered from a guessed position.

**In this process** is for tests: its positions die with the process, which is the defect the
Redis store exists to remove.
"""

from __future__ import annotations

from typing import Any

from squadops.ports.llm.script_positions import ScriptPositionsPort

_ORDER = "llm:script:order:"
_CALLS = "llm:script:calls:"
_BOUND = "llm:script:bound:"

#: KEYS: the order list, the calls hash. ARGV: the task id, the TTL in seconds.
#: Returns {occurrence, call}.
_NEXT_CALL = """
local place = redis.call('LPOS', KEYS[1], ARGV[1])
if not place then
  redis.call('RPUSH', KEYS[1], ARGV[1])
  place = redis.call('LLEN', KEYS[1]) - 1
end
local calls = redis.call('HINCRBY', KEYS[2], ARGV[1], 1)
redis.call('EXPIRE', KEYS[1], ARGV[2])
redis.call('EXPIRE', KEYS[2], ARGV[2])
return {place + 1, calls}
"""


class RedisScriptPositions(ScriptPositionsPort):
    def __init__(self, client: Any, ttl_seconds: int) -> None:
        if ttl_seconds < 1:
            raise ValueError(f"ttl_seconds is {ttl_seconds}; positions must outlive a cycle")
        self._client = client
        self._ttl = ttl_seconds

    @classmethod
    def from_url(cls, url: str, ttl_seconds: int) -> RedisScriptPositions:
        import redis.asyncio as redis

        return cls(redis.from_url(url), ttl_seconds)

    async def next_call(self, cycle_id: str, task_type: str, task_id: str) -> tuple[int, int]:
        occurrence, call = await self._client.eval(
            _NEXT_CALL,
            2,
            f"{_ORDER}{cycle_id}:{task_type}",
            f"{_CALLS}{cycle_id}",
            task_id,
            self._ttl,
        )
        return int(occurrence), int(call)

    async def bind_script(self, cycle_id: str, named: str | None) -> str | None:
        key = _BOUND + cycle_id
        if named is not None:
            await self._client.set(key, named, nx=True, ex=self._ttl)
        bound = await self._client.get(key)
        if bound is None:
            return None
        return bound.decode() if isinstance(bound, bytes) else str(bound)

    async def close(self) -> None:
        await self._client.aclose()


class InProcessScriptPositions(ScriptPositionsPort):
    """Positions held in this process, for tests. They die with it."""

    def __init__(self) -> None:
        self._order: dict[tuple[str, str], list[str]] = {}
        self._calls: dict[tuple[str, str], int] = {}
        self._bound: dict[str, str] = {}

    async def next_call(self, cycle_id: str, task_type: str, task_id: str) -> tuple[int, int]:
        seen = self._order.setdefault((cycle_id, task_type), [])
        if task_id not in seen:
            seen.append(task_id)
        key = (cycle_id, task_id)
        self._calls[key] = self._calls.get(key, 0) + 1
        return seen.index(task_id) + 1, self._calls[key]

    async def bind_script(self, cycle_id: str, named: str | None) -> str | None:
        if named is not None:
            self._bound.setdefault(cycle_id, named)
        return self._bound.get(cycle_id)
