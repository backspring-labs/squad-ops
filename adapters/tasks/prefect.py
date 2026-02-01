"""Prefect adapter stub.

Full implementation in 0.8.8.
Part of SIP-0.8.7 Infrastructure Ports Migration.

IMPORTANT: This module MUST NOT import Prefect at module level.
Prefect is not a required dependency in 0.8.7.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

from squadops.ports.tasks.registry import TaskRegistryPort
from squadops.tasks.types import Task, TaskState

# Only import Prefect for type hints (not at runtime)
if TYPE_CHECKING:
    pass  # Future: from prefect import ... for type hints only


class PrefectTaskAdapter(TaskRegistryPort):
    """Stub adapter for Prefect. Full implementation in 0.8.8.

    All methods raise NotImplementedError. This stub exists to:
    1. Reserve the adapter slot in the factory
    2. Allow type checking without runtime Prefect dependency
    3. Document the deferred scope
    """

    def __init__(self, **config):
        """Initialize stub adapter.

        Args:
            **config: Ignored in stub
        """
        pass

    async def create(self, task: Task) -> str:
        """Create a new task.

        Raises:
            NotImplementedError: PrefectTaskAdapter deferred to 0.8.8
        """
        raise NotImplementedError("PrefectTaskAdapter deferred to 0.8.8")

    async def get(self, task_id: str) -> Task | None:
        """Get a task by ID.

        Raises:
            NotImplementedError: PrefectTaskAdapter deferred to 0.8.8
        """
        raise NotImplementedError("PrefectTaskAdapter deferred to 0.8.8")

    async def update_status(
        self,
        task_id: str,
        status: TaskState,
        result: dict[str, Any] | None = None,
    ) -> None:
        """Update task status.

        Raises:
            NotImplementedError: PrefectTaskAdapter deferred to 0.8.8
        """
        raise NotImplementedError("PrefectTaskAdapter deferred to 0.8.8")

    async def list_pending(self, agent_id: str | None = None) -> list[Task]:
        """List pending tasks.

        Raises:
            NotImplementedError: PrefectTaskAdapter deferred to 0.8.8
        """
        raise NotImplementedError("PrefectTaskAdapter deferred to 0.8.8")
