"""
Error handling for SIP-0064 cycle API routes (§11).

T9: `details` is always present (nullable) for client stability.
"""

from __future__ import annotations

from fastapi import HTTPException

from squadops.api.errors import ErrorRow, mapped_error
from squadops.cycles.models import (
    ActiveProfileDeletionError,
    ArtifactNotFoundError,
    ArtifactUnreadableError,
    BaselineNotAllowedError,
    CycleError,
    CycleNotFoundError,
    DerivedProfileNotFoundError,
    DevelopmentConfigurationNotFoundError,
    GateAlreadyDecidedError,
    GoalSetNotFoundError,
    IllegalStateTransitionError,
    InheritedBaselineNotFoundError,
    PreflightRejectedError,
    ProfileNotFoundError,
    ProfileValidationError,
    ProjectIdTakenError,
    ProjectNotFoundError,
    ProjectNotReadyError,
    ProjectRegistryReadOnlyError,
    ProjectStateConflictError,
    RegistrationKeyConflictError,
    RunNotFoundError,
    RunTerminalError,
    StaleConfigurationRevisionError,
    StaleGoalSetRevisionError,
    StaleSourcePreconditionError,
    ValidationError,
)

_ERROR_MAP: list[ErrorRow] = [
    (ProjectNotFoundError, 404, "PROJECT_NOT_FOUND"),
    (CycleNotFoundError, 404, "CYCLE_NOT_FOUND"),
    (RunNotFoundError, 404, "RUN_NOT_FOUND"),
    (ArtifactNotFoundError, 404, "ARTIFACT_NOT_FOUND"),
    (ArtifactUnreadableError, 500, "ARTIFACT_UNREADABLE"),
    (ProfileNotFoundError, 404, "PROFILE_NOT_FOUND"),
    (DevelopmentConfigurationNotFoundError, 404, "DEVELOPMENT_CONFIGURATION_NOT_FOUND"),
    (InheritedBaselineNotFoundError, 404, "INHERITED_BASELINE_NOT_FOUND"),
    (DerivedProfileNotFoundError, 404, "DERIVED_PROFILE_NOT_FOUND"),
    (GoalSetNotFoundError, 404, "GOAL_SET_NOT_FOUND"),
    (ProjectNotReadyError, 409, "PROJECT_NOT_READY"),
    (ProjectRegistryReadOnlyError, 409, "PROJECT_REGISTRY_READ_ONLY"),
    (ProjectIdTakenError, 409, "PROJECT_ID_TAKEN"),
    (ProjectStateConflictError, 409, "PROJECT_STATE_CONFLICT"),
    (StaleConfigurationRevisionError, 409, "STALE_CONFIGURATION_REVISION"),
    (StaleGoalSetRevisionError, 409, "STALE_GOAL_SET_REVISION"),
    (StaleSourcePreconditionError, 409, "STALE_SOURCE_PRECONDITION"),
    (RegistrationKeyConflictError, 409, "IDEMPOTENCY_KEY_CONFLICT"),
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
    return mapped_error(e, _ERROR_MAP)


def handle_cycle_error(e: CycleError) -> HTTPException:
    """Map a domain error to an HTTPException with the standard error shape."""
    status, detail = cycle_error_envelope(e)
    return HTTPException(status_code=status, detail=detail)
