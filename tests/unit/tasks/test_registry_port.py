"""Unit tests for Tasks registry port interface."""

import pytest

from squadops.ports.tasks.registry import TaskRegistryPort


class TestTaskRegistryPort:
    """Tests for TaskRegistryPort interface."""

    def test_cannot_instantiate_directly(self):
        """TaskRegistryPort is abstract and cannot be instantiated."""
        with pytest.raises(TypeError):
            TaskRegistryPort()  # type: ignore

    def test_has_create_method(self):
        assert hasattr(TaskRegistryPort, "create")

    def test_has_get_method(self):
        assert hasattr(TaskRegistryPort, "get")

    def test_has_update_status_method(self):
        assert hasattr(TaskRegistryPort, "update_status")

    def test_has_list_pending_method(self):
        assert hasattr(TaskRegistryPort, "list_pending")
