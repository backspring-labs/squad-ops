"""ExecutionContext for capability handler execution.

Provides handlers with access to ports and task/cycle metadata.

Part of SIP-0.8.8 Phase 5.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING

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
        role_id: Role of the agent
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
