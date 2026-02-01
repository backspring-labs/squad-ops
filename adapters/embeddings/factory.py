"""Embeddings adapter factory.

Factory function for creating embeddings adapters with secret resolution.
Part of SIP-0.8.8 Agent Migration.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from adapters.embeddings.ollama import OllamaEmbeddingsAdapter
from squadops.ports.embeddings.provider import EmbeddingsPort

if TYPE_CHECKING:
    from squadops.core.secret_manager import SecretManager


def create_embeddings_provider(
    provider: str = "ollama",
    secret_manager: SecretManager | None = None,
    base_url: str = "http://localhost:11434",
    model: str = "nomic-embed-text",
    timeout_seconds: float = 30.0,
    **config,
) -> EmbeddingsPort:
    """Create an embeddings provider.

    Args:
        provider: Provider name ("ollama")
        secret_manager: Optional secret manager for resolving secret:// refs
        base_url: Base URL for the embeddings server (may be secret:// ref)
        model: Embedding model to use
        timeout_seconds: Request timeout
        **config: Additional provider-specific configuration

    Returns:
        EmbeddingsPort implementation

    Raises:
        ValueError: If provider is unknown
    """
    # Resolve secret:// refs via SecretManager (SIP §7.6)
    if secret_manager and base_url.startswith("secret://"):
        base_url = secret_manager.resolve(base_url[9:])

    if provider == "ollama":
        return OllamaEmbeddingsAdapter(
            base_url=base_url,
            model=model,
            timeout_seconds=timeout_seconds,
        )

    raise ValueError(f"Unknown embeddings provider: {provider}")
