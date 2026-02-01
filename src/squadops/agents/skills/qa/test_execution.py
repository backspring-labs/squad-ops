"""Test Execution skill - run tests and report results.

QA agent skill for test execution.
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


class TestExecutionSkill(Skill):
    """Skill for executing tests and reporting results.

    Inputs:
        test_path: str - Path to tests to execute
        test_type: str (optional) - Type of tests (unit/integration)
        options: dict (optional) - Additional test options

    Outputs:
        passed: bool - Whether all tests passed
        total: int - Total number of tests
        passed_count: int - Number of passed tests
        failed_count: int - Number of failed tests
        results: list[dict] - Individual test results
    """

    @property
    def name(self) -> str:
        return "test_execution"

    @property
    def description(self) -> str:
        return "Execute tests and report results"

    @property
    def required_capabilities(self) -> tuple[str, ...]:
        return ("filesystem",)

    def validate_inputs(self, inputs: dict[str, Any]) -> list[str]:
        """Validate test execution inputs."""
        errors = []
        if "test_path" not in inputs:
            errors.append("'test_path' is required")
        return errors

    async def execute(
        self,
        context: SkillContext,
        inputs: dict[str, Any],
    ) -> SkillResult:
        """Execute tests.

        Args:
            context: SkillContext providing port access
            inputs: Must contain 'test_path'

        Returns:
            SkillResult with test results
        """
        start_time = time.perf_counter()

        test_path = inputs["test_path"]
        test_type = inputs.get("test_type", "unit")
        options = inputs.get("options", {})

        # Track filesystem call for test discovery
        context.track_port_call("filesystem", "exists", path=test_path)

        try:
            # In a real implementation, this would:
            # 1. Discover tests at the path
            # 2. Run test framework (pytest, etc.)
            # 3. Collect results
            # For now, return a placeholder structure that indicates
            # the skill was invoked and provides the expected output shape.

            # Simulated test execution result structure
            results = [
                {
                    "name": f"test_{test_type}_placeholder",
                    "status": "passed",
                    "duration_ms": 0.1,
                }
            ]

            duration_ms = (time.perf_counter() - start_time) * 1000

            outputs = {
                "passed": True,
                "total": len(results),
                "passed_count": len([r for r in results if r["status"] == "passed"]),
                "failed_count": len([r for r in results if r["status"] == "failed"]),
                "results": results,
                "test_path": test_path,
                "test_type": test_type,
            }

            evidence = ExecutionEvidence.create(
                skill_name=self.name,
                duration_ms=duration_ms,
                inputs_hash=self._hash_inputs(inputs),
                outputs_hash=self._hash_inputs(
                    {"passed": outputs["passed"], "total": outputs["total"]}
                ),
                port_calls=context.get_port_calls(),
                metadata={"test_type": test_type},
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

    def _hash_inputs(self, d: dict[str, Any]) -> str:
        """Create stable hash of inputs."""
        serialized = json.dumps(d, sort_keys=True, default=str)
        return hashlib.sha256(serialized.encode()).hexdigest()[:16]
