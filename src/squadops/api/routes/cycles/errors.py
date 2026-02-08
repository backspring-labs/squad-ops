"""
Error handling for SIP-0064 cycle API routes (§11).

T9: `details` is always present (nullable) for client stability.
"""

from __future__ import annotations

from fastapi import HTTPException

from squadops.cycles.models import (
    ArtifactNotFoundError,
    BaselineNotAllowedError,
    CycleError,
    CycleNotFoundError,
    GateAlreadyDecidedError,
    IllegalStateTransitionError,
    ProjectNotFoundError,
    RunNotFoundError,
    RunTerminalError,
    ValidationError,
)

_ERROR_MAP: list[tuple[type, int, str]] = [
    (ProjectNotFoundError, 404, "PROJECT_NOT_FOUND"),
    (CycleNotFoundError, 404, "CYCLE_NOT_FOUND"),
    (RunNotFoundError, 404, "RUN_NOT_FOUND"),
    (ArtifactNotFoundError, 404, "ARTIFACT_NOT_FOUND"),
    (IllegalStateTransitionError, 409, "ILLEGAL_STATE_TRANSITION"),
    (GateAlreadyDecidedError, 409, "GATE_ALREADY_DECIDED"),
    (RunTerminalError, 409, "RUN_TERMINAL"),
    (BaselineNotAllowedError, 409, "BASELINE_NOT_ALLOWED"),
    (ValidationError, 422, "VALIDATION_ERROR"),
]


def handle_cycle_error(e: CycleError) -> HTTPException:
    """Map a CycleError to an HTTPException with standard error shape."""
    for exc_type, status, code in _ERROR_MAP:
        if isinstance(e, exc_type):
            return HTTPException(
                status_code=status,
                detail={
                    "error": {"code": code, "message": str(e), "details": None}
                },
            )
    return HTTPException(
        status_code=500,
        detail={
            "error": {"code": "INTERNAL_ERROR", "message": str(e), "details": None}
        },
    )
