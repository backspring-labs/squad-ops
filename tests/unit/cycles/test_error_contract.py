"""
Tests for SIP-0064 error contract (§11).

T9: `details` is always present (nullable) for client stability.
"""

import pytest

from squadops.api.routes.cycles.errors import handle_cycle_error
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

pytestmark = [pytest.mark.domain_orchestration]


class TestErrorContract:
    @pytest.mark.parametrize(
        "exc_cls,expected_status,expected_code",
        [
            (ProjectNotFoundError, 404, "PROJECT_NOT_FOUND"),
            (CycleNotFoundError, 404, "CYCLE_NOT_FOUND"),
            (RunNotFoundError, 404, "RUN_NOT_FOUND"),
            (ArtifactNotFoundError, 404, "ARTIFACT_NOT_FOUND"),
            (IllegalStateTransitionError, 409, "ILLEGAL_STATE_TRANSITION"),
            (GateAlreadyDecidedError, 409, "GATE_ALREADY_DECIDED"),
            (RunTerminalError, 409, "RUN_TERMINAL"),
            (BaselineNotAllowedError, 409, "BASELINE_NOT_ALLOWED"),
            (ValidationError, 422, "VALIDATION_ERROR"),
        ],
    )
    def test_error_maps_to_correct_status(
        self, exc_cls, expected_status, expected_code
    ):
        exc = exc_cls("test message")
        http_exc = handle_cycle_error(exc)
        assert http_exc.status_code == expected_status
        assert http_exc.detail["error"]["code"] == expected_code
        assert http_exc.detail["error"]["message"] == "test message"

    @pytest.mark.parametrize(
        "exc_cls",
        [
            ProjectNotFoundError,
            CycleNotFoundError,
            RunNotFoundError,
            ArtifactNotFoundError,
            IllegalStateTransitionError,
            GateAlreadyDecidedError,
            RunTerminalError,
            BaselineNotAllowedError,
            ValidationError,
        ],
    )
    def test_details_always_present_and_null(self, exc_cls):
        """T9: details field is always present (nullable), not absent."""
        exc = exc_cls("test")
        http_exc = handle_cycle_error(exc)
        assert "details" in http_exc.detail["error"]
        assert http_exc.detail["error"]["details"] is None

    def test_unknown_cycle_error_maps_to_500(self):
        exc = CycleError("generic error")
        http_exc = handle_cycle_error(exc)
        assert http_exc.status_code == 500
        assert http_exc.detail["error"]["code"] == "INTERNAL_ERROR"
        assert http_exc.detail["error"]["details"] is None
