"""API Service layer for task management.

Provides a high-level service interface for the API layer,
coordinating between DTOs, orchestration, and domain models.

Part of SIP-0.8.8 Phase 6.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from squadops.api.mapping import dto_to_envelope, envelope_to_response, result_to_dto
from squadops.api.schemas import (
    TaskRequestDTO,
    TaskResponseDTO,
    TaskResultDTO,
    TaskStatusDTO,
)

if TYPE_CHECKING:
    from squadops.orchestration.orchestrator import AgentOrchestrator

logger = logging.getLogger(__name__)


class TaskService:
    """Service for task management operations.

    Bridges the API layer with the orchestration layer.
    Handles DTO mapping, validation, and response formatting.
    """

    def __init__(self, orchestrator: AgentOrchestrator) -> None:
        """Initialize with orchestrator.

        Args:
            orchestrator: AgentOrchestrator for task execution
        """
        self._orchestrator = orchestrator

    async def submit_task(
        self,
        request: TaskRequestDTO,
        cycle_id: str | None = None,
    ) -> TaskResponseDTO:
        """Submit a task for execution.

        Args:
            request: Task request DTO
            cycle_id: Optional cycle ID

        Returns:
            Task response DTO with task ID and status
        """
        # Map DTO to internal envelope
        envelope = dto_to_envelope(request, cycle_id=cycle_id)

        logger.info(
            "task_submitted_via_api",
            extra={
                "task_id": envelope.task_id,
                "task_type": envelope.task_type,
            },
        )

        # Submit to orchestrator
        result = await self._orchestrator.submit_task(envelope)

        # Return response
        return envelope_to_response(envelope)

    async def execute_task(
        self,
        request: TaskRequestDTO,
        timeout_seconds: int | None = None,
    ) -> TaskResultDTO:
        """Execute a task synchronously and return result.

        Args:
            request: Task request DTO
            timeout_seconds: Optional timeout

        Returns:
            Task result DTO with execution outcome
        """
        envelope = dto_to_envelope(request)

        logger.info(
            "task_executed_via_api",
            extra={
                "task_id": envelope.task_id,
                "task_type": envelope.task_type,
            },
        )

        result = await self._orchestrator.submit_task(envelope, timeout_seconds)

        return result_to_dto(result)

    async def get_task_status(self, task_id: str) -> TaskStatusDTO | None:
        """Get status of a task.

        Args:
            task_id: Task ID to query

        Returns:
            Task status DTO or None if not found
        """
        # Check active tasks
        active = self._orchestrator.get_active_tasks()
        if task_id in active:
            return TaskStatusDTO(
                task_id=task_id,
                status="RUNNING",
            )

        # Task not found in active - could extend with history lookup
        return None

    def list_capabilities(self, role: str | None = None) -> list[str]:
        """List available capabilities.

        Args:
            role: Optional role filter

        Returns:
            List of capability IDs
        """
        return self._orchestrator.get_available_capabilities(role)

    async def health(self) -> dict[str, Any]:
        """Get service health status.

        Returns:
            Health status dictionary
        """
        orchestrator_health = await self._orchestrator.health_check()

        return {
            "status": "healthy" if orchestrator_health["status"] == "healthy" else "unhealthy",
            "orchestrator": orchestrator_health,
            "timestamp": datetime.now(UTC).isoformat(),
        }


class AgentService:
    """Service for agent management operations.

    Provides agent registration and status through the API layer.
    """

    def __init__(self, orchestrator: AgentOrchestrator) -> None:
        """Initialize with orchestrator.

        Args:
            orchestrator: AgentOrchestrator for agent management
        """
        self._orchestrator = orchestrator

    def list_agents(self) -> list[dict[str, Any]]:
        """List all registered agents.

        Returns:
            List of agent information dictionaries
        """
        states = self._orchestrator.get_agent_states()
        return [
            {
                "agent_id": agent_id,
                **state,
            }
            for agent_id, state in states.items()
        ]

    def get_agent(self, agent_id: str) -> dict[str, Any] | None:
        """Get information about a specific agent.

        Args:
            agent_id: Agent ID to query

        Returns:
            Agent information or None if not found
        """
        states = self._orchestrator.get_agent_states()
        if agent_id in states:
            return {
                "agent_id": agent_id,
                **states[agent_id],
            }
        return None

    def list_capabilities_for_agent(self, agent_id: str) -> list[str]:
        """List capabilities available to an agent.

        Args:
            agent_id: Agent ID

        Returns:
            List of capability IDs
        """
        states = self._orchestrator.get_agent_states()
        if agent_id not in states:
            return []

        role = states[agent_id].get("role", "")
        return self._orchestrator.get_available_capabilities(role)
