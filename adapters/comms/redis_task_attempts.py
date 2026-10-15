"""A dispatched task's delivery record in Redis (#1977; ``TaskAttemptsPort``).

The stack's Redis, which every agent already reaches (``comms.redis.url``). Two keys per send of a
task (its ``delivery_key``, §5.3c, #2333), each expiring after ``ttl_seconds``:
- ``comms:attempts:{key}``, an ``INCR`` counted before the handler runs;
- ``comms:done:{key}``, set once the reply was published.

Losing Redis loses the marks, so the window shrinks to nothing until it refills: the failure is
duplicate work, never lost work. The agent falls back to §5.3a's flag rule while a read fails.
"""

from __future__ import annotations

from typing import Any

from squadops.ports.comms.task_attempts import TaskAttemptsPort

_ATTEMPTS = "comms:attempts:"
_DONE = "comms:done:"


class RedisTaskAttempts(TaskAttemptsPort):
    def __init__(self, client: Any, ttl_seconds: int) -> None:
        self._client = client
        self._ttl = ttl_seconds

    @classmethod
    def from_url(cls, url: str, ttl_seconds: int) -> RedisTaskAttempts:
        import redis.asyncio as redis

        return cls(redis.from_url(url), ttl_seconds)

    async def completed(self, key: str) -> bool:
        return bool(await self._client.exists(_DONE + key))

    async def begin_attempt(self, key: str) -> int:
        counter = _ATTEMPTS + key
        count = int(await self._client.incr(counter))
        if count == 1:
            await self._client.expire(counter, self._ttl)
        return count

    async def mark_completed(self, key: str) -> None:
        await self._client.set(_DONE + key, "1", ex=self._ttl)

    async def close(self) -> None:
        await self._client.aclose()
