"""Unit tests for Tasks domain models."""

import pytest

from squadops.tasks.models import TaskIdentity


class TestTaskIdentity:
    """Tests for TaskIdentity dataclass."""

    def test_identity_is_frozen(self):
        identity = TaskIdentity(
            task_id="task-1",
            task_type="test",
            source_agent="agent-1",
        )
        with pytest.raises(AttributeError):
            identity.task_id = "modified"  # type: ignore
