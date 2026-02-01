"""SquadOps Bootstrap - System initialization and configuration.

Provides factory functions for creating fully-configured system components:
- Skill registries with all skills auto-registered
- Handler registries with all handlers auto-registered
- Orchestrators ready for task execution

Part of SIP-0.8.8 Phase 7.
"""
from squadops.bootstrap.skills import (
    create_skill_registry,
    get_all_skills,
    get_skills_for_role,
)
from squadops.bootstrap.handlers import (
    create_handler_registry,
    get_all_handlers,
)
from squadops.bootstrap.system import (
    create_orchestrator,
    create_system,
    SystemConfig,
    SquadOpsSystem,
)

__all__ = [
    # Skill bootstrap
    "create_skill_registry",
    "get_all_skills",
    "get_skills_for_role",
    # Handler bootstrap
    "create_handler_registry",
    "get_all_handlers",
    # System bootstrap
    "create_orchestrator",
    "create_system",
    "SystemConfig",
    "SquadOpsSystem",
]
