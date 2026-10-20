"""Pydantic DTOs for SIP-0085 chat API routes."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from squadops.api.memory_schemas import InstructionApplicabilityDTO, TaskTargetDTO

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
    project_id: str | None = Field(
        default=None,
        description=(
            "The project a new session is bound to (SIP-0110 Appendix A §3.3): it must exist, and "
            "binding it needs memory:read. Omit for an unbound session. Ignored on an existing "
            "session, whose stored binding every turn reads."
        ),
    )

    model_config = ConfigDict(extra="forbid")


class CaptureRequest(BaseModel):
    """A confirmed capture (§3.5): what the card showed, as the person chose it. Nothing is stored
    without one, and only the choices the session offers are accepted."""

    message_id: str = Field(..., description="The turn the record comes from, in this session")
    text: str = Field(..., min_length=1, max_length=4000)
    kind: str = Field(..., description="note or preference (stage A)")
    scope: str = Field(..., description="user, or project for a bound session's note")
    suggestion: bool = Field(
        default=False, description="A note marked as a claim, never a lesson's citation (§3.5)"
    )
    applicability: InstructionApplicabilityDTO | None = Field(
        default=None,
        description=(
            "A project instruction's task_types, roles and stacks, each explicit ('*' for any). "
            "Required for a project instruction, refused for anything else."
        ),
    )
    target: TaskTargetDTO | None = Field(
        default=None,
        description=(
            "A task instruction's cycle and its task types (#2180). Required for a task "
            "instruction, refused for anything else."
        ),
    )
    lesson_revision: str | None = Field(
        default=None,
        pattern=r"^pat_[0-9a-f]{16}@\d+$",
        description="The lesson revision a task instruction applies, kept as its provenance (§3.7)",
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
    project_id: str | None = None


class ChatMessageDTO(BaseModel):
    """A single chat message."""

    message_id: str
    session_id: str
    role: str
    content: str
    created_at: datetime


class CaptureChoiceDTO(BaseModel):
    """A kind and scope a confirmation card may offer this person in this session (§3.3)."""

    kind: str
    scope: str
    project_id: str | None = None
    takes_effect: str


class CaptureResponse(BaseModel):
    """What was saved, its id, its scope and when it takes effect, with the reply that says so."""

    record_id: str
    kind: str
    scope: str
    project_id: str | None = None
    takes_effect: str
    #: A campaign cycle's task instruction: its row in the campaign's control log, or ``None`` when
    #: the row couldn't be written, as the records API answers (§3.5). ``None`` for anything else.
    control_log_entry_id: str | None = None
    reply: ChatMessageDTO


class MessagingAgentDTO(BaseModel):
    """An agent with messaging enabled."""

    agent_id: str
    display_name: str
    description: str
    a2a_port: int
