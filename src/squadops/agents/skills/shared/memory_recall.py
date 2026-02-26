"""Memory Recall skill - search and recall from memory.

Atomic skill for semantic memory search.
Part of SIP-0.8.8 Phase 4.
"""

from __future__ import annotations

import hashlib
import json
import time
from typing import TYPE_CHECKING, Any

from squadops.agents.skills.base import ExecutionEvidence, Skill, SkillResult
from squadops.memory.models import MemoryQuery

if TYPE_CHECKING:
    from squadops.agents.skills.context import SkillContext


class MemoryRecallSkill(Skill):
    """Atomic skill: search and recall from semantic memory.

    Inputs:
        query: str - Search query text
        limit: int (optional) - Maximum results (default 5)
        namespace: str (optional) - Memory namespace to search

    Outputs:
        results: list[dict] - List of matching memories with scores
        count: int - Number of results returned
    """

    @property
    def name(self) -> str:
        return "memory_recall"

    @property
    def description(self) -> str:
        return "Search and recall content from semantic memory"

    @property
    def required_capabilities(self) -> tuple[str, ...]:
        return ("memory",)

    def validate_inputs(self, inputs: dict[str, Any]) -> list[str]:
        """Validate that query is provided."""
        errors = []
        if "query" not in inputs:
            errors.append("'query' is required")
        elif not isinstance(inputs["query"], str):
            errors.append("'query' must be a string")
        elif not inputs["query"].strip():
            errors.append("'query' cannot be empty")

        if "limit" in inputs:
            limit = inputs["limit"]
            if not isinstance(limit, int) or limit < 1:
                errors.append("'limit' must be a positive integer")

        return errors

    async def execute(
        self,
        context: SkillContext,
        inputs: dict[str, Any],
    ) -> SkillResult:
        """Execute memory recall.

        Args:
            context: SkillContext providing port access
            inputs: Must contain 'query', optionally 'limit' and 'namespace'

        Returns:
            SkillResult with search results
        """
        start_time = time.perf_counter()

        query_text = inputs["query"]
        limit = inputs.get("limit", 5)
        namespace = inputs.get("namespace")

        # Track memory call
        context.track_port_call("memory", "search", limit=limit)

        try:
            # Build query
            query = MemoryQuery(
                text=query_text,
                limit=limit,
                namespace=namespace,
            )

            # Search memory
            results = await context.memory.search(query)
            duration_ms = (time.perf_counter() - start_time) * 1000

            # Convert results to serializable format
            result_dicts = [
                {
                    "memory_id": r.memory_id,
                    "content": r.entry.content,
                    "score": r.score,
                    "metadata": dict(r.entry.metadata) if r.entry.metadata else {},
                }
                for r in results
            ]

            outputs = {
                "results": result_dicts,
                "count": len(result_dicts),
            }

            evidence = ExecutionEvidence.create(
                skill_name=self.name,
                duration_ms=duration_ms,
                inputs_hash=self._hash_inputs({"query": query_text, "limit": limit}),
                outputs_hash=self._hash_inputs({"count": outputs["count"]}),
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
