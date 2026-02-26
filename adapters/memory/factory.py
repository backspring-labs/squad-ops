"""Memory adapter factory.

Factory function for creating memory adapters.
Part of SIP-0.8.7 Infrastructure Ports Migration.
Updated in SIP-0.8.8 to use EmbeddingsPort instead of embed_fn seam.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from adapters.memory.lancedb import LanceDBAdapter
from squadops.ports.memory.store import MemoryPort

if TYPE_CHECKING:
    from squadops.core.secret_manager import SecretManager

    from squadops.ports.embeddings.provider import EmbeddingsPort


def create_memory_provider(
    provider: str = "lancedb",
    secret_manager: SecretManager | None = None,
    embeddings: EmbeddingsPort | None = None,
    db_path: str = "./data/memory.lancedb",
    **config,
) -> MemoryPort:
    """Create a memory provider.

    Args:
        provider: Provider name ("lancedb")
        secret_manager: Optional secret manager for resolving secret:// refs
        embeddings: EmbeddingsPort for generating vectors. If None, creates default Ollama adapter.
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

    # Create default embeddings provider if not provided
    if embeddings is None:
        from adapters.embeddings.factory import create_embeddings_provider

        embeddings = create_embeddings_provider(
            provider="ollama",
            secret_manager=secret_manager,
        )

    if provider == "lancedb":
        return LanceDBAdapter(
            db_path=db_path,
            embeddings=embeddings,
            **config,
        )

    raise ValueError(f"Unknown memory provider: {provider}")
