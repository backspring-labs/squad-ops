"""Session store abstraction for SquadOps Console Auth BFF.

Provides an ABC and two implementations:
  - MemorySessionStore: in-process dict (default, development)
  - RedisSessionStore: redis.asyncio backend (production, survives restarts)
"""

from __future__ import annotations

import json
import time
from abc import ABC, abstractmethod
from typing import Any


class SessionStore(ABC):
    """Abstract session store with TTL and sliding-window support."""

    @abstractmethod
    async def get(self, key: str) -> dict[str, Any] | None:
        """Return session data or None if missing/expired."""

    @abstractmethod
    async def set(self, key: str, value: dict[str, Any], ttl: int) -> None:
        """Store session data with TTL in seconds.

        Raises ValueError if max_sessions limit is reached.
        """

    @abstractmethod
    async def delete(self, key: str) -> None:
        """Remove a session."""

    @abstractmethod
    async def touch(self, key: str, ttl: int) -> None:
        """Reset TTL for sliding-window idle timeout. No-op if key missing."""

    @abstractmethod
    async def count(self) -> int:
        """Return number of active (non-expired) sessions."""

    @abstractmethod
    async def close(self) -> None:
        """Release resources (connection pools, etc.)."""


class MemorySessionStore(SessionStore):
    """In-memory session store backed by a plain dict.

    Enforces ``max_sessions`` and lazy-expires entries on ``get()``.
    The ``.store`` attribute is exposed for test introspection.
    """

    def __init__(self, *, max_sessions: int = 10_000, default_ttl: int = 86400) -> None:
        self.store: dict[str, dict[str, Any]] = {}
        self.max_sessions = max_sessions
        self.default_ttl = default_ttl

    async def get(self, key: str) -> dict[str, Any] | None:
        entry = self.store.get(key)
        if entry is None:
            return None
        if time.time() > entry.get("_expires_at", float("inf")):
            del self.store[key]
            return None
        return entry.get("_data")

    async def set(self, key: str, value: dict[str, Any], ttl: int) -> None:
        # Lazy-purge expired before checking count
        self._purge_expired()
        if key not in self.store and len(self.store) >= self.max_sessions:
            raise ValueError("Max sessions limit reached")
        self.store[key] = {"_data": value, "_expires_at": time.time() + ttl}

    async def delete(self, key: str) -> None:
        self.store.pop(key, None)

    async def touch(self, key: str, ttl: int) -> None:
        entry = self.store.get(key)
        if entry is None:
            return
        if time.time() > entry.get("_expires_at", float("inf")):
            del self.store[key]
            return
        entry["_expires_at"] = time.time() + ttl

    async def count(self) -> int:
        self._purge_expired()
        return len(self.store)

    async def close(self) -> None:
        self.store.clear()

    def _purge_expired(self) -> None:
        now = time.time()
        expired = [k for k, v in self.store.items() if now > v.get("_expires_at", float("inf"))]
        for k in expired:
            del self.store[k]


class RedisSessionStore(SessionStore):
    """Redis-backed session store using ``redis.asyncio``.

    Key format: ``squadops:session:{key}`` (or custom prefix).
    TTL is managed natively by Redis SETEX / EXPIRE.
    """

    def __init__(
        self,
        client: Any,
        *,
        prefix: str = "squadops:session:",
        max_sessions: int = 100_000,
    ) -> None:
        self._client = client
        self._prefix = prefix
        self.max_sessions = max_sessions

    def _key(self, key: str) -> str:
        return f"{self._prefix}{key}"

    async def get(self, key: str) -> dict[str, Any] | None:
        raw = await self._client.get(self._key(key))
        if raw is None:
            return None
        return json.loads(raw)

    async def set(self, key: str, value: dict[str, Any], ttl: int) -> None:
        # Check count before writing a new key
        rkey = self._key(key)
        exists = await self._client.exists(rkey)
        if not exists:
            current = await self.count()
            if current >= self.max_sessions:
                raise ValueError("Max sessions limit reached")
        await self._client.setex(rkey, ttl, json.dumps(value))

    async def delete(self, key: str) -> None:
        await self._client.delete(self._key(key))

    async def touch(self, key: str, ttl: int) -> None:
        await self._client.expire(self._key(key), ttl)

    async def count(self) -> int:
        keys = await self._client.keys(f"{self._prefix}*")
        return len(keys)

    async def close(self) -> None:
        await self._client.aclose()
