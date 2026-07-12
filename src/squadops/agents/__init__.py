"""SquadOps Agent Foundation.

Provides the core agent infrastructure:
- BaseAgent with port injection
- PortsBundle for immutable port bundling

Part of SIP-0.8.8.
"""

from squadops.agents.base import BaseAgent, PortsBundle
from squadops.agents.exceptions import (
    AgentError,
    AgentNotFoundError,
    AgentRoleNotFoundError,
)
from squadops.agents.models import AgentConfig, AgentRole

__all__ = [
    # Core classes
    "BaseAgent",
    "PortsBundle",
    # Models
    "AgentConfig",
    "AgentRole",
    # Exceptions
    "AgentError",
    "AgentNotFoundError",
    "AgentRoleNotFoundError",
]
