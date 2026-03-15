"""Error handling for SIP-0085 chat API routes.

Follows the same centralized pattern as cycles/errors.py.
T9-equivalent: `details` is always present (nullable) for client stability.
"""

from __future__ import annotations

from fastapi import HTTPException

from squadops.comms.models import (
    AgentNotFoundError,
    AgentNotMessagingEnabledError,
    ChatError,
    SessionNotFoundError,
)

_ERROR_MAP: list[tuple[type, int, str]] = [
    (SessionNotFoundError, 404, "SESSION_NOT_FOUND"),
    (AgentNotFoundError, 404, "AGENT_NOT_FOUND"),
    (AgentNotMessagingEnabledError, 400, "MESSAGING_NOT_ENABLED"),
]


def handle_chat_error(e: ChatError) -> HTTPException:
    """Map a ChatError to an HTTPException with standard error shape."""
    for exc_type, status, code in _ERROR_MAP:
        if isinstance(e, exc_type):
            return HTTPException(
                status_code=status,
                detail={"error": {"code": code, "message": str(e), "details": None}},
            )
    return HTTPException(
        status_code=500,
        detail={"error": {"code": "INTERNAL_ERROR", "message": str(e), "details": None}},
    )
