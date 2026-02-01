"""Ollama embeddings adapter.

Production adapter for local Ollama embeddings.
Part of SIP-0.8.8 Agent Migration.
"""
from __future__ import annotations

from typing import Any

import httpx

from squadops.embeddings.exceptions import (
    EmbeddingConnectionError,
    EmbeddingError,
    EmbeddingTimeoutError,
)
from squadops.ports.embeddings.provider import EmbeddingsPort


# Model dimensions for known Ollama embedding models
MODEL_DIMENSIONS: dict[str, int] = {
    "nomic-embed-text": 768,
    "mxbai-embed-large": 1024,
    "all-minilm": 384,
    "snowflake-arctic-embed": 1024,
}

DEFAULT_MODEL = "nomic-embed-text"
DEFAULT_DIMENSIONS = 768


class OllamaEmbeddingsAdapter(EmbeddingsPort):
    """Ollama embeddings adapter for local inference.

    Connects to a local or remote Ollama server for text embeddings.
    """

    def __init__(
        self,
        base_url: str = "http://localhost:11434",
        model: str = DEFAULT_MODEL,
        timeout_seconds: float = 30.0,
    ):
        """Initialize Ollama embeddings adapter.

        Args:
            base_url: Ollama server URL
            model: Embedding model to use
            timeout_seconds: Request timeout
        """
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._timeout = timeout_seconds
        self._dimensions = MODEL_DIMENSIONS.get(model, DEFAULT_DIMENSIONS)
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create async HTTP client."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self._base_url,
                timeout=httpx.Timeout(self._timeout),
            )
        return self._client

    async def embed(self, text: str) -> list[float]:
        """Generate embedding vector for text.

        Args:
            text: The text to embed

        Returns:
            Embedding vector as list of floats
        """
        client = await self._get_client()

        payload = {
            "model": self._model,
            "prompt": text,
        }

        try:
            response = await client.post("/api/embeddings", json=payload)
            response.raise_for_status()
            data = response.json()

            embedding = data.get("embedding", [])
            if not embedding:
                raise EmbeddingError(f"Empty embedding returned for text: {text[:50]}...")

            return embedding
        except httpx.TimeoutException as e:
            raise EmbeddingTimeoutError(
                f"Ollama embedding timed out after {self._timeout}s"
            ) from e
        except httpx.ConnectError as e:
            raise EmbeddingConnectionError(
                f"Failed to connect to Ollama at {self._base_url}"
            ) from e
        except httpx.HTTPStatusError as e:
            raise EmbeddingError(f"Ollama embedding request failed: {e}") from e

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for multiple texts.

        Note: Ollama doesn't have a native batch endpoint, so this
        processes texts sequentially. For high-throughput scenarios,
        consider a provider with native batch support.

        Args:
            texts: List of texts to embed

        Returns:
            List of embedding vectors
        """
        embeddings = []
        for text in texts:
            embedding = await self.embed(text)
            embeddings.append(embedding)
        return embeddings

    def dimensions(self) -> int:
        """Return embedding dimensions for this model.

        Returns:
            Number of dimensions in embedding vectors
        """
        return self._dimensions

    async def health(self) -> dict[str, Any]:
        """Check Ollama server health.

        Returns:
            Health status dictionary
        """
        try:
            client = await self._get_client()
            response = await client.get("/api/tags", timeout=5.0)
            return {
                "healthy": response.status_code == 200,
                "base_url": self._base_url,
                "model": self._model,
                "dimensions": self._dimensions,
            }
        except Exception as e:
            return {
                "healthy": False,
                "base_url": self._base_url,
                "model": self._model,
                "error": str(e),
            }

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None
