"""ExecutionContext for capability handler execution.

Provides handlers with access to skills and ports while
tracking all executions for evidence aggregation.

Part of SIP-0.8.8 Phase 5.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from squadops.agents.skills.context import SkillContext
from squadops.agents.skills.registry import SkillRegistry

if TYPE_CHECKING:
    from squadops.agents.base import PortsBundle
    from squadops.agents.skills.base import SkillResult
    from squadops.telemetry.models import CorrelationContext

logger = logging.getLogger(__name__)


@dataclass
class SkillExecutionRecord:
    """Record of a skill execution for evidence.

    Attributes:
        skill_name: Name of the executed skill
        inputs: Inputs provided to the skill
        outputs: Outputs from the skill
        success: Whether execution succeeded
        duration_ms: Execution duration
        error: Error message if failed
    """

    skill_name: str
    inputs: dict[str, Any]
    outputs: dict[str, Any]
    success: bool
    duration_ms: float
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for evidence serialization."""
        return {
            "skill_name": self.skill_name,
            "inputs_keys": list(self.inputs.keys()),
            "outputs_keys": list(self.outputs.keys()),
            "success": self.success,
            "duration_ms": self.duration_ms,
            "error": self.error,
        }


@dataclass
class ExecutionContext:
    """Context for capability handler execution.

    Provides handlers with:
    - Access to SkillRegistry for skill execution
    - PortsBundle for creating SkillContext
    - Task/cycle metadata
    - Evidence aggregation from skill executions

    Attributes:
        agent_id: ID of the executing agent
        role_id: Role of the agent
        task_id: Current task ID
        cycle_id: Current cycle ID
        ports: PortsBundle for port access
        skill_registry: Registry for skill execution
    """

    agent_id: str
    role_id: str
    task_id: str
    cycle_id: str
    ports: PortsBundle
    skill_registry: SkillRegistry
    correlation_context: CorrelationContext | None = None
    _skill_executions: list[SkillExecutionRecord] = field(default_factory=list)

    @classmethod
    def create(
        cls,
        agent_id: str,
        role_id: str,
        task_id: str,
        cycle_id: str,
        ports: PortsBundle,
        skill_registry: SkillRegistry,
        correlation_context: CorrelationContext | None = None,
    ) -> ExecutionContext:
        """Factory method for creating execution context.

        Args:
            agent_id: Agent instance ID
            role_id: Agent role ID
            task_id: Current task ID
            cycle_id: Current cycle ID
            ports: PortsBundle from agent
            skill_registry: SkillRegistry with available skills
            correlation_context: Optional LangFuse correlation context

        Returns:
            ExecutionContext instance
        """
        return cls(
            agent_id=agent_id,
            role_id=role_id,
            task_id=task_id,
            cycle_id=cycle_id,
            ports=ports,
            skill_registry=skill_registry,
            correlation_context=correlation_context,
        )

    def create_skill_context(self) -> SkillContext:
        """Create a SkillContext for skill execution.

        Returns:
            SkillContext with current task/cycle metadata
        """
        return SkillContext.from_agent(
            agent_id=self.agent_id,
            role_id=self.role_id,
            task_id=self.task_id,
            cycle_id=self.cycle_id,
            ports=self.ports,
        )

    async def execute_skill(
        self,
        skill_name: str,
        inputs: dict[str, Any],
    ) -> SkillResult:
        """Execute a skill and record evidence.

        Args:
            skill_name: Name of skill to execute
            inputs: Inputs for the skill

        Returns:
            SkillResult from execution

        Raises:
            SkillNotFoundError: If skill not registered
            SkillContractViolation: If skill execution fails contract
        """
        context = self.create_skill_context()

        logger.debug(
            "executing_skill",
            extra={
                "skill_name": skill_name,
                "task_id": self.task_id,
                "agent_id": self.agent_id,
            },
        )

        result = await self.skill_registry.execute(skill_name, context, inputs)

        # Record execution for evidence
        record = SkillExecutionRecord(
            skill_name=skill_name,
            inputs=inputs,
            outputs=result.outputs,
            success=result.success,
            duration_ms=result.evidence.duration_ms,
            error=result.error,
        )
        self._skill_executions.append(record)

        logger.debug(
            "skill_executed",
            extra={
                "skill_name": skill_name,
                "success": result.success,
                "duration_ms": result.evidence.duration_ms,
            },
        )

        return result

    def get_skill_executions(self) -> list[dict[str, Any]]:
        """Get all skill execution records as dicts.

        Returns:
            List of execution record dictionaries
        """
        return [r.to_dict() for r in self._skill_executions]

    def get_total_duration_ms(self) -> float:
        """Get total duration of all skill executions.

        Returns:
            Sum of all execution durations in milliseconds
        """
        return sum(r.duration_ms for r in self._skill_executions)

    def clear_executions(self) -> None:
        """Clear execution records (for testing)."""
        self._skill_executions.clear()

    def has_skill(self, skill_name: str) -> bool:
        """Check if a skill is available.

        Args:
            skill_name: Skill to check

        Returns:
            True if skill is registered
        """
        return skill_name in self.skill_registry._skills
