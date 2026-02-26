"""Embeddings adapters.

Concrete implementations of EmbeddingsPort.
Part of SIP-0.8.8 Agent Migration.
"""

from adapters.embeddings.factory import create_embeddings_provider
from adapters.embeddings.ollama import OllamaEmbeddingsAdapter

__all__ = [
    "OllamaEmbeddingsAdapter",
    "create_embeddings_provider",
]
