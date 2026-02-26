"""Tasks adapter factory.

Factory function for creating task registry adapters.
Part of SIP-0.8.7 Infrastructure Ports Migration.
Updated in SIP-0.8.8 with full PrefectTaskAdapter implementation.
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
    prefect_api_url: str | None = None,
    prefect_api_key: str | None = None,
    **config,
) -> TaskRegistryPort:
    """Create a task registry provider.

    Args:
        provider: Provider name ("sql", "prefect")
        secret_manager: Optional secret manager for resolving secret:// refs
        connection_string: Database connection string (may be secret:// ref)
        prefect_api_url: Optional Prefect API URL (for "prefect" provider)
        prefect_api_key: Optional Prefect API key (for "prefect" provider)
        **config: Additional provider-specific configuration

    Returns:
        TaskRegistryPort implementation

    Raises:
        ValueError: If provider is unknown or required config missing
    """
    # Resolve secret:// refs via SecretManager (SIP §7.6)
    if secret_manager and connection_string.startswith("secret://"):
        connection_string = secret_manager.resolve(connection_string[9:])

    if provider == "sql":
        if not connection_string:
            raise ValueError("connection_string is required for SQL provider")
        return SQLTaskAdapter(connection_string=connection_string, **config)

    if provider == "prefect":
        if not connection_string:
            raise ValueError("connection_string is required for Prefect provider")
        return PrefectTaskAdapter(
            connection_string=connection_string,
            secret_manager=secret_manager,
            prefect_api_url=prefect_api_url,
            prefect_api_key=prefect_api_key,
            **config,
        )

    raise ValueError(f"Unknown task registry provider: {provider}")
