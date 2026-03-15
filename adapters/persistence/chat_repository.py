"""Postgres chat repository for console messaging (SIP-0085 Phase 3).

Postgres is the authoritative store for chat history (P3-RC2).
All methods are async and use the shared asyncpg pool.
"""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    import asyncpg

from squadops.comms.models import ChatMessage, ChatSession, SessionNotFoundError

logger = logging.getLogger(__name__)


class ChatRepository:
    """Postgres-backed chat persistence.

    Follows the same pattern as PostgresCycleRegistry: receives an asyncpg
    pool at construction, uses context-managed connections for each operation.
    """

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def create_session(self, session: ChatSession) -> ChatSession:
        """Create a new chat session.

        Args:
            session: Session to persist.

        Returns:
            The persisted session (same object — Postgres is source of truth).
        """
        async with self._pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO chat_sessions (session_id, agent_id, user_id, started_at, metadata)
                VALUES ($1, $2, $3, $4, $5)
                """,
                session.session_id,
                session.agent_id,
                session.user_id,
                session.started_at,
                json.dumps(session.metadata),
            )
        return session

    async def get_session(self, session_id: str) -> ChatSession:
        """Fetch a session by ID.

        Raises:
            SessionNotFoundError: If session does not exist.
        """
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM chat_sessions WHERE session_id = $1",
                session_id,
            )
        if row is None:
            raise SessionNotFoundError(f"Session not found: {session_id}")
        return self._assemble_session(row)

    async def end_session(self, session_id: str, ended_at: Any) -> None:
        """Mark a session as ended.

        Raises:
            SessionNotFoundError: If session does not exist.
        """
        async with self._pool.acquire() as conn:
            result = await conn.execute(
                "UPDATE chat_sessions SET ended_at = $1 WHERE session_id = $2",
                ended_at,
                session_id,
            )
            if result == "UPDATE 0":
                raise SessionNotFoundError(f"Session not found: {session_id}")

    async def list_sessions(
        self,
        agent_id: str,
        user_id: str,
        limit: int = 50,
    ) -> list[ChatSession]:
        """List sessions for an agent+user pair, most recent first."""
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT * FROM chat_sessions
                WHERE agent_id = $1 AND user_id = $2
                ORDER BY started_at DESC
                LIMIT $3
                """,
                agent_id,
                user_id,
                limit,
            )
        return [self._assemble_session(r) for r in rows]

    async def store_message(self, message: ChatMessage) -> ChatMessage:
        """Persist a chat message.

        Postgres write is required (P3-RC2). Failure here is a real error
        that must be surfaced.

        Returns:
            The persisted message.
        """
        async with self._pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO chat_messages
                    (message_id, session_id, role, content, created_at, metadata)
                VALUES ($1, $2, $3, $4, $5, $6)
                """,
                message.message_id,
                message.session_id,
                message.role,
                message.content,
                message.created_at,
                json.dumps(message.metadata),
            )
        return message

    async def get_session_messages(
        self,
        session_id: str,
        limit: int = 100,
    ) -> list[ChatMessage]:
        """Get messages for a session, ordered by creation time (ascending)."""
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT * FROM chat_messages
                WHERE session_id = $1
                ORDER BY created_at ASC
                LIMIT $2
                """,
                session_id,
                limit,
            )
        return [self._assemble_message(r) for r in rows]

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_jsonb(value: Any) -> dict:
        """Decode a JSONB column value (asyncpg returns strings)."""
        if isinstance(value, str):
            return json.loads(value)
        if value is None:
            return {}
        return value

    def _assemble_session(self, row: Any) -> ChatSession:
        """Reconstruct a ChatSession from a database row."""
        return ChatSession(
            session_id=row["session_id"],
            agent_id=row["agent_id"],
            user_id=row["user_id"],
            started_at=row["started_at"],
            ended_at=row["ended_at"],
            metadata=self._parse_jsonb(row["metadata"]),
        )

    def _assemble_message(self, row: Any) -> ChatMessage:
        """Reconstruct a ChatMessage from a database row."""
        return ChatMessage(
            message_id=row["message_id"],
            session_id=row["session_id"],
            role=row["role"],
            content=row["content"],
            created_at=row["created_at"],
            metadata=self._parse_jsonb(row["metadata"]),
        )
