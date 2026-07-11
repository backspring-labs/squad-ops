"""Agent domain models.

Frozen dataclasses for agent configuration and identity.
Part of SIP-0.8.8 Agent Foundation.
"""

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class AgentRole:
    """Immutable agent role definition.

    Defines the capabilities for an agent role.
    """

    role_id: str
    display_name: str
    description: str
    capabilities: tuple[str, ...] = ()


@dataclass(frozen=True)
class AgentConfig:
    """Immutable agent configuration.

    Configuration for instantiating an agent.
    """

    agent_id: str
    role_id: str
    settings: dict[str, Any] = field(default_factory=dict)


# Pre-defined roles (can be extended via registry)
LEAD_ROLE = AgentRole(
    role_id="lead",
    display_name="Lead Agent",
    description="Task orchestration and delegation",
)

DEV_ROLE = AgentRole(
    role_id="dev",
    display_name="Developer Agent",
    description="Code generation and implementation",
)

QA_ROLE = AgentRole(
    role_id="qa",
    display_name="QA Agent",
    description="Testing and validation",
)

STRAT_ROLE = AgentRole(
    role_id="strat",
    display_name="Strategy Agent",
    description="Strategic planning and analysis",
)

DATA_ROLE = AgentRole(
    role_id="data",
    display_name="Data Agent",
    description="Analytics and data processing",
)

BUILDER_ROLE = AgentRole(
    role_id="builder",
    display_name="Builder Agent",
    description="Artifact production from approved plans",
)

# Role registry
DEFAULT_ROLES = {
    "lead": LEAD_ROLE,
    "dev": DEV_ROLE,
    "qa": QA_ROLE,
    "strat": STRAT_ROLE,
    "data": DATA_ROLE,
    "builder": BUILDER_ROLE,
}
