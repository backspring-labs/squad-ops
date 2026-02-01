"""Embeddings domain.

Part of SIP-0.8.8 Agent Migration.
"""
from squadops.embeddings.exceptions import (
    EmbeddingConnectionError,
    EmbeddingError,
    EmbeddingTimeoutError,
)

__all__ = [
    "EmbeddingError",
    "EmbeddingConnectionError",
    "EmbeddingTimeoutError",
]
