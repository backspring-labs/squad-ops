"""Tasks registry port interface.

Abstract base class for task registry adapters.
Part of SIP-0.8.7 Infrastructure Ports Migration.
"""
from abc import ABC, abstractmethod
from typing import Any

from squadops.tasks.types import Task, TaskState


class TaskRegistryPort(ABC):
    """Port interface for task registry operations.

    Adapters implement task persistence and state management.
    Uses legacy Task (TaskEnvelope) via compatibility bridge for 0.8.7.
    Full migration to frozen dataclasses in 0.8.8.
    """

    @abstractmethod
    async def create(self, task: Task) -> str:
        """Create a new task.

        Args:
            task: Task to create (legacy Task model via types.py bridge)

        Returns:
            Task ID of the created task

        Raises:
            TaskValidationError: Invalid task data
            TaskError: Failed to create task
        """
        ...

    @abstractmethod
    async def get(self, task_id: str) -> Task | None:
        """Get a task by ID.

        Args:
            task_id: ID of the task to retrieve

        Returns:
            Task if found, None otherwise
        """
        ...

    @abstractmethod
    async def update_status(
        self,
        task_id: str,
        status: TaskState,
        result: dict[str, Any] | None = None,
    ) -> None:
        """Update task status.

        Args:
            task_id: ID of the task to update
            status: New task state
            result: Optional result data

        Raises:
            TaskNotFoundError: Task not found
            TaskStateError: Invalid state transition
        """
        ...

    @abstractmethod
    async def list_pending(self, agent_id: str | None = None) -> list[Task]:
        """List pending tasks.

        Args:
            agent_id: Optional filter by target agent

        Returns:
            List of pending tasks
        """
        ...
