"""SquadOps - Multi-agent orchestration framework.

A hexagonal architecture (ports & adapters) framework for
orchestrating AI agent squads in software development workflows.
``docs/architecture/overview.md`` maps every package.
"""

from squadops._version import resolve_version as _resolve_version

__version__ = _resolve_version()

# Core exports for quick access
from squadops.agents import (
    BaseAgent,
    PortsBundle,
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
    # Tasks
    "TaskEnvelope",
    "TaskResult",
]
