"""Tests for chat domain models (SIP-0085 Phase 3)."""

from __future__ import annotations

import dataclasses
from datetime import UTC, datetime

import pytest

from squadops.comms.models import (
    AgentNotFoundError,
    AgentNotMessagingEnabledError,
    ChatError,
    ChatMessage,
    ChatSession,
    SessionNotFoundError,
)


class TestChatSession:
    """ChatSession frozen dataclass behavior."""

    def test_frozen_immutability(self):
        """Frozen dataclass raises on mutation attempt."""
        session = ChatSession(
            session_id="s1",
            agent_id="comms-agent",
            user_id="user1",
            started_at=datetime.now(UTC),
        )
        with pytest.raises(dataclasses.FrozenInstanceError):
            session.agent_id = "other"  # type: ignore[misc]

    def test_replace_produces_new_instance(self):
        """dataclasses.replace() on frozen session works for ending a session."""
        now = datetime.now(UTC)
        session = ChatSession(
            session_id="s1",
            agent_id="comms-agent",
            user_id="user1",
            started_at=now,
        )
        ended = dataclasses.replace(session, ended_at=now)
        assert ended.ended_at == now
        assert session.ended_at is None  # original unchanged


class TestChatMessage:
    """ChatMessage frozen dataclass behavior."""

    def test_frozen_immutability(self):
        """Frozen dataclass raises on mutation attempt."""
        msg = ChatMessage(
            message_id="m1",
            session_id="s1",
            role="user",
            content="hello",
            created_at=datetime.now(UTC),
        )
        with pytest.raises(dataclasses.FrozenInstanceError):
            msg.content = "modified"  # type: ignore[misc]


class TestChatErrors:
    """Error hierarchy catches correct exceptions."""

    def test_session_not_found_is_chat_error(self):
        """SessionNotFoundError is a ChatError — can be caught at domain level."""
        with pytest.raises(ChatError):
            raise SessionNotFoundError("not found")

    def test_agent_not_found_is_chat_error(self):
        """AgentNotFoundError is a ChatError."""
        with pytest.raises(ChatError):
            raise AgentNotFoundError("not found")

    def test_agent_not_messaging_enabled_is_chat_error(self):
        """AgentNotMessagingEnabledError is a ChatError."""
        with pytest.raises(ChatError):
            raise AgentNotMessagingEnabledError("not enabled")

    def test_error_message_preserved(self):
        """Error messages are accessible via str()."""
        err = SessionNotFoundError("Session xyz not found")
        assert "xyz" in str(err)
