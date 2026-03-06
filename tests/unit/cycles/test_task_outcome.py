"""Tests for TaskOutcome and FailureClassification constants (SIP-0079 §7.3, §7.7)."""

import pytest

from squadops.cycles.task_outcome import FailureClassification, TaskOutcome

pytestmark = [pytest.mark.domain_orchestration]


class TestTaskOutcome:
    def test_all_six_constants_exist(self):
        expected = {
            "SUCCESS",
            "RETRYABLE_FAILURE",
            "SEMANTIC_FAILURE",
            "BLOCKED",
            "NEEDS_REPAIR",
            "NEEDS_REPLAN",
        }
        actual = {
            k for k, v in vars(TaskOutcome).items() if not k.startswith("_") and isinstance(v, str)
        }
        assert actual == expected

    def test_values_are_lowercase_strings(self):
        for attr in (
            "SUCCESS",
            "RETRYABLE_FAILURE",
            "SEMANTIC_FAILURE",
            "BLOCKED",
            "NEEDS_REPAIR",
            "NEEDS_REPLAN",
        ):
            val = getattr(TaskOutcome, attr)
            assert isinstance(val, str)
            assert val == val.lower()

    def test_no_duplicate_values(self):
        values = [
            v for k, v in vars(TaskOutcome).items() if not k.startswith("_") and isinstance(v, str)
        ]
        assert len(values) == len(set(values))


class TestFailureClassification:
    def test_all_five_constants_exist(self):
        expected = {
            "EXECUTION",
            "WORK_PRODUCT",
            "ALIGNMENT",
            "DECISION",
            "MODEL_LIMITATION",
        }
        actual = {
            k
            for k, v in vars(FailureClassification).items()
            if not k.startswith("_") and isinstance(v, str)
        }
        assert actual == expected

    def test_values_are_lowercase_strings(self):
        for attr in ("EXECUTION", "WORK_PRODUCT", "ALIGNMENT", "DECISION", "MODEL_LIMITATION"):
            val = getattr(FailureClassification, attr)
            assert isinstance(val, str)
            assert val == val.lower()

    def test_no_duplicate_values(self):
        values = [
            v
            for k, v in vars(FailureClassification).items()
            if not k.startswith("_") and isinstance(v, str)
        ]
        assert len(values) == len(set(values))
