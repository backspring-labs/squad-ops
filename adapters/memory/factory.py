"""Memory adapter factory.

Factory function for creating memory adapters.
Part of SIP-0.8.7 Infrastructure Ports Migration.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Awaitable, Callable

from adapters.memory.lancedb import LanceDBAdapter
from squadops.ports.memory.store import MemoryPort

if TYPE_CHECKING:
    from squadops.core.secret_manager import SecretManager

# Type alias for async embedding function
EmbedFn = Callable[[str], Awaitable[list[float]]]


def create_memory_provider(
    provider: str = "lancedb",
    secret_manager: SecretManager | None = None,
    embed_fn: EmbedFn | None = None,
    db_path: str = "./data/memory.lancedb",
    **config,
) -> MemoryPort:
    """Create a memory provider.

    Args:
        provider: Provider name ("lancedb")
        secret_manager: Optional secret manager for resolving secret:// refs
        embed_fn: Async embedding function. If None, uses default Ollama embeddings.
        db_path: Path to database (may be secret:// ref for credentials)
        **config: Additional provider-specific configuration

    Returns:
        MemoryPort implementation

    Raises:
        ValueError: If provider is unknown
    """
    # Resolve secret:// refs via SecretManager (SIP §7.6)
    if secret_manager and db_path.startswith("secret://"):
        db_path = secret_manager.resolve(db_path[9:])

    if provider == "lancedb":
        return LanceDBAdapter(
            db_path=db_path,
            embed_fn=embed_fn,
            **config,
        )

    raise ValueError(f"Unknown memory provider: {provider}")
