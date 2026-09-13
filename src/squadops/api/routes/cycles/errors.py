"""
Error handling for SIP-0064 cycle API routes (§11).

T9: `details` is always present (nullable) for client stability.
"""

from __future__ import annotations

from fastapi import HTTPException

from squadops.cycles.models import (
    ActiveProfileDeletionError,
    ArtifactNotFoundError,
    BaselineNotAllowedError,
    CycleError,
    CycleNotFoundError,
    GateAlreadyDecidedError,
    IllegalStateTransitionError,
    PreflightRejectedError,
    ProfileNotFoundError,
    ProfileValidationError,
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
    (ProfileNotFoundError, 404, "PROFILE_NOT_FOUND"),
    (IllegalStateTransitionError, 409, "ILLEGAL_STATE_TRANSITION"),
    (GateAlreadyDecidedError, 409, "GATE_ALREADY_DECIDED"),
    (RunTerminalError, 409, "RUN_TERMINAL"),
    (BaselineNotAllowedError, 409, "BASELINE_NOT_ALLOWED"),
    (ActiveProfileDeletionError, 409, "ACTIVE_PROFILE_DELETION"),
    (ProfileValidationError, 422, "PROFILE_VALIDATION_ERROR"),
    (PreflightRejectedError, 422, "PREFLIGHT_REJECTED"),
    (ValidationError, 422, "VALIDATION_ERROR"),
]


def cycle_error_envelope(e: CycleError) -> tuple[int, dict]:
    """The (status, detail) envelope for a domain error — one table, read by the
    app-level exception handler (#576) and by the HTTPException helper below."""
    for exc_type, status, code in _ERROR_MAP:
        if isinstance(e, exc_type):
            return status, {"error": {"code": code, "message": str(e), "details": None}}
    return 500, {"error": {"code": "INTERNAL_ERROR", "message": str(e), "details": None}}


def handle_cycle_error(e: CycleError) -> HTTPException:
    """Map a domain error to an HTTPException with the standard error shape."""
    status, detail = cycle_error_envelope(e)
    return HTTPException(status_code=status, detail=detail)
