"""Governance capability handler.

Orchestrates governance-related skills (task delegation)
to fulfill governance capability contracts.

Part of SIP-0.8.8 Phase 5.
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING, Any

from squadops.capabilities.handlers.base import (
    CapabilityHandler,
    HandlerEvidence,
    HandlerResult,
)

if TYPE_CHECKING:
    from squadops.capabilities.handlers.context import ExecutionContext


class TaskDelegationHandler(CapabilityHandler):
    """Handler for task delegation capability.

    Orchestrates task_delegation skill to route tasks
    to appropriate agent roles.
    """

    @property
    def name(self) -> str:
        return "task_delegation_handler"

    @property
    def capability_id(self) -> str:
        return "governance.task_delegation"

    @property
    def description(self) -> str:
        return "Delegate a task to the appropriate agent role"

    @property
    def required_skills(self) -> tuple[str, ...]:
        return ("task_delegation",)

    def validate_inputs(
        self,
        inputs: dict[str, Any],
        contract=None,
    ) -> list[str]:
        errors = super().validate_inputs(inputs, contract)

        if "task_type" not in inputs:
            errors.append("'task_type' is required")
        if "task_description" not in inputs:
            errors.append("'task_description' is required")

        return errors

    async def handle(
        self,
        context: ExecutionContext,
        inputs: dict[str, Any],
    ) -> HandlerResult:
        """Delegate task using task_delegation skill.

        Args:
            context: ExecutionContext with skill access
            inputs: Must contain 'task_type' and 'task_description'

        Returns:
            HandlerResult with delegation outputs
        """
        start_time = time.perf_counter()

        try:
            result = await context.execute_skill(
                "task_delegation",
                {
                    "task_type": inputs["task_type"],
                    "task_description": inputs["task_description"],
                },
            )

            duration_ms = (time.perf_counter() - start_time) * 1000

            if not result.success:
                evidence = HandlerEvidence.create(
                    handler_name=self.name,
                    capability_id=self.capability_id,
                    duration_ms=duration_ms,
                    skill_executions=context.get_skill_executions(),
                    inputs_hash=self._hash_dict(inputs),
                    outputs_hash=self._hash_dict({"error": result.error}),
                    metadata={"error": True},
                )
                return HandlerResult(
                    success=False,
                    outputs={},
                    _evidence=evidence,
                    error=result.error,
                )

            outputs = {
                "target_role": result.outputs.get("target_role", ""),
                "task_envelope": result.outputs.get("task_envelope", {}),
            }

            evidence = HandlerEvidence.create(
                handler_name=self.name,
                capability_id=self.capability_id,
                duration_ms=duration_ms,
                skill_executions=context.get_skill_executions(),
                inputs_hash=self._hash_dict(inputs),
                outputs_hash=self._hash_dict(outputs),
            )

            return HandlerResult(
                success=True,
                outputs=outputs,
                _evidence=evidence,
            )

        except Exception as e:
            duration_ms = (time.perf_counter() - start_time) * 1000
            evidence = HandlerEvidence.create(
                handler_name=self.name,
                capability_id=self.capability_id,
                duration_ms=duration_ms,
                skill_executions=context.get_skill_executions(),
                inputs_hash=self._hash_dict(inputs),
                outputs_hash=self._hash_dict({"error": str(e)}),
                metadata={"error": True},
            )
            return HandlerResult(
                success=False,
                outputs={},
                _evidence=evidence,
                error=str(e),
            )
