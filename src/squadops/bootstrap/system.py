"""System bootstrap - Complete system initialization.

Provides factory functions for creating a fully-configured
SquadOps system with all components wired together.

Part of SIP-0.8.8 Phase 7.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from squadops.agents.base import PortsBundle
from squadops.api.service import AgentService, TaskService
from squadops.bootstrap.handlers import create_handler_registry
from squadops.bootstrap.skills import create_skill_registry
from squadops.orchestration.orchestrator import AgentOrchestrator

if TYPE_CHECKING:
    from squadops.agents.skills.registry import SkillRegistry
    from squadops.orchestration.handler_registry import HandlerRegistry
    from squadops.ports.comms.messaging import MessagingPort
    from squadops.ports.comms.queue import QueuePort
    from squadops.ports.llm.provider import LLMPort
    from squadops.ports.memory.store import MemoryPort
    from squadops.ports.prompts.service import PromptService
    from squadops.ports.telemetry.events import EventPort
    from squadops.ports.telemetry.llm_observability import LLMObservabilityPort
    from squadops.ports.telemetry.metrics import MetricsPort
    from squadops.ports.tools.filesystem import FileSystemPort
    from squadops.prompts.renderer import RequestTemplateRenderer

logger = logging.getLogger(__name__)


@dataclass
class SystemConfig:
    """Configuration for SquadOps system initialization.

    Attributes:
        roles: Roles to enable (None = all)
        enable_warmboot: Whether to enable warmboot handlers
        default_timeout: Default task timeout in seconds
    """

    roles: list[str] | None = None
    enable_warmboot: bool = True
    default_timeout: float = 300.0
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class SquadOpsSystem:
    """Fully configured SquadOps system.

    Contains all components needed for operation:
    - Skill registry with all skills
    - Handler registry with all handlers
    - Orchestrator for task coordination
    - API services for external access

    Attributes:
        skill_registry: Registry of all skills
        handler_registry: Registry of all handlers
        orchestrator: AgentOrchestrator for coordination
        task_service: TaskService for API access
        agent_service: AgentService for API access
        ports: PortsBundle for port access
        config: System configuration
    """

    skill_registry: SkillRegistry
    handler_registry: HandlerRegistry
    orchestrator: AgentOrchestrator
    task_service: TaskService
    agent_service: AgentService
    ports: PortsBundle
    config: SystemConfig

    async def health(self) -> dict[str, Any]:
        """Check system health.

        Returns:
            Health status dictionary
        """
        orchestrator_health = await self.orchestrator.health_check()

        return {
            "status": orchestrator_health["status"],
            "skills": len(self.skill_registry.list_skills()),
            "handlers": len(self.handler_registry.list_capabilities()),
            "orchestrator": orchestrator_health,
        }

    async def shutdown(self) -> None:
        """Gracefully shutdown the system."""
        logger.info("Shutting down SquadOps system")
        # Future: Add cleanup logic for ports, connections, etc.


def create_orchestrator(
    ports: PortsBundle,
    skill_registry: SkillRegistry | None = None,
    handler_registry: HandlerRegistry | None = None,
    roles: list[str] | None = None,
) -> AgentOrchestrator:
    """Create a configured AgentOrchestrator.

    Args:
        ports: PortsBundle with all required ports
        skill_registry: Optional pre-configured skill registry
        handler_registry: Optional pre-configured handler registry
        roles: Roles to enable (used if registries not provided)

    Returns:
        Configured AgentOrchestrator
    """
    # Create registries if not provided
    if skill_registry is None:
        skill_registry = create_skill_registry(roles=roles)

    if handler_registry is None:
        handler_registry = create_handler_registry(roles=roles)

    # Create orchestrator
    orchestrator = AgentOrchestrator(
        handler_registry=handler_registry,
        skill_registry=skill_registry,
        ports=ports,
    )

    logger.info(
        "Created orchestrator",
        extra={
            "skills": len(skill_registry.list_skills()),
            "handlers": len(handler_registry.list_capabilities()),
        },
    )

    return orchestrator


def create_system(
    *,
    llm: LLMPort,
    memory: MemoryPort,
    prompt_service: PromptService,
    queue: QueuePort,
    metrics: MetricsPort,
    events: EventPort,
    filesystem: FileSystemPort,
    llm_observability: LLMObservabilityPort | None = None,
    request_renderer: RequestTemplateRenderer | None = None,
    messaging: MessagingPort | None = None,
    config: SystemConfig | None = None,
) -> SquadOpsSystem:
    """Create a fully configured SquadOps system.

    This is the main entry point for initializing SquadOps.
    It creates all registries, wires up the orchestrator,
    and returns a ready-to-use system.

    Args:
        llm: LLM provider port
        memory: Memory storage port
        prompt_service: Prompt assembly service
        queue: Message queue port
        metrics: Metrics collection port
        events: Event/tracing port
        filesystem: Filesystem operations port
        config: Optional system configuration

    Returns:
        Fully configured SquadOpsSystem

    Example:
        system = create_system(
            llm=llm_adapter,
            memory=memory_adapter,
            prompt_service=prompt_service,
            queue=queue_adapter,
            metrics=metrics_adapter,
            events=events_adapter,
            filesystem=filesystem_adapter,
        )

        result = await system.task_service.execute_task(request)
    """
    config = config or SystemConfig()

    # Create ports bundle
    ports = PortsBundle(
        llm=llm,
        memory=memory,
        prompt_service=prompt_service,
        queue=queue,
        metrics=metrics,
        events=events,
        filesystem=filesystem,
        llm_observability=llm_observability,
        request_renderer=request_renderer,
        messaging=messaging,
    )

    # Create registries
    skill_registry = create_skill_registry(roles=config.roles)
    handler_registry = create_handler_registry(roles=config.roles)

    # Create orchestrator
    orchestrator = AgentOrchestrator(
        handler_registry=handler_registry,
        skill_registry=skill_registry,
        ports=ports,
        llm_observability=llm_observability,
    )

    # Create API services
    task_service = TaskService(orchestrator)
    agent_service = AgentService(orchestrator)

    logger.info(
        "Created SquadOps system",
        extra={
            "skills": len(skill_registry.list_skills()),
            "handlers": len(handler_registry.list_capabilities()),
            "roles": config.roles,
        },
    )

    return SquadOpsSystem(
        skill_registry=skill_registry,
        handler_registry=handler_registry,
        orchestrator=orchestrator,
        task_service=task_service,
        agent_service=agent_service,
        ports=ports,
        config=config,
    )
