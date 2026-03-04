"""Agent Orchestrator for multi-agent coordination.

Coordinates task routing, agent selection, and workflow execution
across the agent squad.

Part of SIP-0.8.8 Phase 6.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from squadops.orchestration.handler_executor import HandlerExecutor
from squadops.orchestration.handler_registry import HandlerRegistry
from squadops.tasks.models import TaskEnvelope, TaskResult
from squadops.telemetry.models import CorrelationContext, StructuredEvent

if TYPE_CHECKING:
    from squadops.agents.base import PortsBundle
    from squadops.agents.skills.registry import SkillRegistry
    from squadops.ports.telemetry.llm_observability import LLMObservabilityPort

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class TaskRouting:
    """Result of task routing decision.

    Attributes:
        target_role: Role to handle the task
        target_agent_id: Specific agent ID (if known)
        capability_id: Capability to invoke
        priority: Task priority
        reason: Routing decision reason
    """

    target_role: str
    capability_id: str
    target_agent_id: str | None = None
    priority: int = 5
    reason: str = ""


@dataclass
class OrchestratorState:
    """Orchestrator runtime state.

    Attributes:
        active_tasks: Currently executing tasks
        task_history: Recent completed tasks
        agent_states: Agent availability/health
    """

    active_tasks: dict[str, TaskEnvelope] = field(default_factory=dict)
    task_history: list[str] = field(default_factory=list)
    agent_states: dict[str, dict[str, Any]] = field(default_factory=dict)


class AgentOrchestrator:
    """Orchestrator for multi-agent workflows.

    Coordinates:
    - Task routing to appropriate agents/handlers
    - Agent lifecycle management
    - Workflow execution across agent squad

    Example:
        orchestrator = AgentOrchestrator(
            handler_registry=registry,
            skill_registry=skill_registry,
            ports=ports,
        )
        result = await orchestrator.submit_task(envelope)
    """

    # Default routing rules: task_type prefix -> role
    DEFAULT_ROUTING = {
        "governance.": "lead",
        "development.": "dev",
        "qa.": "qa",
        "data.": "data",
        "strategy.": "strat",
        "agent.": "lead",  # Agent lifecycle tasks go to lead
    }

    def __init__(
        self,
        handler_registry: HandlerRegistry,
        skill_registry: SkillRegistry,
        ports: PortsBundle,
        llm_observability: LLMObservabilityPort | None = None,
    ) -> None:
        """Initialize orchestrator.

        Args:
            handler_registry: Registry of capability handlers
            skill_registry: Registry of skills
            ports: PortsBundle for port access
            llm_observability: LLM observability port (SIP-0061)
        """
        self._handler_registry = handler_registry
        self._skill_registry = skill_registry
        self._ports = ports
        self._state = OrchestratorState()

        # SIP-0061: Always inject NoOp when None
        if llm_observability is None:
            from adapters.telemetry.noop_llm_observability import NoOpLLMObservabilityAdapter

            llm_observability = NoOpLLMObservabilityAdapter()
        self._llm_observability = llm_observability

        # Create default executor
        self._executor = HandlerExecutor(
            executor_id="orchestrator-executor",
            handler_registry=handler_registry,
            skill_registry=skill_registry,
            ports=ports,
        )

    def route_task(self, envelope: TaskEnvelope) -> TaskRouting:
        """Determine routing for a task.

        Args:
            envelope: Task to route

        Returns:
            TaskRouting with target information
        """
        task_type = envelope.task_type

        # Route by task type prefix
        for prefix, role in self.DEFAULT_ROUTING.items():
            if task_type.startswith(prefix):
                return TaskRouting(
                    target_role=role,
                    capability_id=task_type,
                    reason=f"prefix_match:{prefix}",
                )

        # Default to lead for unknown tasks
        return TaskRouting(
            target_role="lead",
            capability_id=task_type,
            reason="default_to_lead",
        )

    async def submit_task(
        self,
        envelope: TaskEnvelope,
        timeout_seconds: int | None = None,
    ) -> TaskResult:
        """Submit a task for execution.

        Routes task to appropriate handler and executes.

        Args:
            envelope: Task to execute
            timeout_seconds: Optional timeout

        Returns:
            TaskResult with execution outcome
        """
        task_id = envelope.task_id
        logger.info(
            "task_submitted",
            extra={
                "task_id": task_id,
                "task_type": envelope.task_type,
            },
        )

        # Track active task
        self._state.active_tasks[task_id] = envelope

        try:
            # Route the task
            routing = self.route_task(envelope)

            logger.debug(
                "task_routed",
                extra={
                    "task_id": task_id,
                    "target_role": routing.target_role,
                    "capability_id": routing.capability_id,
                    "reason": routing.reason,
                },
            )

            # Execute via handler executor
            result = await self._executor.execute(envelope, timeout_seconds)

            # Record in history
            self._state.task_history.append(task_id)
            if len(self._state.task_history) > 100:
                self._state.task_history = self._state.task_history[-100:]

            return result

        finally:
            # Remove from active
            self._state.active_tasks.pop(task_id, None)

    async def submit_batch(
        self,
        envelopes: list[TaskEnvelope],
        timeout_seconds: int | None = None,
    ) -> list[TaskResult]:
        """Submit multiple tasks for execution.

        Executes tasks sequentially (respecting dependencies).

        Args:
            envelopes: Tasks to execute
            timeout_seconds: Timeout per task

        Returns:
            List of TaskResults in order
        """
        # SIP-0061: Derive cycle_id from the first envelope (batch shares a cycle)
        cycle_id = envelopes[0].cycle_id if envelopes else "batch-unknown"
        ctx_cycle = CorrelationContext.for_cycle(cycle_id=cycle_id)

        # SIP-0061: Start cycle trace
        self._llm_observability.start_cycle_trace(ctx_cycle)
        self._llm_observability.record_event(
            ctx_cycle,
            StructuredEvent(
                name="cycle.started",
                message=f"Cycle {cycle_id} started ({len(envelopes)} tasks)",
            ),
        )

        results = []
        try:
            for envelope in envelopes:
                # SIP-0061: Start pulse span per-task
                ctx_pulse = CorrelationContext.for_pulse(
                    cycle_id=cycle_id, pulse_id=envelope.pulse_id
                )
                self._llm_observability.start_pulse_span(ctx_pulse)
                self._llm_observability.record_event(
                    ctx_pulse,
                    StructuredEvent(
                        name="pulse.started",
                        message=f"Pulse {envelope.pulse_id} started",
                    ),
                )

                result = await self.submit_task(envelope, timeout_seconds)
                results.append(result)

                # SIP-0061: End pulse span
                self._llm_observability.record_event(
                    ctx_pulse,
                    StructuredEvent(
                        name="pulse.completed",
                        message=f"Pulse {envelope.pulse_id} completed",
                    ),
                )
                self._llm_observability.end_pulse_span(ctx_pulse)

                # Stop on failure if desired (fail-fast)
                if result.status != "SUCCEEDED":
                    # Mark remaining as skipped
                    for remaining in envelopes[len(results) :]:
                        results.append(
                            TaskResult(
                                task_id=remaining.task_id,
                                status="SKIPPED",
                                outputs=None,
                                error=f"Skipped due to prior failure: {result.task_id}",
                            )
                        )
                    break

        finally:
            # SIP-0061: Deterministic shutdown sequence
            self._llm_observability.record_event(
                ctx_cycle,
                StructuredEvent(
                    name="cycle.completed",
                    message=f"Cycle {cycle_id} completed ({len(results)} results)",
                ),
            )
            self._llm_observability.end_cycle_trace(ctx_cycle)
            self._llm_observability.flush()
            self._llm_observability.close()

        return results

    def get_active_tasks(self) -> list[str]:
        """Get list of currently active task IDs.

        Returns:
            List of active task IDs
        """
        return list(self._state.active_tasks.keys())

    def get_agent_states(self) -> dict[str, dict[str, Any]]:
        """Get current agent states.

        Returns:
            Dictionary of agent_id -> state
        """
        return dict(self._state.agent_states)

    def get_available_capabilities(self, role: str | None = None) -> list[str]:
        """Get capabilities available for execution.

        Args:
            role: Optional role filter

        Returns:
            List of capability IDs
        """
        if role:
            return self._handler_registry.list_by_role(role)
        return self._handler_registry.list_capabilities()

    async def health_check(self) -> dict[str, Any]:
        """Perform orchestrator health check.

        Returns:
            Health status dictionary
        """
        executor_health = await self._executor.health()

        return {
            "status": "healthy",
            "executor": executor_health,
            "active_tasks": len(self._state.active_tasks),
            "capabilities": len(self._handler_registry.list_capabilities()),
        }

    def create_envelope(
        self,
        task_type: str,
        inputs: dict[str, Any],
        agent_id: str | None = None,
        cycle_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> TaskEnvelope:
        """Helper to create a TaskEnvelope.

        Args:
            task_type: Type/capability ID
            inputs: Task inputs
            agent_id: Optional target agent
            cycle_id: Optional cycle ID
            metadata: Optional metadata

        Returns:
            TaskEnvelope ready for submission
        """
        task_id = f"task-{uuid.uuid4().hex[:12]}"
        cycle = cycle_id or f"cycle-{uuid.uuid4().hex[:8]}"

        return TaskEnvelope(
            task_id=task_id,
            agent_id=agent_id or "orchestrator",
            cycle_id=cycle,
            pulse_id=f"pulse-{uuid.uuid4().hex[:8]}",
            project_id="default",
            task_type=task_type,
            inputs=inputs,
            correlation_id=f"corr-{cycle}",
            causation_id=f"cause-{task_id}",
            trace_id=f"trace-{task_id}",
            span_id=f"span-{task_id}",
            metadata=metadata or {},
        )
