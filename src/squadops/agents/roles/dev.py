"""DevAgent - Code generation and implementation.

The Developer agent handles code generation, modifications, and testing.
Part of SIP-0.8.8 Phase 3.
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from squadops.agents.base import BaseAgent
from squadops.agents.exceptions import SkillNotFoundError
from squadops.agents.skills.context import SkillContext
from squadops.tasks.models import TaskEnvelope, TaskResult

if TYPE_CHECKING:
    from squadops.agents.skills.registry import SkillRegistry

logger = logging.getLogger(__name__)


# Task type to skill ID mapping for Dev agent
TASK_TYPE_SKILL_MAP = {
    "generate": "code_generation",
    "code_generate": "code_generation",
    "modify": "code_modification",
    "code_modify": "code_modification",
    "test": "test_writing",
    "write_test": "test_writing",
    "fix": "bug_fixing",
    "bug_fix": "bug_fixing",
    "refactor": "refactoring",
}


class DevAgent(BaseAgent):
    """Developer agent for code generation and implementation.

    Responsible for:
    - Code generation from requirements
    - Code modification and updates
    - Test writing
    - Bug fixing
    - Refactoring
    """

    ROLE_ID = "dev"
    DEFAULT_SKILLS = (
        "code_generation",
        "code_modification",
        "test_writing",
        "bug_fixing",
        "refactoring",
    )

    def __init__(
        self,
        *,
        agent_id: str,
        skill_registry: SkillRegistry | None = None,
        **ports: Any,
    ) -> None:
        """Initialize Dev agent.

        Args:
            agent_id: Unique agent identifier
            skill_registry: Registry for skill execution
            **ports: Port dependencies (llm, memory, etc.)
        """
        super().__init__(
            agent_id=agent_id,
            role_id=self.ROLE_ID,
            skill_registry=skill_registry,
            **ports,
        )
        logger.info(
            "dev_agent_initialized",
            extra={"agent_id": agent_id, "skills": self.DEFAULT_SKILLS},
        )

    async def handle_task(self, envelope: TaskEnvelope) -> TaskResult:
        """Process incoming task by routing to appropriate skill.

        Args:
            envelope: Task envelope with task details

        Returns:
            TaskResult with execution outcome
        """
        logger.info(
            "dev_handling_task",
            extra={
                "agent_id": self.agent_id,
                "task_id": envelope.task_id,
                "task_type": envelope.task_type,
            },
        )

        # Select skill based on task type
        skill_id = self._select_skill(envelope.task_type)

        # Build skill context
        context = SkillContext.from_agent(
            agent_id=self.agent_id,
            role_id=self.role_id,
            task_id=envelope.task_id,
            cycle_id=envelope.cycle_id,
            ports=self.ports,
        )

        # Execute skill if registry available
        if self._skill_registry is None:
            logger.warning(
                "skill_registry_not_available",
                extra={"agent_id": self.agent_id, "task_id": envelope.task_id},
            )
            return TaskResult(
                task_id=envelope.task_id,
                status="failed",
                error="Skill registry not available",
            )

        # Convert envelope inputs to skill inputs
        inputs = self._map_task_to_inputs(envelope)

        # Execute via registry
        result = await self._skill_registry.execute(skill_id, context, inputs)

        # Convert skill result to task result
        return TaskResult(
            task_id=envelope.task_id,
            status="completed" if result.success else "failed",
            outputs=result.outputs,
            error=result.error,
        )

    def _select_skill(self, task_type: str) -> str:
        """Select skill ID based on task type.

        Args:
            task_type: The task type from envelope

        Returns:
            Skill ID to execute

        Raises:
            SkillNotFoundError: If no skill handles this task type
        """
        skill_id = TASK_TYPE_SKILL_MAP.get(task_type)
        if skill_id is None:
            raise SkillNotFoundError(
                f"No skill registered for task type: {task_type}"
            )
        return skill_id

    def _map_task_to_inputs(self, envelope: TaskEnvelope) -> dict[str, Any]:
        """Convert TaskEnvelope to skill-specific inputs.

        Args:
            envelope: Task envelope

        Returns:
            Dict of inputs for skill execution
        """
        # Start with envelope inputs
        inputs = dict(envelope.inputs)

        # Add envelope metadata that skills might need
        inputs["_task_id"] = envelope.task_id
        inputs["_task_type"] = envelope.task_type
        inputs["_cycle_id"] = envelope.cycle_id
        inputs["_project_id"] = envelope.project_id

        return inputs
