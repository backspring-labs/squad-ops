"""SquadOps - Multi-agent orchestration framework.

A hexagonal architecture (ports & adapters) framework for
orchestrating AI agent squads in software development workflows.

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
        task_type="governance.review",
        source_agent="user",
        inputs={"description": "Review the delivered artifacts"},
    )
    result = await system.task_service.execute_task(request)
"""

from squadops._version import resolve_version as _resolve_version

__version__ = _resolve_version()

# Core exports for quick access
from squadops.agents import (
    BaseAgent,
    PortsBundle,
)
from squadops.api import (
    AgentService,
    TaskRequestDTO,
    TaskResponseDTO,
    TaskResultDTO,
    TaskService,
)
from squadops.bootstrap import (
    SquadOpsSystem,
    SystemConfig,
    create_handler_registry,
    create_orchestrator,
    create_system,
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
    "create_handler_registry",
    "SystemConfig",
    "SquadOpsSystem",
    # Agents
    "BaseAgent",
    "PortsBundle",
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
