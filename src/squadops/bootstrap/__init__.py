"""SquadOps Bootstrap - System initialization and configuration.

Provides factory functions for creating fully-configured system components:
- Handler registries with all handlers auto-registered
- Orchestrators ready for task execution

Part of SIP-0.8.8 Phase 7.
"""

from squadops.bootstrap.handlers import (
    create_handler_registry,
    get_all_handlers,
)
from squadops.bootstrap.system import (
    SquadOpsSystem,
    SystemConfig,
    create_orchestrator,
    create_system,
)

__all__ = [
    # Handler bootstrap
    "create_handler_registry",
    "get_all_handlers",
    # System bootstrap
    "create_orchestrator",
    "create_system",
    "SystemConfig",
    "SquadOpsSystem",
]
