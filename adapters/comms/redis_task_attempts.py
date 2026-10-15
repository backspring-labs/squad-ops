"""A dispatched task's delivery record in Redis (#1977; ``TaskAttemptsPort``).

The stack's Redis, which every agent already reaches (``comms.redis.url``). Two keys per task,
each expiring after ``ttl_seconds``:
- ``comms:attempts:{task_id}``, an ``INCR`` counted before the handler runs;
- ``comms:done:{task_id}``, set once the reply was published.

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

    async def completed(self, task_id: str) -> bool:
        return bool(await self._client.exists(_DONE + task_id))

    async def begin_attempt(self, task_id: str) -> int:
        key = _ATTEMPTS + task_id
        count = int(await self._client.incr(key))
        if count == 1:
            await self._client.expire(key, self._ttl)
        return count

    async def mark_completed(self, task_id: str) -> None:
        await self._client.set(_DONE + task_id, "1", ex=self._ttl)

    async def close(self) -> None:
        await self._client.aclose()
