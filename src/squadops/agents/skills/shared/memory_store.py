"""Memory Store skill - store content in memory.

Atomic skill for semantic memory storage.
Part of SIP-0.8.8 Phase 4.
"""

from __future__ import annotations

import hashlib
import json
import time
from typing import TYPE_CHECKING, Any

from squadops.agents.skills.base import ExecutionEvidence, Skill, SkillResult
from squadops.memory.models import MemoryEntry

if TYPE_CHECKING:
    from squadops.agents.skills.context import SkillContext


class MemoryStoreSkill(Skill):
    """Atomic skill: store content in semantic memory.

    Inputs:
        content: str - Content to store
        metadata: dict (optional) - Additional metadata
        namespace: str (optional) - Memory namespace

    Outputs:
        memory_id: str - ID of the stored memory
        content_size: int - Size of stored content
    """

    @property
    def name(self) -> str:
        return "memory_store"

    @property
    def description(self) -> str:
        return "Store content in semantic memory with embeddings"

    @property
    def required_capabilities(self) -> tuple[str, ...]:
        return ("memory",)

    def validate_inputs(self, inputs: dict[str, Any]) -> list[str]:
        """Validate that content is provided."""
        errors = []
        if "content" not in inputs:
            errors.append("'content' is required")
        elif not isinstance(inputs["content"], str):
            errors.append("'content' must be a string")
        elif not inputs["content"].strip():
            errors.append("'content' cannot be empty")
        return errors

    async def execute(
        self,
        context: SkillContext,
        inputs: dict[str, Any],
    ) -> SkillResult:
        """Execute memory store.

        Args:
            context: SkillContext providing port access
            inputs: Must contain 'content', optionally 'metadata' and 'namespace'

        Returns:
            SkillResult with memory ID
        """
        start_time = time.perf_counter()

        content = inputs["content"]
        metadata = inputs.get("metadata", {})
        namespace = inputs.get("namespace", "default")

        # Track memory call
        context.track_port_call("memory", "store", namespace=namespace)

        try:
            # Create memory entry
            entry = MemoryEntry(
                content=content,
                metadata={
                    **metadata,
                    "namespace": namespace,
                    "task_id": context.task_id,
                    "agent_id": context.agent_id,
                },
            )

            # Store in memory
            memory_id = await context.memory.store(entry)
            duration_ms = (time.perf_counter() - start_time) * 1000

            outputs = {
                "memory_id": memory_id,
                "content_size": len(content),
            }

            evidence = ExecutionEvidence.create(
                skill_name=self.name,
                duration_ms=duration_ms,
                inputs_hash=self._hash_inputs({"content_size": len(content)}),
                outputs_hash=self._hash_inputs(outputs),
                port_calls=context.get_port_calls(),
                metadata={"namespace": namespace},
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
