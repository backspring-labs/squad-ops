"""
Driven port for capability execution abstraction.

This interface defines the contract for executing capability tasks,
allowing the domain logic to remain isolated from the specific
execution mechanism (ACI queue, Prefect, etc.).
"""

from abc import ABC, abstractmethod
from typing import Any

# Import ACI models from v0_legacy (path added via pytest pythonpath)
# [DEFERRED] Migrate TaskEnvelope/TaskResult to canonical location in future SIP
from agents.tasks.models import TaskEnvelope, TaskResult


class CapabilityExecutor(ABC):
    """
    Abstract contract for executing capability tasks.

    Implementations handle the actual execution mechanism (queue dispatch,
    workflow orchestration, etc.) while the domain layer works against
    this abstraction.
    """

    @property
    @abstractmethod
    def executor_id(self) -> str:
        """
        Unique identifier for this executor.

        Used for executor resolution and logging.

        Returns:
            Executor identifier string
        """
        pass

    @abstractmethod
    async def execute(
        self,
        envelope: TaskEnvelope,
        timeout_seconds: int | None = None,
    ) -> TaskResult:
        """
        Execute a task and await its result.

        The executor is responsible for:
        1. Dispatching the task envelope to the appropriate agent
        2. Awaiting the task result
        3. Handling timeouts

        Args:
            envelope: ACI TaskEnvelope with task details
            timeout_seconds: Maximum time to wait for result (None = use default)

        Returns:
            TaskResult with execution outcome

        Raises:
            TimeoutError: If execution exceeds timeout
            ExecutorError: If execution fails for other reasons
        """
        pass

    @abstractmethod
    async def health(self) -> dict[str, Any]:
        """
        Check the health status of the executor.

        Returns:
            Dictionary with health status information
            (e.g., {"status": "healthy", "queue_connected": True})
        """
        pass

    @abstractmethod
    def can_execute(self, capability_id: str, agent_role: str) -> bool:
        """
        Check if this executor can execute a given capability for a role.

        Used during executor resolution to determine if this executor
        is suitable for a specific task.

        Args:
            capability_id: Capability contract identifier
            agent_role: Target agent role

        Returns:
            True if this executor can handle the capability
        """
        pass
