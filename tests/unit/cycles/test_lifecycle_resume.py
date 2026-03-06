"""Tests for SIP-0079 FAILED → RUNNING lifecycle transition."""

import pytest

from squadops.cycles.lifecycle import validate_run_transition
from squadops.cycles.models import IllegalStateTransitionError, RunStatus

pytestmark = [pytest.mark.domain_orchestration]


class TestResumeFromFailed:
    def test_failed_to_running_valid(self):
        """SIP-0079: resume_from_failed allows FAILED → RUNNING."""
        validate_run_transition(RunStatus.FAILED, RunStatus.RUNNING)

    def test_paused_to_running_still_valid(self):
        """Regression: existing PAUSED → RUNNING unchanged."""
        validate_run_transition(RunStatus.PAUSED, RunStatus.RUNNING)

    def test_completed_to_running_invalid(self):
        with pytest.raises(IllegalStateTransitionError):
            validate_run_transition(RunStatus.COMPLETED, RunStatus.RUNNING)

    def test_cancelled_to_running_invalid(self):
        with pytest.raises(IllegalStateTransitionError):
            validate_run_transition(RunStatus.CANCELLED, RunStatus.RUNNING)

    def test_failed_to_completed_still_invalid(self):
        """FAILED only gains RUNNING as a target, nothing else."""
        with pytest.raises(IllegalStateTransitionError):
            validate_run_transition(RunStatus.FAILED, RunStatus.COMPLETED)

    def test_failed_to_cancelled_still_invalid(self):
        with pytest.raises(IllegalStateTransitionError):
            validate_run_transition(RunStatus.FAILED, RunStatus.CANCELLED)
