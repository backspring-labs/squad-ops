"""Unit tests for Tasks domain models."""

import pytest

from squadops.tasks.models import TaskIdentity


class TestTaskIdentity:
    """Tests for TaskIdentity dataclass."""

    def test_minimal_identity(self):
        identity = TaskIdentity(
            task_id="task-1",
            task_type="test",
            source_agent="agent-1",
        )
        assert identity.task_id == "task-1"
        assert identity.task_type == "test"
        assert identity.source_agent == "agent-1"
        assert identity.target_agent is None
        assert identity.correlation_id is None
        assert identity.causation_id is None
        assert identity.trace_id is None

    def test_full_identity(self):
        identity = TaskIdentity(
            task_id="task-1",
            task_type="test",
            source_agent="agent-1",
            target_agent="agent-2",
            correlation_id="corr-1",
            causation_id="cause-1",
            trace_id="trace-1",
        )
        assert identity.target_agent == "agent-2"
        assert identity.correlation_id == "corr-1"
        assert identity.causation_id == "cause-1"
        assert identity.trace_id == "trace-1"

    def test_identity_is_frozen(self):
        identity = TaskIdentity(
            task_id="task-1",
            task_type="test",
            source_agent="agent-1",
        )
        with pytest.raises(AttributeError):
            identity.task_id = "modified"  # type: ignore
