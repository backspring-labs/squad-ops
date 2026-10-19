"""Chat domain models for console messaging (SIP-0085 Phase 3).

Frozen dataclasses for chat sessions and messages. Postgres is
the authoritative store (P3-RC2); Redis is an opportunistic cache.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass(frozen=True)
class ChatSession:
    """A conversation session between a user and an agent."""

    session_id: str
    agent_id: str
    user_id: str
    started_at: datetime
    ended_at: datetime | None = None
    metadata: dict = field(default_factory=dict)
    #: The project the session was bound to when it opened, server-side; ``None`` for an unbound
    #: session, which sees only its owner's private records (SIP-0110 Appendix A §3.3, #2180).
    project_id: str | None = None
    #: When its owner deleted it (Q29). Its messages are gone, and it reads as no session.
    deleted_at: datetime | None = None


@dataclass(frozen=True)
class ChatMessage:
    """A single message within a chat session."""

    message_id: str
    session_id: str
    role: str  # "user" or "assistant"
    content: str
    created_at: datetime
    metadata: dict = field(default_factory=dict)


class ChatError(Exception):
    """Base exception for chat domain errors."""


class SessionNotFoundError(ChatError):
    """Raised when a chat session is not found."""


class AgentNotMessagingEnabledError(ChatError):
    """Raised when a non-messaging agent is targeted for chat."""


class AgentNotFoundError(ChatError):
    """Raised when an agent is not found."""
