"""Redis chat session cache for console messaging (SIP-0085 Phase 3).

Best-effort cache (P3-RC2): failed Redis writes do not fail the
conversation. Read path: Redis first → Postgres fallback → repopulate.
"""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from redis.asyncio import Redis

from squadops.comms.models import ChatMessage

logger = logging.getLogger(__name__)

# Default TTL for cached session data (seconds)
_DEFAULT_TTL_SECONDS = 3600  # 1 hour


class ChatSessionCache:
    """Redis-backed session cache for chat messages.

    All operations are best-effort — callers must handle None returns
    and fall back to Postgres.
    """

    def __init__(self, redis: Redis, ttl_seconds: int = _DEFAULT_TTL_SECONDS) -> None:
        self._redis = redis
        self._ttl = ttl_seconds

    def _messages_key(self, session_id: str) -> str:
        return f"chat:session:{session_id}:messages"

    def _meta_key(self, session_id: str) -> str:
        return f"chat:session:{session_id}:meta"

    async def cache_message(self, message: ChatMessage) -> None:
        """Append a message to the session's cached message list.

        Best-effort: logs on failure, never raises.
        """
        try:
            key = self._messages_key(message.session_id)
            payload = json.dumps({
                "message_id": message.message_id,
                "role": message.role,
                "content": message.content,
                "created_at": message.created_at.isoformat(),
            })
            await self._redis.rpush(key, payload)
            await self._redis.expire(key, self._ttl)
        except Exception:
            logger.debug("Redis cache_message failed (best-effort)", exc_info=True)

    async def get_messages(self, session_id: str) -> list[dict[str, Any]] | None:
        """Get cached messages for a session.

        Returns:
            List of message dicts, or None on cache miss / error.
        """
        try:
            key = self._messages_key(session_id)
            raw_messages = await self._redis.lrange(key, 0, -1)
            if not raw_messages:
                return None
            return [json.loads(m) for m in raw_messages]
        except Exception:
            logger.debug("Redis get_messages failed (best-effort)", exc_info=True)
            return None

    async def cache_session_meta(self, session_id: str, meta: dict[str, Any]) -> None:
        """Cache session metadata.

        Best-effort: logs on failure, never raises.
        """
        try:
            key = self._meta_key(session_id)
            await self._redis.set(key, json.dumps(meta), ex=self._ttl)
        except Exception:
            logger.debug("Redis cache_session_meta failed (best-effort)", exc_info=True)

    async def get_session_meta(self, session_id: str) -> dict[str, Any] | None:
        """Get cached session metadata.

        Returns:
            Session metadata dict, or None on cache miss / error.
        """
        try:
            key = self._meta_key(session_id)
            raw = await self._redis.get(key)
            if raw is None:
                return None
            return json.loads(raw)
        except Exception:
            logger.debug("Redis get_session_meta failed (best-effort)", exc_info=True)
            return None

    async def invalidate_session(self, session_id: str) -> None:
        """Remove all cached data for a session.

        Best-effort: logs on failure, never raises.
        """
        try:
            await self._redis.delete(
                self._messages_key(session_id),
                self._meta_key(session_id),
            )
        except Exception:
            logger.debug("Redis invalidate_session failed (best-effort)", exc_info=True)
