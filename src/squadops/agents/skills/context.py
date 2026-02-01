"""SkillContext for port access during skill execution.

Provides skills with access to required ports while tracking
all port calls for execution evidence.

Part of SIP-0.8.8 Agent Foundation.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from squadops.agents.base import PortsBundle
    from squadops.ports.comms.queue import QueuePort
    from squadops.ports.llm.provider import LLMPort
    from squadops.ports.memory.store import MemoryPort
    from squadops.ports.prompts.service import PromptService
    from squadops.ports.telemetry.events import EventPort
    from squadops.ports.telemetry.metrics import MetricsPort
    from squadops.ports.tools.filesystem import FileSystemPort

logger = logging.getLogger(__name__)


@dataclass
class SkillContext:
    """Context provided to skills during execution.

    Provides controlled access to ports and tracks all port interactions
    for execution evidence generation.

    Attributes:
        agent_id: ID of the agent executing the skill
        role_id: Role of the agent
        task_id: ID of the current task
        cycle_id: ID of the current execution cycle
        ports: Bundle of all available ports
    """

    agent_id: str
    role_id: str
    task_id: str
    cycle_id: str
    ports: PortsBundle
    _port_calls: list[str] = field(default_factory=list)

    @classmethod
    def from_agent(
        cls,
        agent_id: str,
        role_id: str,
        task_id: str,
        cycle_id: str,
        ports: PortsBundle,
    ) -> SkillContext:
        """Create context from agent state.

        Args:
            agent_id: Agent instance ID
            role_id: Agent role ID
            task_id: Current task ID
            cycle_id: Current cycle ID
            ports: PortsBundle from agent

        Returns:
            SkillContext instance
        """
        return cls(
            agent_id=agent_id,
            role_id=role_id,
            task_id=task_id,
            cycle_id=cycle_id,
            ports=ports,
        )

    # Port accessors with call tracking

    @property
    def llm(self) -> LLMPort:
        """Get LLM port (tracks access)."""
        self._track_call("llm.access")
        return self.ports.llm

    @property
    def memory(self) -> MemoryPort:
        """Get memory port (tracks access)."""
        self._track_call("memory.access")
        return self.ports.memory

    @property
    def prompt_service(self) -> PromptService:
        """Get prompt service (tracks access)."""
        self._track_call("prompt_service.access")
        return self.ports.prompt_service

    @property
    def queue(self) -> QueuePort:
        """Get queue port (tracks access)."""
        self._track_call("queue.access")
        return self.ports.queue

    @property
    def metrics(self) -> MetricsPort:
        """Get metrics port (tracks access)."""
        self._track_call("metrics.access")
        return self.ports.metrics

    @property
    def events(self) -> EventPort:
        """Get events port (tracks access)."""
        self._track_call("events.access")
        return self.ports.events

    @property
    def filesystem(self) -> FileSystemPort:
        """Get filesystem port (tracks access)."""
        self._track_call("filesystem.access")
        return self.ports.filesystem

    # Call tracking

    def _track_call(self, call: str) -> None:
        """Track a port call for evidence generation.

        Args:
            call: Description of the port call
        """
        self._port_calls.append(call)

    def track_port_call(self, port: str, method: str, **kwargs: Any) -> None:
        """Explicitly track a port method call.

        Skills can call this to track specific port operations
        beyond simple property access.

        Args:
            port: Port name (e.g., "llm", "memory")
            method: Method name (e.g., "generate", "store")
            **kwargs: Additional call metadata
        """
        call_desc = f"{port}.{method}"
        if kwargs:
            call_desc += f"({', '.join(f'{k}={v}' for k, v in kwargs.items())})"
        self._port_calls.append(call_desc)
        logger.debug(
            "port_call_tracked",
            extra={"call": call_desc, "task_id": self.task_id},
        )

    def get_port_calls(self) -> list[str]:
        """Get list of all tracked port calls.

        Returns:
            List of port call descriptions
        """
        return list(self._port_calls)

    def clear_port_calls(self) -> None:
        """Clear tracked port calls (for testing)."""
        self._port_calls.clear()
