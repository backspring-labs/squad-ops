"""Tasks adapter factory.

Factory function for creating task registry adapters.
Part of SIP-0.8.7 Infrastructure Ports Migration.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from adapters.tasks.prefect import PrefectTaskAdapter
from adapters.tasks.sql import SQLTaskAdapter
from squadops.ports.tasks.registry import TaskRegistryPort

if TYPE_CHECKING:
    from squadops.core.secret_manager import SecretManager


def create_task_registry_provider(
    provider: str = "sql",
    secret_manager: SecretManager | None = None,
    connection_string: str = "",
    **config,
) -> TaskRegistryPort:
    """Create a task registry provider.

    Args:
        provider: Provider name ("sql", "prefect")
        secret_manager: Optional secret manager for resolving secret:// refs
        connection_string: Database connection string (may be secret:// ref)
        **config: Additional provider-specific configuration

    Returns:
        TaskRegistryPort implementation

    Raises:
        ValueError: If provider is unknown
    """
    # Resolve secret:// refs via SecretManager (SIP §7.6)
    if secret_manager and connection_string.startswith("secret://"):
        connection_string = secret_manager.resolve(connection_string[9:])

    if provider == "sql":
        if not connection_string:
            raise ValueError("connection_string is required for SQL provider")
        return SQLTaskAdapter(connection_string=connection_string, **config)

    if provider == "prefect":
        # Stub - raises NotImplementedError on all methods
        return PrefectTaskAdapter(**config)

    raise ValueError(f"Unknown task registry provider: {provider}")
