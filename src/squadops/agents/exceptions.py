"""Agent domain exceptions.

Part of SIP-0.8.8 Agent Foundation.
"""


class AgentError(Exception):
    """Base exception for agent operations."""

    pass


class AgentNotFoundError(AgentError):
    """Agent not found."""

    pass


class AgentRoleNotFoundError(AgentError):
    """Agent role not found in registry."""

    pass
