"""QA capability handler.

Orchestrates QA-related skills (test execution, validation)
to fulfill QA capability contracts.

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


class TestExecutionHandler(CapabilityHandler):
    """Handler for test execution capability.

    Orchestrates test_execution skill to run tests
    and produce structured results.
    """

    @property
    def name(self) -> str:
        return "test_execution_handler"

    @property
    def capability_id(self) -> str:
        return "qa.test_execution"

    @property
    def description(self) -> str:
        return "Execute tests and report results"

    @property
    def required_skills(self) -> tuple[str, ...]:
        return ("test_execution",)

    def validate_inputs(
        self,
        inputs: dict[str, Any],
        contract=None,
    ) -> list[str]:
        errors = super().validate_inputs(inputs, contract)

        if "test_path" not in inputs:
            errors.append("'test_path' is required")

        return errors

    async def handle(
        self,
        context: ExecutionContext,
        inputs: dict[str, Any],
    ) -> HandlerResult:
        """Execute tests using test_execution skill.

        Args:
            context: ExecutionContext with skill access
            inputs: Must contain 'test_path', optionally 'pattern', 'verbose'

        Returns:
            HandlerResult with test results
        """
        start_time = time.perf_counter()

        try:
            skill_inputs = {"test_path": inputs["test_path"]}
            if "pattern" in inputs:
                skill_inputs["pattern"] = inputs["pattern"]
            if "verbose" in inputs:
                skill_inputs["verbose"] = inputs["verbose"]

            result = await context.execute_skill("test_execution", skill_inputs)

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
                "passed": result.outputs.get("passed", 0),
                "failed": result.outputs.get("failed", 0),
                "total": result.outputs.get("total", 0),
                "results": result.outputs.get("results", []),
                "all_passed": result.outputs.get("passed", 0) == result.outputs.get("total", 0),
            }

            evidence = HandlerEvidence.create(
                handler_name=self.name,
                capability_id=self.capability_id,
                duration_ms=duration_ms,
                skill_executions=context.get_skill_executions(),
                inputs_hash=self._hash_dict(inputs),
                outputs_hash=self._hash_dict(
                    {
                        "passed": outputs["passed"],
                        "total": outputs["total"],
                    }
                ),
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


class ValidationHandler(CapabilityHandler):
    """Handler for validation capability.

    Orchestrates validation skill to verify artifacts
    against criteria.
    """

    @property
    def name(self) -> str:
        return "validation_handler"

    @property
    def capability_id(self) -> str:
        return "qa.validation"

    @property
    def description(self) -> str:
        return "Validate artifacts against criteria"

    @property
    def required_skills(self) -> tuple[str, ...]:
        return ("validation",)

    def validate_inputs(
        self,
        inputs: dict[str, Any],
        contract=None,
    ) -> list[str]:
        errors = super().validate_inputs(inputs, contract)

        if "artifact_path" not in inputs:
            errors.append("'artifact_path' is required")
        if "criteria" not in inputs:
            errors.append("'criteria' is required")
        elif not isinstance(inputs.get("criteria"), list):
            errors.append("'criteria' must be a list")

        return errors

    async def handle(
        self,
        context: ExecutionContext,
        inputs: dict[str, Any],
    ) -> HandlerResult:
        """Validate artifacts using validation skill.

        Args:
            context: ExecutionContext with skill access
            inputs: Must contain 'artifact_path' and 'criteria'

        Returns:
            HandlerResult with validation results
        """
        start_time = time.perf_counter()

        try:
            result = await context.execute_skill(
                "validation",
                {
                    "artifact_path": inputs["artifact_path"],
                    "criteria": inputs["criteria"],
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
                "valid": result.outputs.get("valid", False),
                "errors": result.outputs.get("errors", []),
                "criteria_checked": len(inputs["criteria"]),
            }

            evidence = HandlerEvidence.create(
                handler_name=self.name,
                capability_id=self.capability_id,
                duration_ms=duration_ms,
                skill_executions=context.get_skill_executions(),
                inputs_hash=self._hash_dict(inputs),
                outputs_hash=self._hash_dict({"valid": outputs["valid"]}),
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
