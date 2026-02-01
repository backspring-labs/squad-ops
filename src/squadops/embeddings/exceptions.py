"""Embeddings domain exceptions.

Part of SIP-0.8.8 Agent Migration.
"""


class EmbeddingError(Exception):
    """Base exception for embedding operations."""

    pass


class EmbeddingConnectionError(EmbeddingError):
    """Failed to connect to embedding provider."""

    pass


class EmbeddingTimeoutError(EmbeddingError):
    """Embedding request timed out."""

    pass
