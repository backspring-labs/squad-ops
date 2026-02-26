"""Warmboot capability handler.

Orchestrates memory-related skills for agent warmboot/initialization.
Enables agents to recall context and state on startup.

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


class WarmbootHandler(CapabilityHandler):
    """Handler for agent warmboot capability.

    Orchestrates memory_recall and memory_store skills
    to restore agent context on initialization.
    """

    @property
    def name(self) -> str:
        return "warmboot_handler"

    @property
    def capability_id(self) -> str:
        return "agent.warmboot"

    @property
    def description(self) -> str:
        return "Initialize agent with recalled context from memory"

    @property
    def required_skills(self) -> tuple[str, ...]:
        return ("memory_recall", "memory_store")

    def validate_inputs(
        self,
        inputs: dict[str, Any],
        contract=None,
    ) -> list[str]:
        errors = super().validate_inputs(inputs, contract)

        if "agent_id" not in inputs:
            errors.append("'agent_id' is required")
        if "context_query" not in inputs:
            errors.append("'context_query' is required")

        return errors

    async def handle(
        self,
        context: ExecutionContext,
        inputs: dict[str, Any],
    ) -> HandlerResult:
        """Warmboot agent using memory skills.

        Args:
            context: ExecutionContext with skill access
            inputs: Must contain 'agent_id' and 'context_query'

        Returns:
            HandlerResult with recalled context
        """
        start_time = time.perf_counter()

        try:
            # Recall relevant context from memory
            recall_result = await context.execute_skill(
                "memory_recall",
                {
                    "query": inputs["context_query"],
                    "limit": inputs.get("recall_limit", 10),
                    "namespace": inputs.get("namespace"),
                },
            )

            if not recall_result.success:
                duration_ms = (time.perf_counter() - start_time) * 1000
                evidence = HandlerEvidence.create(
                    handler_name=self.name,
                    capability_id=self.capability_id,
                    duration_ms=duration_ms,
                    skill_executions=context.get_skill_executions(),
                    inputs_hash=self._hash_dict(inputs),
                    outputs_hash=self._hash_dict({"error": recall_result.error}),
                    metadata={"error": True},
                )
                return HandlerResult(
                    success=False,
                    outputs={},
                    _evidence=evidence,
                    error=f"Memory recall failed: {recall_result.error}",
                )

            recalled_memories = recall_result.outputs.get("results", [])
            recall_count = recall_result.outputs.get("count", 0)

            # Optionally store warmboot event in memory
            if inputs.get("log_warmboot", False):
                warmboot_log = {
                    "event": "warmboot",
                    "agent_id": inputs["agent_id"],
                    "recalled_count": recall_count,
                    "context_query": inputs["context_query"],
                }
                await context.execute_skill(
                    "memory_store",
                    {
                        "content": str(warmboot_log),
                        "metadata": {"type": "warmboot_log"},
                    },
                )

            duration_ms = (time.perf_counter() - start_time) * 1000

            outputs = {
                "recalled_memories": recalled_memories,
                "recall_count": recall_count,
                "agent_id": inputs["agent_id"],
                "warmboot_complete": True,
            }

            evidence = HandlerEvidence.create(
                handler_name=self.name,
                capability_id=self.capability_id,
                duration_ms=duration_ms,
                skill_executions=context.get_skill_executions(),
                inputs_hash=self._hash_dict(inputs),
                outputs_hash=self._hash_dict({"recall_count": recall_count}),
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


class ContextSyncHandler(CapabilityHandler):
    """Handler for context synchronization capability.

    Orchestrates memory skills to sync context between agents
    or persist important state.
    """

    @property
    def name(self) -> str:
        return "context_sync_handler"

    @property
    def capability_id(self) -> str:
        return "agent.context_sync"

    @property
    def description(self) -> str:
        return "Synchronize context to memory for persistence"

    @property
    def required_skills(self) -> tuple[str, ...]:
        return ("memory_store",)

    def validate_inputs(
        self,
        inputs: dict[str, Any],
        contract=None,
    ) -> list[str]:
        errors = super().validate_inputs(inputs, contract)

        if "content" not in inputs:
            errors.append("'content' is required")
        elif not isinstance(inputs["content"], str):
            errors.append("'content' must be a string")
        elif not inputs["content"].strip():
            errors.append("'content' cannot be empty")

        return errors

    async def handle(
        self,
        context: ExecutionContext,
        inputs: dict[str, Any],
    ) -> HandlerResult:
        """Sync context to memory using memory_store skill.

        Args:
            context: ExecutionContext with skill access
            inputs: Must contain 'content'

        Returns:
            HandlerResult with storage confirmation
        """
        start_time = time.perf_counter()

        try:
            skill_inputs = {"content": inputs["content"]}
            if "metadata" in inputs:
                skill_inputs["metadata"] = inputs["metadata"]
            if "namespace" in inputs:
                skill_inputs["namespace"] = inputs["namespace"]

            result = await context.execute_skill("memory_store", skill_inputs)

            duration_ms = (time.perf_counter() - start_time) * 1000

            if not result.success:
                evidence = HandlerEvidence.create(
                    handler_name=self.name,
                    capability_id=self.capability_id,
                    duration_ms=duration_ms,
                    skill_executions=context.get_skill_executions(),
                    inputs_hash=self._hash_dict({"content_length": len(inputs["content"])}),
                    outputs_hash=self._hash_dict({"error": result.error}),
                    metadata={"error": True},
                )
                return HandlerResult(
                    success=False,
                    outputs={},
                    _evidence=evidence,
                    error=f"Memory store failed: {result.error}",
                )

            outputs = {
                "memory_id": result.outputs.get("memory_id", ""),
                "synced": True,
            }

            evidence = HandlerEvidence.create(
                handler_name=self.name,
                capability_id=self.capability_id,
                duration_ms=duration_ms,
                skill_executions=context.get_skill_executions(),
                inputs_hash=self._hash_dict({"content_length": len(inputs["content"])}),
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
