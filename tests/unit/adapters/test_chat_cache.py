"""Tests for ChatSessionCache (SIP-0085 Phase 3).

Verifies best-effort semantics: failures are swallowed, never raised.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from unittest.mock import AsyncMock

from adapters.persistence.chat_cache import ChatSessionCache
from squadops.comms.models import ChatMessage

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_redis():
    """Build a mock Redis client."""
    redis = AsyncMock()
    redis.rpush = AsyncMock()
    redis.expire = AsyncMock()
    redis.lrange = AsyncMock(return_value=[])
    redis.set = AsyncMock()
    redis.get = AsyncMock(return_value=None)
    redis.delete = AsyncMock()
    return redis


def _make_message(msg_id: str = "m1") -> ChatMessage:
    return ChatMessage(
        message_id=msg_id,
        session_id="s1",
        role="user",
        content="hello",
        created_at=datetime.now(UTC),
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestCacheMessage:
    """cache_message() writes to Redis best-effort."""

    async def test_appends_to_redis_list(self):
        """Message is JSON-serialized and appended to session key."""
        redis = _make_redis()
        cache = ChatSessionCache(redis=redis)
        msg = _make_message()

        await cache.cache_message(msg)

        redis.rpush.assert_called_once()
        key = redis.rpush.call_args[0][0]
        assert "chat:session:s1:messages" == key
        payload = json.loads(redis.rpush.call_args[0][1])
        assert payload["message_id"] == "m1"
        assert payload["role"] == "user"

    async def test_sets_ttl(self):
        """TTL is applied after write."""
        redis = _make_redis()
        cache = ChatSessionCache(redis=redis, ttl_seconds=300)
        msg = _make_message()

        await cache.cache_message(msg)

        redis.expire.assert_called_once()
        assert redis.expire.call_args[0][1] == 300

    async def test_failure_is_swallowed(self):
        """Redis failure does not raise — best-effort semantics."""
        redis = _make_redis()
        redis.rpush = AsyncMock(side_effect=ConnectionError("Redis down"))
        cache = ChatSessionCache(redis=redis)
        msg = _make_message()

        # Should not raise
        await cache.cache_message(msg)


class TestGetMessages:
    """get_messages() reads from Redis, returns None on miss/error."""

    async def test_returns_parsed_messages(self):
        """Cached messages are JSON-parsed and returned."""
        redis = _make_redis()
        redis.lrange = AsyncMock(return_value=[
            json.dumps({"message_id": "m1", "role": "user", "content": "hi", "created_at": "2025-01-01T00:00:00"}),
            json.dumps({"message_id": "m2", "role": "assistant", "content": "hello", "created_at": "2025-01-01T00:00:01"}),
        ])
        cache = ChatSessionCache(redis=redis)

        result = await cache.get_messages("s1")

        assert result is not None
        assert len(result) == 2
        assert result[0]["role"] == "user"
        assert result[1]["role"] == "assistant"

    async def test_returns_none_on_empty(self):
        """Empty cache returns None (triggers Postgres fallback)."""
        redis = _make_redis()
        redis.lrange = AsyncMock(return_value=[])
        cache = ChatSessionCache(redis=redis)

        result = await cache.get_messages("s-empty")
        assert result is None

    async def test_returns_none_on_error(self):
        """Redis error returns None — best-effort semantics."""
        redis = _make_redis()
        redis.lrange = AsyncMock(side_effect=ConnectionError("Redis down"))
        cache = ChatSessionCache(redis=redis)

        result = await cache.get_messages("s1")
        assert result is None


class TestSessionMeta:
    """Session metadata caching."""

    async def test_cache_and_retrieve_meta(self):
        """Metadata is round-tripped through Redis."""
        redis = _make_redis()
        redis.get = AsyncMock(return_value=json.dumps({"agent_id": "comms-agent"}))
        cache = ChatSessionCache(redis=redis)

        await cache.cache_session_meta("s1", {"agent_id": "comms-agent"})
        redis.set.assert_called_once()

        result = await cache.get_session_meta("s1")
        assert result == {"agent_id": "comms-agent"}

    async def test_meta_failure_is_swallowed(self):
        """Redis failure on meta write does not raise."""
        redis = _make_redis()
        redis.set = AsyncMock(side_effect=ConnectionError("Redis down"))
        cache = ChatSessionCache(redis=redis)

        # Should not raise
        await cache.cache_session_meta("s1", {"key": "value"})


class TestInvalidateSession:
    """Session invalidation deletes both keys."""

    async def test_deletes_both_keys(self):
        """Both messages and meta keys are deleted."""
        redis = _make_redis()
        cache = ChatSessionCache(redis=redis)

        await cache.invalidate_session("s1")

        redis.delete.assert_called_once()
        deleted_keys = redis.delete.call_args[0]
        assert "chat:session:s1:messages" in deleted_keys
        assert "chat:session:s1:meta" in deleted_keys

    async def test_failure_is_swallowed(self):
        """Redis failure on invalidation does not raise."""
        redis = _make_redis()
        redis.delete = AsyncMock(side_effect=ConnectionError("Redis down"))
        cache = ChatSessionCache(redis=redis)

        # Should not raise
        await cache.invalidate_session("s1")
