"""File Read skill - read content from file.

Atomic skill for filesystem read operations.
Part of SIP-0.8.8 Phase 4.
"""
from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from typing import TYPE_CHECKING, Any

from squadops.agents.skills.base import ExecutionEvidence, Skill, SkillResult

if TYPE_CHECKING:
    from squadops.agents.skills.context import SkillContext


class FileReadSkill(Skill):
    """Atomic skill: read content from file.

    Inputs:
        path: str - Path to the file to read

    Outputs:
        content: str - File contents
        path: str - Absolute path read from
        size: int - Content size in bytes
    """

    @property
    def name(self) -> str:
        return "file_read"

    @property
    def description(self) -> str:
        return "Read content from a file"

    @property
    def required_capabilities(self) -> tuple[str, ...]:
        return ("filesystem",)

    def validate_inputs(self, inputs: dict[str, Any]) -> list[str]:
        """Validate that path is provided."""
        errors = []
        if "path" not in inputs:
            errors.append("'path' is required")
        elif not isinstance(inputs["path"], str):
            errors.append("'path' must be a string")
        elif not inputs["path"].strip():
            errors.append("'path' cannot be empty")
        return errors

    async def execute(
        self,
        context: SkillContext,
        inputs: dict[str, Any],
    ) -> SkillResult:
        """Execute file read.

        Args:
            context: SkillContext providing port access
            inputs: Must contain 'path'

        Returns:
            SkillResult with file contents
        """
        start_time = time.perf_counter()

        path = Path(inputs["path"])

        # Track filesystem call
        context.track_port_call("filesystem", "read", path=str(path))

        try:
            # Read file
            content = context.filesystem.read(path)
            duration_ms = (time.perf_counter() - start_time) * 1000

            outputs = {
                "content": content,
                "path": str(path.absolute()),
                "size": len(content),
            }

            evidence = ExecutionEvidence.create(
                skill_name=self.name,
                duration_ms=duration_ms,
                inputs_hash=self._hash_inputs(inputs),
                outputs_hash=self._hash_inputs({"size": outputs["size"]}),
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

    def _hash_inputs(self, d: dict[str, Any]) -> str:
        """Create stable hash of inputs."""
        serialized = json.dumps(d, sort_keys=True, default=str)
        return hashlib.sha256(serialized.encode()).hexdigest()[:16]
