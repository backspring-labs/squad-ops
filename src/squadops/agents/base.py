"""BaseAgent with full port injection.

Provides the core agent base class with dependency-injected ports.
Part of SIP-0.8.8 Agent Foundation.
"""
from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from squadops.tasks.models import TaskEnvelope, TaskResult

if TYPE_CHECKING:
    from squadops.agents.skills.registry import SkillRegistry
    from squadops.ports.comms.queue import QueuePort
    from squadops.ports.llm.provider import LLMPort
    from squadops.ports.memory.store import MemoryPort
    from squadops.ports.prompts.service import PromptService
    from squadops.ports.telemetry.events import EventPort
    from squadops.ports.telemetry.metrics import MetricsPort
    from squadops.ports.tools.filesystem import FileSystemPort

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class PortsBundle:
    """Immutable bundle of all ports for easy passing to contexts.

    This bundle provides a single object that can be passed to skill contexts
    and other components that need access to multiple ports.
    """

    llm: LLMPort
    memory: MemoryPort
    prompt_service: PromptService
    queue: QueuePort
    metrics: MetricsPort
    events: EventPort
    filesystem: FileSystemPort


class BaseAgent(ABC):
    """Base agent with full port injection.

    This class provides the foundation for all agents with:
    - Dependency-injected access to all required ports
    - Standardized identity (agent_id, role_id)
    - Lifecycle hooks (on_agent_start, on_agent_stop, etc.)
    - Task handling interface
    - Skill registry integration

    Subclasses must implement handle_task() for task processing.
    """

    ROLE_ID: str = "base"  # Override in subclasses

    def __init__(
        self,
        *,
        agent_id: str,
        role_id: str | None = None,
        llm: LLMPort,
        memory: MemoryPort,
        prompt_service: PromptService,
        queue: QueuePort,
        metrics: MetricsPort,
        events: EventPort,
        filesystem: FileSystemPort,
        skill_registry: SkillRegistry | None = None,
    ):
        """Initialize agent with injected ports.

        Args:
            agent_id: Unique agent instance identifier
            role_id: Agent role (defaults to class ROLE_ID)
            llm: LLM provider port
            memory: Memory storage port
            prompt_service: Prompt assembly service
            queue: Message queue port
            metrics: Metrics collection port
            events: Event/tracing port
            filesystem: Filesystem operations port
            skill_registry: Optional skill registry for skill execution
        """
        self._agent_id = agent_id
        self._role_id = role_id or self.ROLE_ID

        # Store individual ports for property access
        self._llm = llm
        self._memory = memory
        self._prompt_service = prompt_service
        self._queue = queue
        self._metrics = metrics
        self._events = events
        self._filesystem = filesystem

        # Store bundle for easy context building
        self._ports = PortsBundle(
            llm=llm,
            memory=memory,
            prompt_service=prompt_service,
            queue=queue,
            metrics=metrics,
            events=events,
            filesystem=filesystem,
        )

        # Skill registry (optional)
        self._skill_registry = skill_registry

        logger.info(
            "agent_initialized",
            extra={"agent_id": self._agent_id, "role_id": self._role_id},
        )

    # Identity properties (read-only)

    @property
    def agent_id(self) -> str:
        """Unique agent instance identifier."""
        return self._agent_id

    @property
    def role_id(self) -> str:
        """Agent role identifier."""
        return self._role_id

    # Port accessors (read-only)

    @property
    def llm(self) -> LLMPort:
        """LLM provider port."""
        return self._llm

    @property
    def memory(self) -> MemoryPort:
        """Memory storage port."""
        return self._memory

    @property
    def prompt_service(self) -> PromptService:
        """Prompt assembly service."""
        return self._prompt_service

    @property
    def queue(self) -> QueuePort:
        """Message queue port."""
        return self._queue

    @property
    def metrics(self) -> MetricsPort:
        """Metrics collection port."""
        return self._metrics

    @property
    def events(self) -> EventPort:
        """Event/tracing port."""
        return self._events

    @property
    def filesystem(self) -> FileSystemPort:
        """Filesystem operations port."""
        return self._filesystem

    @property
    def ports(self) -> PortsBundle:
        """Bundle of all ports."""
        return self._ports

    @property
    def skill_registry(self) -> SkillRegistry | None:
        """Skill registry for skill execution."""
        return self._skill_registry

    # Lifecycle hooks

    async def on_agent_start(self) -> None:
        """Called when agent starts.

        Override in subclasses for custom initialization.
        """
        logger.debug("agent_start", extra={"agent_id": self._agent_id})

    async def on_agent_stop(self) -> None:
        """Called when agent stops.

        Override in subclasses for custom cleanup.
        """
        logger.debug("agent_stop", extra={"agent_id": self._agent_id})

    async def on_cycle_start(self, cycle_id: str) -> None:
        """Called when a new execution cycle starts.

        Args:
            cycle_id: The cycle identifier
        """
        logger.debug(
            "cycle_start",
            extra={"agent_id": self._agent_id, "cycle_id": cycle_id},
        )

    async def on_cycle_end(self, cycle_id: str) -> None:
        """Called when an execution cycle ends.

        Args:
            cycle_id: The cycle identifier
        """
        logger.debug(
            "cycle_end",
            extra={"agent_id": self._agent_id, "cycle_id": cycle_id},
        )

    async def on_pulse_start(self, pulse_id: str) -> None:
        """Called when a new pulse starts.

        Args:
            pulse_id: The pulse identifier
        """
        logger.debug(
            "pulse_start",
            extra={"agent_id": self._agent_id, "pulse_id": pulse_id},
        )

    async def on_pulse_end(self, pulse_id: str) -> None:
        """Called when a pulse ends.

        Args:
            pulse_id: The pulse identifier
        """
        logger.debug(
            "pulse_end",
            extra={"agent_id": self._agent_id, "pulse_id": pulse_id},
        )

    # Task handling

    @abstractmethod
    async def handle_task(self, envelope: TaskEnvelope) -> TaskResult:
        """Process incoming task.

        Subclasses must implement this method to handle tasks.

        Args:
            envelope: Task envelope with task details

        Returns:
            Task result with execution outcome
        """
        ...

    # Utility methods

    def get_system_prompt(self) -> str:
        """Get assembled system prompt for this agent's role.

        Uses the injected PromptService to assemble a deterministic,
        versioned prompt based on the agent's role.

        Returns:
            Assembled prompt content, or empty string if unavailable.
        """
        if self._prompt_service is None:
            return ""
        assembled = self._prompt_service.get_system_prompt(self._role_id)
        return assembled.content

    async def health(self) -> dict[str, Any]:
        """Check agent health status.

        Returns:
            Dictionary with health information
        """
        llm_health = await self._llm.health()

        return {
            "healthy": llm_health.get("healthy", False),
            "agent_id": self._agent_id,
            "role_id": self._role_id,
            "llm": llm_health,
        }
