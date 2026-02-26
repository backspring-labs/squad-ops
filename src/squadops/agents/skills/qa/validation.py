"""Validation skill - validate artifacts and outputs.

QA agent skill for validation.
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


class ValidationSkill(Skill):
    """Skill for validating artifacts against criteria.

    Inputs:
        artifact_path: str - Path to artifact to validate
        criteria: list[str] - Validation criteria
        schema: dict (optional) - JSON schema for validation

    Outputs:
        valid: bool - Whether validation passed
        errors: list[str] - Validation errors if any
        warnings: list[str] - Validation warnings
    """

    @property
    def name(self) -> str:
        return "validation"

    @property
    def description(self) -> str:
        return "Validate artifacts against criteria"

    @property
    def required_capabilities(self) -> tuple[str, ...]:
        return ("filesystem",)

    def validate_inputs(self, inputs: dict[str, Any]) -> list[str]:
        """Validate skill inputs."""
        errors = []
        if "artifact_path" not in inputs:
            errors.append("'artifact_path' is required")
        if "criteria" not in inputs:
            errors.append("'criteria' is required")
        elif not isinstance(inputs["criteria"], list):
            errors.append("'criteria' must be a list")
        return errors

    async def execute(
        self,
        context: SkillContext,
        inputs: dict[str, Any],
    ) -> SkillResult:
        """Execute validation.

        Args:
            context: SkillContext providing port access
            inputs: Must contain 'artifact_path' and 'criteria'

        Returns:
            SkillResult with validation results
        """
        start_time = time.perf_counter()

        artifact_path = inputs["artifact_path"]
        criteria = inputs["criteria"]
        schema = inputs.get("schema")

        # Track filesystem call
        context.track_port_call("filesystem", "read", path=artifact_path)

        try:
            # Read artifact
            content = context.filesystem.read(artifact_path)

            # Perform validation
            errors = []
            warnings = []

            # Check each criterion
            for criterion in criteria:
                passed, message = self._check_criterion(criterion, content, schema)
                if not passed:
                    errors.append(message)

            duration_ms = (time.perf_counter() - start_time) * 1000

            outputs = {
                "valid": len(errors) == 0,
                "errors": errors,
                "warnings": warnings,
                "artifact_path": artifact_path,
                "criteria_checked": len(criteria),
            }

            evidence = ExecutionEvidence.create(
                skill_name=self.name,
                duration_ms=duration_ms,
                inputs_hash=self._hash_inputs(inputs),
                outputs_hash=self._hash_inputs({"valid": outputs["valid"]}),
                port_calls=context.get_port_calls(),
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

    def _check_criterion(
        self,
        criterion: str,
        content: str,
        schema: dict | None,
    ) -> tuple[bool, str]:
        """Check a single validation criterion.

        Args:
            criterion: The criterion to check
            content: Artifact content
            schema: Optional JSON schema

        Returns:
            Tuple of (passed, message)
        """
        # Simple criterion checking - in real implementation would be more sophisticated
        criterion_lower = criterion.lower()

        if "not_empty" in criterion_lower:
            if not content.strip():
                return False, "Content is empty"
            return True, "Content is not empty"

        if "valid_json" in criterion_lower:
            try:
                json.loads(content)
                return True, "Content is valid JSON"
            except json.JSONDecodeError as e:
                return False, f"Invalid JSON: {e}"

        if "contains:" in criterion_lower:
            search_term = criterion.split(":", 1)[1].strip()
            if search_term in content:
                return True, f"Contains '{search_term}'"
            return False, f"Does not contain '{search_term}'"

        # Default: criterion passes
        return True, f"Criterion '{criterion}' checked"

    def _hash_inputs(self, d: dict[str, Any]) -> str:
        """Create stable hash of inputs."""
        serialized = json.dumps(d, sort_keys=True, default=str)
        return hashlib.sha256(serialized.encode()).hexdigest()[:16]
