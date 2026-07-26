"""OperationResult §4.4 coherence (SIP-0102, phase 102.1 slice a).

The roll-4 defect class — an environment failure consumed as an application
failure — must be unrepresentable in the result model, not merely discouraged.
"""

import pytest

from squadops.execution.models import (
    BuildResult,
    OperationName,
    OperationStatus,
    is_deliverable_failure,
)


def _result(**overrides) -> BuildResult:
    base = {
        "operation": OperationName.BUILD_FRONTEND,
        "workspace_revision_id": "rev1",
        "status": OperationStatus.SUCCEEDED,
        "ran": True,
    }
    return BuildResult(**{**base, **overrides})


class TestRanStatusCoherence:
    def test_not_ran_with_failed_status_is_unrepresentable(self):
        """Bug caught: the roll-4 conflation — an environment that never
        executed the operation recorded as a FAILED deliverable, which then
        takes `patch` and burns application correction budget."""
        with pytest.raises(ValueError, match="did not run"):
            _result(ran=False, status=OperationStatus.FAILED)

    def test_ran_with_not_run_status_is_unrepresentable(self):
        """Bug caught: the inverse laundering — an executed failure hidden
        under not_run, exempting a real defect from correction."""
        with pytest.raises(ValueError, match="cannot carry"):
            _result(ran=True, status=OperationStatus.NOT_RUN)

    def test_unknown_status_and_operation_are_rejected(self):
        """Bug caught: typo'd vocabulary silently entering evidence, breaking
        every downstream status-keyed rollup."""
        with pytest.raises(ValueError, match="unknown operation status"):
            _result(status="errored")
        with pytest.raises(ValueError, match="unknown operation"):
            _result(operation="run_shell")


class TestDeliverableFailure:
    @pytest.mark.parametrize(
        ("ran", "status", "expected"),
        [
            (True, OperationStatus.FAILED, True),
            (True, OperationStatus.SUCCEEDED, False),
            (False, OperationStatus.NOT_RUN, False),
        ],
        ids=["ran-and-failed", "ran-and-succeeded", "environment-unavailable"],
    )
    def test_only_executed_failures_are_deliverable_failures(self, ran, status, expected):
        """Bug caught: NOT_RUN counted as a deliverable failure — the exact
        classification §4.4's ran=False semantics exist to forbid."""
        result = _result(ran=ran, status=status)
        assert is_deliverable_failure(result) is expected
