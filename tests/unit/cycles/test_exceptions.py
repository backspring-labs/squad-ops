"""
Tests for SIP-0064 domain exceptions.
"""

import pytest

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

_EXCEPTION_CLASSES = [
    CycleNotFoundError,
    RunNotFoundError,
    IllegalStateTransitionError,
    GateAlreadyDecidedError,
    RunTerminalError,
    ProjectNotFoundError,
    ArtifactNotFoundError,
    BaselineNotAllowedError,
    ValidationError,
]


class TestExceptionHierarchy:
    @pytest.mark.parametrize("exc_cls", _EXCEPTION_CLASSES)
    def test_can_instantiate_with_message(self, exc_cls):
        e = exc_cls("test message")
        assert str(e) == "test message"

    @pytest.mark.parametrize("exc_cls", _EXCEPTION_CLASSES)
    def test_can_raise_and_catch_as_cycle_error(self, exc_cls):
        with pytest.raises(CycleError):
            raise exc_cls("test")

    def test_cycle_error_is_base(self):
        assert issubclass(CycleError, Exception)
        e = CycleError("base error")
        assert str(e) == "base error"
