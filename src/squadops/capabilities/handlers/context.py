"""ExecutionContext for capability handler execution.

Provides handlers with access to ports and task/cycle metadata.

Part of SIP-0.8.8 Phase 5.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from squadops.cycles.llm_usage import UsageLedger

if TYPE_CHECKING:
    from squadops.agents.base import PortsBundle
    from squadops.telemetry.models import CorrelationContext

logger = logging.getLogger(__name__)


@dataclass
class ExecutionContext:
    """Context for capability handler execution.

    Provides handlers with:
    - PortsBundle for port access
    - Task/cycle metadata

    Attributes:
        agent_id: ID of the executing agent
        role_id: the role the executing process IS (SIP-0108 §10i) — the identity layer of
            every system prompt reads it. A handler's own ``_role`` is the STEP's role: what
            the task does, which owns its artifacts and routes its repairs.
        task_id: Current task ID
        cycle_id: Current cycle ID
        project_id: Current project ID
        ports: PortsBundle for port access
    """

    agent_id: str
    role_id: str
    task_id: str
    cycle_id: str
    ports: PortsBundle
    project_id: str = ""
    correlation_context: CorrelationContext | None = None
    #: SIP-0108 §4.1: this task's LLM usage, added by ``_llm_call`` for every call — the one
    #: seam every generation passes — and carried on the task result on every exit path.
    llm_usage: UsageLedger = field(default_factory=UsageLedger)
    #: SIP-0096 §17a: the checks this task's responses disputed, stripped from each response
    #: by ``_llm_call`` and carried on the task result's outputs by the handler executor.
    disputed_checks: list[dict[str, str]] = field(default_factory=list)
    #: SIP-0110 §0.11 (#2105): when the task type is an authoring seam, the handler executor sets
    #: these before ``handle()``: the dispatched task type, the inputs as plain JSON as the
    #: handler was handed them, and the paths JSON could not carry. ``None`` for every other
    #: task. ``_llm_call`` reads them to build the envelope.
    authoring_task_type: str | None = None
    authoring_inputs: dict[str, Any] | None = None
    authoring_inputs_not_captured: tuple[str, ...] = ()
    #: The authoring replay envelope, as a dict: built by ``_llm_call`` at the task's first model
    #: call, once, and carried on the task result on every exit path.
    authoring_envelope: dict[str, Any] | None = None

    @classmethod
    def create(
        cls,
        agent_id: str,
        role_id: str,
        task_id: str,
        cycle_id: str,
        ports: PortsBundle,
        project_id: str = "",
        correlation_context: CorrelationContext | None = None,
    ) -> ExecutionContext:
        """Factory method for creating execution context.

        Args:
            agent_id: Agent instance ID
            role_id: Agent role ID
            task_id: Current task ID
            cycle_id: Current cycle ID
            ports: PortsBundle from agent
            project_id: Current project ID (issue #109 — handlers that
                emit implementation_plan.yaml need authoritative
                project_id alongside cycle_id so they don't ask the LLM
                to invent it)
            correlation_context: Optional LangFuse correlation context

        Returns:
            ExecutionContext instance
        """
        return cls(
            agent_id=agent_id,
            role_id=role_id,
            task_id=task_id,
            cycle_id=cycle_id,
            ports=ports,
            project_id=project_id,
            correlation_context=correlation_context,
        )
