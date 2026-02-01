"""SquadOps Agent Foundation.

Provides the core agent infrastructure:
- BaseAgent with port injection
- PortsBundle for immutable port bundling
- AgentFactory for dependency-injected agent creation
- SkillRegistry for skill discovery and execution

Part of SIP-0.8.8.
"""
from squadops.agents.base import BaseAgent, PortsBundle
from squadops.agents.exceptions import (
    AgentError,
    AgentNotFoundError,
    AgentRoleNotFoundError,
    SkillContractViolation,
    SkillNotFoundError,
)
from squadops.agents.factory import AgentFactory
from squadops.agents.models import AgentConfig, AgentRole

__all__ = [
    # Core classes
    "BaseAgent",
    "PortsBundle",
    "AgentFactory",
    # Models
    "AgentConfig",
    "AgentRole",
    # Exceptions
    "AgentError",
    "AgentNotFoundError",
    "AgentRoleNotFoundError",
    "SkillContractViolation",
    "SkillNotFoundError",
]
