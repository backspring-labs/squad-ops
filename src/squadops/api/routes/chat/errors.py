"""Error handling for SIP-0085 chat API routes.

Follows the same centralized pattern as cycles/errors.py.
T9-equivalent: `details` is always present (nullable) for client stability.
"""

from __future__ import annotations

from fastapi import HTTPException

from squadops.api.errors import ErrorRow, mapped_error
from squadops.comms.models import (
    AgentNotFoundError,
    AgentNotMessagingEnabledError,
    ChatError,
    SessionNotFoundError,
)

_ERROR_MAP: list[ErrorRow] = [
    (SessionNotFoundError, 404, "SESSION_NOT_FOUND"),
    (AgentNotFoundError, 404, "AGENT_NOT_FOUND"),
    (AgentNotMessagingEnabledError, 400, "MESSAGING_NOT_ENABLED"),
]


def chat_error_envelope(e: ChatError) -> tuple[int, dict]:
    """The (status, detail) envelope for a domain error — one table, read by the
    app-level exception handler (#576) and by the HTTPException helper below."""
    return mapped_error(e, _ERROR_MAP)


def handle_chat_error(e: ChatError) -> HTTPException:
    """Map a domain error to an HTTPException with the standard error shape."""
    status, detail = chat_error_envelope(e)
    return HTTPException(status_code=status, detail=detail)
