"""Tests for ChatRepository (SIP-0085 Phase 3).

Uses mock asyncpg pool — no real database needed for unit tests.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from adapters.persistence.chat_repository import ChatRepository
from squadops.comms.models import ChatMessage, ChatSession, SessionNotFoundError

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_pool():
    """Build a mock asyncpg pool with context-managed connection."""
    pool = MagicMock()
    conn = AsyncMock()

    # Make pool.acquire() work as async context manager
    ctx = AsyncMock()
    ctx.__aenter__ = AsyncMock(return_value=conn)
    ctx.__aexit__ = AsyncMock(return_value=None)
    pool.acquire.return_value = ctx

    return pool, conn


def _now():
    return datetime.now(UTC)


def _make_session(session_id: str = "s1") -> ChatSession:
    return ChatSession(
        session_id=session_id,
        agent_id="comms-agent",
        user_id="user1",
        started_at=_now(),
    )


def _make_message(message_id: str = "m1", session_id: str = "s1") -> ChatMessage:
    return ChatMessage(
        message_id=message_id,
        session_id=session_id,
        role="user",
        content="hello agent",
        created_at=_now(),
    )


def _make_session_row(session_id: str = "s1") -> dict:
    return {
        "session_id": session_id,
        "agent_id": "comms-agent",
        "user_id": "user1",
        "started_at": _now(),
        "ended_at": None,
        "metadata": "{}",
    }


def _make_message_row(message_id: str = "m1", session_id: str = "s1") -> dict:
    return {
        "message_id": message_id,
        "session_id": session_id,
        "role": "user",
        "content": "hello agent",
        "created_at": _now(),
        "metadata": "{}",
    }


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestChatRepositoryCreateSession:
    """Session creation persists to Postgres."""

    async def test_create_session_executes_insert(self):
        """create_session() calls conn.execute with correct SQL and params."""
        pool, conn = _make_pool()
        repo = ChatRepository(pool=pool)
        session = _make_session()

        result = await repo.create_session(session)

        conn.execute.assert_called_once()
        sql = conn.execute.call_args[0][0]
        assert "INSERT INTO chat_sessions" in sql
        assert result.session_id == session.session_id

    async def test_create_session_serializes_metadata(self):
        """Metadata dict is JSON-serialized for the JSONB column."""
        pool, conn = _make_pool()
        repo = ChatRepository(pool=pool)
        session = ChatSession(
            session_id="s-meta",
            agent_id="comms-agent",
            user_id="user1",
            started_at=_now(),
            metadata={"source": "console"},
        )

        await repo.create_session(session)

        # Last positional arg to execute is the serialized metadata
        call_args = conn.execute.call_args[0]
        metadata_arg = call_args[-1]  # last param
        assert json.loads(metadata_arg) == {"source": "console"}


class TestChatRepositoryGetSession:
    """Session retrieval and not-found handling."""

    async def test_get_session_returns_assembled_session(self):
        """get_session() reconstructs a ChatSession from row data."""
        pool, conn = _make_pool()
        conn.fetchrow.return_value = _make_session_row("s-found")
        repo = ChatRepository(pool=pool)

        session = await repo.get_session("s-found")

        assert session.session_id == "s-found"
        assert session.agent_id == "comms-agent"

    async def test_get_session_not_found_raises(self):
        """get_session() raises SessionNotFoundError for missing session."""
        pool, conn = _make_pool()
        conn.fetchrow.return_value = None
        repo = ChatRepository(pool=pool)

        with pytest.raises(SessionNotFoundError, match="s-missing"):
            await repo.get_session("s-missing")


class TestChatRepositoryEndSession:
    """Session ending and not-found handling."""

    async def test_end_session_updates_ended_at(self):
        """end_session() executes UPDATE with ended_at timestamp."""
        pool, conn = _make_pool()
        conn.execute.return_value = "UPDATE 1"
        repo = ChatRepository(pool=pool)

        now = _now()
        await repo.end_session("s1", now)

        conn.execute.assert_called_once()
        sql = conn.execute.call_args[0][0]
        assert "UPDATE chat_sessions" in sql

    async def test_end_session_not_found_raises(self):
        """end_session() raises SessionNotFoundError if no rows updated."""
        pool, conn = _make_pool()
        conn.execute.return_value = "UPDATE 0"
        repo = ChatRepository(pool=pool)

        with pytest.raises(SessionNotFoundError):
            await repo.end_session("s-gone", _now())


class TestChatRepositoryMessages:
    """Message CRUD operations."""

    async def test_store_message_executes_insert(self):
        """store_message() inserts into chat_messages."""
        pool, conn = _make_pool()
        repo = ChatRepository(pool=pool)
        msg = _make_message()

        result = await repo.store_message(msg)

        conn.execute.assert_called_once()
        sql = conn.execute.call_args[0][0]
        assert "INSERT INTO chat_messages" in sql
        assert result.message_id == msg.message_id

    async def test_get_session_messages_returns_ordered(self):
        """get_session_messages() returns messages in creation order."""
        pool, conn = _make_pool()
        rows = [
            _make_message_row("m1", "s1"),
            _make_message_row("m2", "s1"),
        ]
        conn.fetch.return_value = rows
        repo = ChatRepository(pool=pool)

        messages = await repo.get_session_messages("s1")

        assert len(messages) == 2
        assert messages[0].message_id == "m1"
        assert messages[1].message_id == "m2"
        # Verify ORDER BY is in the SQL
        sql = conn.fetch.call_args[0][0]
        assert "ORDER BY created_at ASC" in sql

    async def test_get_session_messages_respects_limit(self):
        """Limit parameter is passed to SQL query."""
        pool, conn = _make_pool()
        conn.fetch.return_value = []
        repo = ChatRepository(pool=pool)

        await repo.get_session_messages("s1", limit=10)

        call_args = conn.fetch.call_args[0]
        assert call_args[2] == 10  # third positional param is limit


class TestChatRepositoryListSessions:
    """Session listing by agent+user."""

    async def test_list_sessions_filters_by_agent_and_user(self):
        """list_sessions() queries with agent_id and user_id filters."""
        pool, conn = _make_pool()
        conn.fetch.return_value = [_make_session_row("s1")]
        repo = ChatRepository(pool=pool)

        sessions = await repo.list_sessions("comms-agent", "user1")

        assert len(sessions) == 1
        sql = conn.fetch.call_args[0][0]
        assert "agent_id" in sql
        assert "user_id" in sql
        assert "ORDER BY started_at DESC" in sql


class TestChatRepositoryJsonb:
    """JSONB parsing edge cases."""

    def test_parse_jsonb_handles_string(self):
        """asyncpg returns JSONB as string — parser decodes it."""
        result = ChatRepository._parse_jsonb('{"key": "value"}')
        assert result == {"key": "value"}

    def test_parse_jsonb_handles_dict(self):
        """Already-decoded dict passes through."""
        result = ChatRepository._parse_jsonb({"key": "value"})
        assert result == {"key": "value"}

    def test_parse_jsonb_handles_none(self):
        """None returns empty dict."""
        result = ChatRepository._parse_jsonb(None)
        assert result == {}
