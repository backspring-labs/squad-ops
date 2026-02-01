"""File Write skill - write content to file.

Atomic skill for filesystem write operations.
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


class FileWriteSkill(Skill):
    """Atomic skill: write content to file.

    Inputs:
        path: str - Path to the file to write
        content: str - Content to write

    Outputs:
        path: str - Absolute path written to
        bytes_written: int - Number of bytes written
    """

    @property
    def name(self) -> str:
        return "file_write"

    @property
    def description(self) -> str:
        return "Write content to a file"

    @property
    def required_capabilities(self) -> tuple[str, ...]:
        return ("filesystem",)

    def validate_inputs(self, inputs: dict[str, Any]) -> list[str]:
        """Validate that path and content are provided."""
        errors = []
        if "path" not in inputs:
            errors.append("'path' is required")
        elif not isinstance(inputs["path"], str):
            errors.append("'path' must be a string")
        elif not inputs["path"].strip():
            errors.append("'path' cannot be empty")

        if "content" not in inputs:
            errors.append("'content' is required")
        elif not isinstance(inputs["content"], str):
            errors.append("'content' must be a string")

        return errors

    async def execute(
        self,
        context: SkillContext,
        inputs: dict[str, Any],
    ) -> SkillResult:
        """Execute file write.

        Args:
            context: SkillContext providing port access
            inputs: Must contain 'path' and 'content'

        Returns:
            SkillResult with write confirmation
        """
        start_time = time.perf_counter()

        path = Path(inputs["path"])
        content = inputs["content"]

        # Track filesystem call
        context.track_port_call("filesystem", "write", path=str(path))

        try:
            # Write file
            context.filesystem.write(path, content)
            duration_ms = (time.perf_counter() - start_time) * 1000

            outputs = {
                "path": str(path.absolute()),
                "bytes_written": len(content),
            }

            evidence = ExecutionEvidence.create(
                skill_name=self.name,
                duration_ms=duration_ms,
                inputs_hash=self._hash_inputs({"path": str(path)}),
                outputs_hash=self._hash_inputs(outputs),
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
