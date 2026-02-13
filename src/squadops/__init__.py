"""SquadOps - Multi-agent orchestration framework.

A hexagonal architecture (ports & adapters) framework for
orchestrating AI agent squads in software development workflows.

Framework Version: 0.9.6
SIP-0.8.8 Agent Migration + SIP-0.8.9 Test Suite Modernization complete.

Quick Start:
    from squadops.bootstrap import create_system

    system = create_system(
        llm=llm_adapter,
        memory=memory_adapter,
        prompt_service=prompt_service,
        queue=queue_adapter,
        metrics=metrics_adapter,
        events=events_adapter,
        filesystem=filesystem_adapter,
    )

    # Execute a task
    from squadops.api import TaskRequestDTO
    request = TaskRequestDTO(
        task_type="governance.task_analysis",
        source_agent="user",
        inputs={"description": "Build a REST API"},
    )
    result = await system.task_service.execute_task(request)
"""

__version__ = "0.9.6"

# Core exports for quick access
from squadops.bootstrap import (
    create_system,
    create_orchestrator,
    create_skill_registry,
    create_handler_registry,
    SystemConfig,
    SquadOpsSystem,
)
from squadops.agents import (
    BaseAgent,
    PortsBundle,
    AgentFactory,
)
from squadops.api import (
    TaskRequestDTO,
    TaskResponseDTO,
    TaskResultDTO,
    TaskService,
    AgentService,
)
from squadops.tasks.models import (
    TaskEnvelope,
    TaskResult,
)

__all__ = [
    # Version
    "__version__",
    # Bootstrap
    "create_system",
    "create_orchestrator",
    "create_skill_registry",
    "create_handler_registry",
    "SystemConfig",
    "SquadOpsSystem",
    # Agents
    "BaseAgent",
    "PortsBundle",
    "AgentFactory",
    # API
    "TaskRequestDTO",
    "TaskResponseDTO",
    "TaskResultDTO",
    "TaskService",
    "AgentService",
    # Tasks
    "TaskEnvelope",
    "TaskResult",
]
