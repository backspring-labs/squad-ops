"""Handler bootstrap - Auto-registration of capability handlers.

Provides factory functions for creating handler registries
with all handlers auto-discovered and registered.

Part of SIP-0.8.8 Phase 7.
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from squadops.orchestration.handler_registry import HandlerRegistry

# Import handlers
from squadops.capabilities.handlers.governance import (
    TaskAnalysisHandler,
    TaskDelegationHandler,
)
from squadops.capabilities.handlers.development import (
    CodeGenerationHandler,
    CodeAnalysisHandler,
)
from squadops.capabilities.handlers.qa import (
    TestExecutionHandler,
    ValidationHandler,
)
from squadops.capabilities.handlers.data import (
    DataAnalysisHandler,
    MetricsCollectionHandler,
)
from squadops.capabilities.handlers.warmboot import (
    WarmbootHandler,
    ContextSyncHandler,
)

if TYPE_CHECKING:
    from squadops.capabilities.handlers.base import CapabilityHandler

logger = logging.getLogger(__name__)


# All handler classes with their role assignments
HANDLER_CONFIGS: list[tuple[type[CapabilityHandler], tuple[str, ...]]] = [
    # Governance handlers (lead role)
    (TaskAnalysisHandler, ("lead",)),
    (TaskDelegationHandler, ("lead",)),
    # Development handlers (dev role)
    (CodeGenerationHandler, ("dev",)),
    (CodeAnalysisHandler, ("dev", "lead")),  # Lead can also review code
    # QA handlers (qa role)
    (TestExecutionHandler, ("qa",)),
    (ValidationHandler, ("qa", "lead")),  # Lead can validate too
    # Data handlers (data role)
    (DataAnalysisHandler, ("data",)),
    (MetricsCollectionHandler, ("data",)),
    # Warmboot handlers (all roles can warmboot)
    (WarmbootHandler, ("lead", "dev", "qa", "strat", "data")),
    (ContextSyncHandler, ("lead", "dev", "qa", "strat", "data")),
]


def get_all_handlers() -> list[tuple[type[CapabilityHandler], tuple[str, ...]]]:
    """Get all handler classes with their role assignments.

    Returns:
        List of (handler_class, roles) tuples
    """
    return list(HANDLER_CONFIGS)


def create_handler_registry(
    roles: list[str] | None = None,
) -> HandlerRegistry:
    """Create a handler registry with auto-registered handlers.

    Args:
        roles: Optional list of roles to include handlers for.
               If None, includes all handlers.

    Returns:
        HandlerRegistry with handlers registered
    """
    registry = HandlerRegistry()

    for handler_class, handler_roles in HANDLER_CONFIGS:
        # Filter by roles if specified
        if roles is not None:
            if not any(r in roles for r in handler_roles):
                continue

        try:
            handler = handler_class()
            registry.register(handler, roles=handler_roles)
            logger.debug(
                f"Registered handler: {handler.capability_id} for roles {handler_roles}"
            )
        except Exception as e:
            logger.warning(f"Failed to register handler {handler_class}: {e}")

    logger.info(
        f"Created handler registry with {len(registry.list_capabilities())} handlers"
    )

    return registry
