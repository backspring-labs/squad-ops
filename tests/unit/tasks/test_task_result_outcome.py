"""Tests for TaskResult outcome_class field (SIP-0079)."""

import pytest

from squadops.tasks.models import TaskResult

pytestmark = [pytest.mark.unit]


class TestTaskResultOutcomeClass:
    def test_outcome_class_defaults_none(self):
        tr = TaskResult(task_id="t1", status="SUCCEEDED")
        assert tr.outcome_class is None

    def test_outcome_class_set(self):
        tr = TaskResult(task_id="t1", status="FAILED", outcome_class="retryable_failure")
        assert tr.outcome_class == "retryable_failure"

    def test_to_dict_preserves_outcome_class(self):
        tr = TaskResult(task_id="t1", status="SUCCEEDED", outcome_class="success")
        d = tr.to_dict()
        assert d["outcome_class"] == "success"

    def test_from_dict_round_trip(self):
        original = TaskResult(
            task_id="t1",
            status="FAILED",
            error="timeout",
            outcome_class="retryable_failure",
        )
        d = original.to_dict()
        restored = TaskResult.from_dict(d)
        assert restored == original
        assert restored.outcome_class == "retryable_failure"

    def test_backward_compat_from_dict_without_outcome_class(self):
        """Pre-SIP-0079 dicts without outcome_class still deserialize."""
        d = {"task_id": "t1", "status": "SUCCEEDED"}
        tr = TaskResult.from_dict(d)
        assert tr.outcome_class is None
