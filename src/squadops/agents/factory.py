"""AgentFactory for dependency-injected agent creation.

Provides centralized agent instantiation with full port injection.

Part of SIP-0.8.8 Agent Foundation.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from squadops.agents.base import BaseAgent
from squadops.agents.exceptions import AgentRoleNotFoundError
from squadops.agents.models import DEFAULT_ROLES, AgentConfig, AgentRole

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


class AgentFactory:
    """Factory for creating agents with dependency injection.

    Manages agent type registration and instantiation with full port injection.
    Ensures consistent agent creation with all required dependencies.
    """

    def __init__(
        self,
        *,
        llm: LLMPort,
        memory: MemoryPort,
        prompt_service: PromptService,
        queue: QueuePort,
        metrics: MetricsPort,
        events: EventPort,
        filesystem: FileSystemPort,
        skill_registry: SkillRegistry | None = None,
    ) -> None:
        """Initialize factory with injected ports.

        Args:
            llm: LLM provider port
            memory: Memory storage port
            prompt_service: Prompt assembly service
            queue: Message queue port
            metrics: Metrics collection port
            events: Event/tracing port
            filesystem: Filesystem operations port
            skill_registry: Optional shared skill registry
        """
        self._llm = llm
        self._memory = memory
        self._prompt_service = prompt_service
        self._queue = queue
        self._metrics = metrics
        self._events = events
        self._filesystem = filesystem
        self._skill_registry = skill_registry

        # Agent type registry (role_id -> agent class)
        self._agent_types: dict[str, type[BaseAgent]] = {}

        # Role registry (can be extended beyond defaults)
        self._roles: dict[str, AgentRole] = dict(DEFAULT_ROLES)

        logger.info("agent_factory_initialized")

    def register_agent_type(
        self,
        role_id: str,
        agent_class: type[BaseAgent],
    ) -> None:
        """Register an agent class for a role.

        Args:
            role_id: Role identifier
            agent_class: Agent class to use for this role

        Raises:
            ValueError: If role_id already registered
        """
        if role_id in self._agent_types:
            raise ValueError(f"Agent type for role '{role_id}' already registered")
        self._agent_types[role_id] = agent_class
        logger.info(
            "agent_type_registered",
            extra={"role_id": role_id, "class": agent_class.__name__},
        )

    def register_role(self, role: AgentRole) -> None:
        """Register a custom role definition.

        Args:
            role: AgentRole to register

        Raises:
            ValueError: If role_id already registered
        """
        if role.role_id in self._roles:
            raise ValueError(f"Role '{role.role_id}' already registered")
        self._roles[role.role_id] = role
        logger.info("role_registered", extra={"role_id": role.role_id})

    def get_role(self, role_id: str) -> AgentRole:
        """Get a role definition by ID.

        Args:
            role_id: Role identifier

        Returns:
            AgentRole definition

        Raises:
            AgentRoleNotFoundError: If role not found
        """
        role = self._roles.get(role_id)
        if role is None:
            raise AgentRoleNotFoundError(f"Role '{role_id}' not found in registry")
        return role

    def list_roles(self) -> list[str]:
        """List all registered role IDs.

        Returns:
            List of role identifiers
        """
        return list(self._roles.keys())

    def create(
        self,
        config: AgentConfig,
        **overrides: Any,
    ) -> BaseAgent:
        """Create an agent from configuration.

        Args:
            config: Agent configuration
            **overrides: Optional port overrides for testing

        Returns:
            Instantiated agent with injected ports

        Raises:
            AgentRoleNotFoundError: If role not found
            ValueError: If no agent class registered for role
        """
        # Validate role exists
        if config.role_id not in self._roles:
            raise AgentRoleNotFoundError(f"Role '{config.role_id}' not found in registry")

        # Get agent class (if registered) or use BaseAgent subclass requirement
        agent_class = self._agent_types.get(config.role_id)
        if agent_class is None:
            raise ValueError(
                f"No agent class registered for role '{config.role_id}'. "
                f"Use register_agent_type() to register an agent class."
            )

        # Build port kwargs with optional overrides
        port_kwargs = {
            "llm": overrides.get("llm", self._llm),
            "memory": overrides.get("memory", self._memory),
            "prompt_service": overrides.get("prompt_service", self._prompt_service),
            "queue": overrides.get("queue", self._queue),
            "metrics": overrides.get("metrics", self._metrics),
            "events": overrides.get("events", self._events),
            "filesystem": overrides.get("filesystem", self._filesystem),
            "skill_registry": overrides.get("skill_registry", self._skill_registry),
        }

        # Create agent
        agent = agent_class(
            agent_id=config.agent_id,
            role_id=config.role_id,
            **port_kwargs,
        )

        logger.info(
            "agent_created",
            extra={
                "agent_id": config.agent_id,
                "role_id": config.role_id,
                "class": agent_class.__name__,
            },
        )

        return agent

    def create_from_role(
        self,
        agent_id: str,
        role_id: str,
        **overrides: Any,
    ) -> BaseAgent:
        """Convenience method to create agent from role ID.

        Args:
            agent_id: Unique agent identifier
            role_id: Role identifier
            **overrides: Optional port overrides for testing

        Returns:
            Instantiated agent with injected ports
        """
        config = AgentConfig(
            agent_id=agent_id,
            role_id=role_id,
        )
        return self.create(config, **overrides)
