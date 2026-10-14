"""Memory adapter factory.

Factory function for creating memory adapters.
Part of SIP-0.8.7 Infrastructure Ports Migration.
Updated in SIP-0.8.8 to use EmbeddingsPort instead of embed_fn seam.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from adapters.memory.dormant import DormantMemoryPort
from adapters.memory.lancedb import LanceDBAdapter
from squadops.ports.memory.store import MemoryPort

if TYPE_CHECKING:
    from squadops.core.secret_manager import SecretManager

    from squadops.ports.embeddings.provider import EmbeddingsPort


def create_memory_provider(
    provider: str,
    *,
    embeddings: EmbeddingsPort | None = None,
    db_path: str | None = None,
    secret_manager: SecretManager | None = None,
    **config,
) -> MemoryPort:
    """Create a memory provider.

    Args:
        provider: ``"dormant"`` (what the agents hold, SIP-0110 §A.4.3, #2174) or ``"lancedb"``
        embeddings: EmbeddingsPort for generating vectors. Required by ``lancedb``: no embedder is
            built at an address nobody set (#2174).
        db_path: Path to database (may be secret:// ref). Required by ``lancedb``.
        secret_manager: Optional secret manager for resolving secret:// refs
        **config: Additional provider-specific configuration

    Returns:
        MemoryPort implementation

    Raises:
        ValueError: If provider is unknown, or ``lancedb`` is missing what it requires
    """
    if provider == "dormant":
        return DormantMemoryPort()

    if provider == "lancedb":
        if embeddings is None or db_path is None:
            raise ValueError("the lancedb memory provider requires its embeddings and its db_path")
        # Resolve secret:// refs via SecretManager (SIP §7.6)
        if secret_manager and db_path.startswith("secret://"):
            db_path = secret_manager.resolve(db_path[9:])
        return LanceDBAdapter(
            db_path=db_path,
            embeddings=embeddings,
            **config,
        )

    raise ValueError(f"Unknown memory provider: {provider}")
