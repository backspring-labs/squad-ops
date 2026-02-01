"""Task Delegation skill - delegate tasks to agents.

Lead agent skill for task assignment.
Part of SIP-0.8.8 Phase 4.
"""
from __future__ import annotations

import hashlib
import json
import time
from typing import TYPE_CHECKING, Any

from squadops.agents.skills.base import ExecutionEvidence, Skill, SkillResult

if TYPE_CHECKING:
    from squadops.agents.skills.context import SkillContext


# Role capabilities for delegation routing
ROLE_CAPABILITIES = {
    "dev": ["code_generate", "code_modify", "test", "fix", "refactor"],
    "qa": ["test_design", "test_execute", "validate", "bug_report"],
    "strat": ["strategy", "architecture", "requirements"],
    "data": ["analyze_data", "metrics", "report"],
}


class TaskDelegationSkill(Skill):
    """Skill for delegating tasks to appropriate agents.

    Inputs:
        task_type: str - Type of task to delegate
        task_description: str - Task description
        priority: str (optional) - Task priority (low/medium/high)

    Outputs:
        target_role: str - Recommended agent role
        delegation_reason: str - Reason for the delegation
        task_envelope: dict - Prepared task envelope for queueing
    """

    @property
    def name(self) -> str:
        return "task_delegation"

    @property
    def description(self) -> str:
        return "Delegate a task to the appropriate agent role"

    @property
    def required_capabilities(self) -> tuple[str, ...]:
        return ("queue",)

    def validate_inputs(self, inputs: dict[str, Any]) -> list[str]:
        """Validate delegation inputs."""
        errors = []
        if "task_type" not in inputs:
            errors.append("'task_type' is required")
        if "task_description" not in inputs:
            errors.append("'task_description' is required")
        return errors

    async def execute(
        self,
        context: SkillContext,
        inputs: dict[str, Any],
    ) -> SkillResult:
        """Execute task delegation.

        Args:
            context: SkillContext providing port access
            inputs: Must contain 'task_type' and 'task_description'

        Returns:
            SkillResult with delegation details
        """
        start_time = time.perf_counter()

        task_type = inputs["task_type"]
        task_description = inputs["task_description"]
        priority = inputs.get("priority", "medium")

        try:
            # Determine target role based on task type
            target_role = self._select_target_role(task_type)
            delegation_reason = self._get_delegation_reason(task_type, target_role)

            # Prepare task envelope for delegation
            task_envelope = {
                "task_type": task_type,
                "description": task_description,
                "priority": priority,
                "target_agent": target_role,
                "delegated_by": context.agent_id,
                "cycle_id": context.cycle_id,
            }

            # Track queue call (actual publish would be done by capability layer)
            context.track_port_call(
                "queue", "prepare_delegation", target=target_role
            )

            duration_ms = (time.perf_counter() - start_time) * 1000

            outputs = {
                "target_role": target_role,
                "delegation_reason": delegation_reason,
                "task_envelope": task_envelope,
            }

            evidence = ExecutionEvidence.create(
                skill_name=self.name,
                duration_ms=duration_ms,
                inputs_hash=self._hash_inputs(inputs),
                outputs_hash=self._hash_inputs({"target_role": target_role}),
                port_calls=context.get_port_calls(),
                metadata={"target_role": target_role},
            )

            return SkillResult(
                success=True,
                outputs=outputs,
                _evidence=evidence,
            )

        except Exception as e:
            duration_ms = (time.perf_counter() - start_time) * 1000
            evidence = ExecutionEvidence.create(
                skill_name=self.name,
                duration_ms=duration_ms,
                inputs_hash=self._hash_inputs(inputs),
                outputs_hash=self._hash_inputs({"error": str(e)}),
                port_calls=context.get_port_calls(),
                metadata={"error": True},
            )
            return SkillResult(
                success=False,
                outputs={},
                _evidence=evidence,
                error=str(e),
            )

    def _select_target_role(self, task_type: str) -> str:
        """Select appropriate role for task type."""
        for role, capabilities in ROLE_CAPABILITIES.items():
            if task_type in capabilities or any(
                cap in task_type for cap in capabilities
            ):
                return role
        # Default to dev for code-related tasks
        return "dev"

    def _get_delegation_reason(self, task_type: str, target_role: str) -> str:
        """Generate reason for delegation decision."""
        role_descriptions = {
            "dev": "code generation and implementation",
            "qa": "testing and validation",
            "strat": "strategic planning and architecture",
            "data": "analytics and data processing",
        }
        return (
            f"Task type '{task_type}' is best handled by {target_role} agent "
            f"which specializes in {role_descriptions.get(target_role, 'this domain')}"
        )

    def _hash_inputs(self, d: dict[str, Any]) -> str:
        """Create stable hash of inputs."""
        serialized = json.dumps(d, sort_keys=True, default=str)
        return hashlib.sha256(serialized.encode()).hexdigest()[:16]
