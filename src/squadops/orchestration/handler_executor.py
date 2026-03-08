"""Handler Executor implementing CapabilityExecutor interface.

Bridges capability handlers with the WorkloadRunner by implementing
the CapabilityExecutor port interface.

Part of SIP-0.8.8 Phase 6.
"""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING, Any

from squadops.capabilities.handlers.context import ExecutionContext
from squadops.orchestration.handler_registry import HandlerNotFoundError, HandlerRegistry
from squadops.ports.capabilities.executor import CapabilityExecutor
from squadops.tasks.models import TaskEnvelope, TaskResult

if TYPE_CHECKING:
    from squadops.agents.base import PortsBundle
    from squadops.agents.skills.registry import SkillRegistry

logger = logging.getLogger(__name__)


class HandlerExecutor(CapabilityExecutor):
    """CapabilityExecutor implementation using handlers.

    Executes capabilities by:
    1. Looking up the appropriate handler from registry
    2. Creating ExecutionContext with skill access
    3. Invoking handler.handle() with task inputs
    4. Converting result to TaskResult

    This bridges the capability contract system with the
    skill-based execution infrastructure.
    """

    def __init__(
        self,
        executor_id: str,
        handler_registry: HandlerRegistry,
        skill_registry: SkillRegistry,
        ports: PortsBundle,
        default_role: str = "lead",
    ) -> None:
        """Initialize handler executor.

        Args:
            executor_id: Unique identifier for this executor
            handler_registry: Registry of capability handlers
            skill_registry: Registry of skills for execution
            ports: PortsBundle for port access
            default_role: Default role for agent context
        """
        self._executor_id = executor_id
        self._handler_registry = handler_registry
        self._skill_registry = skill_registry
        self._ports = ports
        self._default_role = default_role

    @property
    def executor_id(self) -> str:
        """Return executor identifier."""
        return self._executor_id

    async def execute(
        self,
        envelope: TaskEnvelope,
        timeout_seconds: int | None = None,
    ) -> TaskResult:
        """Execute a task using the appropriate handler.

        Args:
            envelope: Task envelope with capability_id as task_type
            timeout_seconds: Maximum execution time

        Returns:
            TaskResult with execution outcome

        Raises:
            TimeoutError: If execution exceeds timeout
        """
        capability_id = envelope.task_type
        task_id = envelope.task_id

        logger.info(
            "executing_capability",
            extra={
                "task_id": task_id,
                "capability_id": capability_id,
                "agent_id": envelope.agent_id,
            },
        )

        try:
            # Get handler
            try:
                handler = self._handler_registry.get(capability_id)
            except HandlerNotFoundError:
                return TaskResult(
                    task_id=task_id,
                    status="FAILED",
                    outputs=None,
                    error=f"No handler for capability: {capability_id}",
                    execution_evidence={"error": "handler_not_found"},
                )

            # Create execution context with correlation for LangFuse tracing
            from squadops.telemetry.models import CorrelationContext

            corr_ctx = CorrelationContext.from_envelope(
                envelope,
                agent_id=envelope.agent_id,
            )
            context = ExecutionContext.create(
                agent_id=envelope.agent_id,
                role_id=self._default_role,
                task_id=task_id,
                cycle_id=envelope.cycle_id,
                ports=self._ports,
                skill_registry=self._skill_registry,
                correlation_context=corr_ctx,
            )

            # Validate inputs
            errors = handler.validate_inputs(envelope.inputs or {})
            if errors:
                return TaskResult(
                    task_id=task_id,
                    status="FAILED",
                    outputs=None,
                    error=f"Validation failed: {'; '.join(errors)}",
                    execution_evidence={"validation_errors": errors},
                )

            # Execute with timeout
            timeout = timeout_seconds or envelope.timeout or 300

            try:
                result = await asyncio.wait_for(
                    handler.handle(context, envelope.inputs or {}),
                    timeout=timeout,
                )
            except TimeoutError as err:
                raise TimeoutError(f"Execution timed out after {timeout}s") from err

            # Convert handler result to task result
            if result.success:
                logger.info(
                    "handler_succeeded",
                    extra={
                        "task_id": task_id,
                        "capability_id": capability_id,
                    },
                )
                return TaskResult(
                    task_id=task_id,
                    status="SUCCEEDED",
                    outputs=result.outputs,
                    error=None,
                    execution_evidence=self._evidence_to_dict(result.evidence),
                )
            else:
                logger.warning(
                    "handler_failed",
                    extra={
                        "task_id": task_id,
                        "capability_id": capability_id,
                        "error": result.error,
                    },
                )
                return TaskResult(
                    task_id=task_id,
                    status="FAILED",
                    outputs=result.outputs,
                    error=result.error,
                    execution_evidence=self._evidence_to_dict(result.evidence),
                )

        except TimeoutError:
            raise

        except Exception as e:
            logger.exception(
                "execution_failed",
                extra={"task_id": task_id, "error": str(e)},
            )
            return TaskResult(
                task_id=task_id,
                status="FAILED",
                outputs=None,
                error=str(e),
                execution_evidence={"exception": type(e).__name__},
            )

    async def health(self) -> dict[str, Any]:
        """Check executor health.

        Returns:
            Health status dictionary
        """
        return {
            "status": "healthy",
            "executor_id": self._executor_id,
            "handlers_registered": len(self._handler_registry.list_capabilities()),
            "skills_registered": len(self._skill_registry.list_skills()),
        }

    def can_execute(self, capability_id: str, agent_role: str) -> bool:
        """Check if this executor can handle a capability.

        Args:
            capability_id: Capability contract ID
            agent_role: Agent role

        Returns:
            True if executor can handle the capability
        """
        if not self._handler_registry.has(capability_id):
            return False

        # Check if role has access
        available = self._handler_registry.list_by_role(agent_role)
        return capability_id in available or not available  # Empty = all roles

    def _evidence_to_dict(self, evidence) -> dict[str, Any]:
        """Convert handler evidence to dictionary.

        Args:
            evidence: HandlerEvidence instance

        Returns:
            Dictionary for serialization
        """
        return {
            "handler_name": evidence.handler_name,
            "capability_id": evidence.capability_id,
            "executed_at": evidence.executed_at.isoformat(),
            "duration_ms": evidence.duration_ms,
            "skill_executions": list(evidence.skill_executions),
            "inputs_hash": evidence.inputs_hash,
            "outputs_hash": evidence.outputs_hash,
        }
