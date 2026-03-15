"""Pydantic DTOs for SIP-0085 chat API routes."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

# =============================================================================
# Request DTOs
# =============================================================================


class ChatMessageRequest(BaseModel):
    """Send a chat message to an agent."""

    message: str = Field(..., min_length=1, max_length=10000)
    session_id: str | None = Field(
        default=None,
        description="Existing session ID. Omit to start a new session.",
    )

    model_config = ConfigDict(extra="forbid")


# =============================================================================
# Response DTOs
# =============================================================================


class ChatSessionDTO(BaseModel):
    """Chat session summary."""

    session_id: str
    agent_id: str
    user_id: str
    started_at: datetime
    ended_at: datetime | None = None


class ChatMessageDTO(BaseModel):
    """A single chat message."""

    message_id: str
    session_id: str
    role: str
    content: str
    created_at: datetime


class MessagingAgentDTO(BaseModel):
    """An agent with messaging enabled."""

    agent_id: str
    display_name: str
    description: str
    a2a_port: int
