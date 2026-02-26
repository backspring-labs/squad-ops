"""Embeddings port interface.

Abstract base class for embedding provider adapters.
Part of SIP-0.8.8 Agent Migration.
"""

from abc import ABC, abstractmethod
from typing import Any


class EmbeddingsPort(ABC):
    """Port interface for embedding providers.

    Adapters must implement embed, embed_batch, dimensions, and health.
    Replaces the EmbedFn callable seam from SIP-0.8.7.
    """

    @abstractmethod
    async def embed(self, text: str) -> list[float]:
        """Generate embedding vector for text.

        Args:
            text: The text to embed

        Returns:
            Embedding vector as list of floats

        Raises:
            EmbeddingConnectionError: Failed to connect to provider
            EmbeddingTimeoutError: Request timed out
            EmbeddingError: General embedding failure
        """
        ...

    @abstractmethod
    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for multiple texts.

        Args:
            texts: List of texts to embed

        Returns:
            List of embedding vectors

        Raises:
            EmbeddingConnectionError: Failed to connect to provider
            EmbeddingTimeoutError: Request timed out
            EmbeddingError: General embedding failure
        """
        ...

    @abstractmethod
    def dimensions(self) -> int:
        """Return embedding dimensions for this model.

        Returns:
            Number of dimensions in embedding vectors
        """
        ...

    @abstractmethod
    async def health(self) -> dict[str, Any]:
        """Check provider health.

        Returns:
            Health status dictionary with at least {"healthy": bool}
        """
        ...
