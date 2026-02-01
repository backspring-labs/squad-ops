"""Unit tests for Ollama embeddings adapter."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from adapters.embeddings.ollama import OllamaEmbeddingsAdapter, MODEL_DIMENSIONS
from squadops.embeddings.exceptions import (
    EmbeddingConnectionError,
    EmbeddingError,
    EmbeddingTimeoutError,
)


class TestOllamaEmbeddingsAdapter:
    """Tests for OllamaEmbeddingsAdapter."""

    def test_init_defaults(self):
        """Adapter initializes with default values."""
        adapter = OllamaEmbeddingsAdapter()
        assert adapter._base_url == "http://localhost:11434"
        assert adapter._model == "nomic-embed-text"
        assert adapter._timeout == 30.0
        assert adapter._dimensions == 768

    def test_init_custom(self):
        """Adapter accepts custom configuration."""
        adapter = OllamaEmbeddingsAdapter(
            base_url="http://custom:8080",
            model="mxbai-embed-large",
            timeout_seconds=60.0,
        )
        assert adapter._base_url == "http://custom:8080"
        assert adapter._model == "mxbai-embed-large"
        assert adapter._timeout == 60.0
        assert adapter._dimensions == 1024  # mxbai-embed-large dimension

    def test_dimensions_returns_correct_value(self):
        """dimensions() returns the model's embedding dimension."""
        adapter = OllamaEmbeddingsAdapter(model="nomic-embed-text")
        assert adapter.dimensions() == 768

        adapter = OllamaEmbeddingsAdapter(model="all-minilm")
        assert adapter.dimensions() == 384

    def test_unknown_model_uses_default_dimensions(self):
        """Unknown models use default dimensions."""
        adapter = OllamaEmbeddingsAdapter(model="unknown-model")
        assert adapter.dimensions() == 768  # Default


@pytest.mark.asyncio
class TestOllamaEmbeddingsAdapterAsync:
    """Async tests for OllamaEmbeddingsAdapter."""

    async def test_embed_success(self):
        """embed() returns embedding vector on success."""
        adapter = OllamaEmbeddingsAdapter()

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"embedding": [0.1, 0.2, 0.3] * 256}

        with patch.object(adapter, "_get_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_client.post.return_value = mock_response
            mock_get_client.return_value = mock_client

            embedding = await adapter.embed("test text")

            assert len(embedding) == 768
            mock_client.post.assert_called_once_with(
                "/api/embeddings",
                json={"model": "nomic-embed-text", "prompt": "test text"},
            )

    async def test_embed_empty_response_raises_error(self):
        """embed() raises EmbeddingError on empty response."""
        adapter = OllamaEmbeddingsAdapter()

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"embedding": []}

        with patch.object(adapter, "_get_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_client.post.return_value = mock_response
            mock_get_client.return_value = mock_client

            with pytest.raises(EmbeddingError, match="Empty embedding"):
                await adapter.embed("test text")

    async def test_embed_timeout_raises_error(self):
        """embed() raises EmbeddingTimeoutError on timeout."""
        import httpx

        adapter = OllamaEmbeddingsAdapter()

        with patch.object(adapter, "_get_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_client.post.side_effect = httpx.TimeoutException("timeout")
            mock_get_client.return_value = mock_client

            with pytest.raises(EmbeddingTimeoutError, match="timed out"):
                await adapter.embed("test text")

    async def test_embed_connection_error(self):
        """embed() raises EmbeddingConnectionError on connection failure."""
        import httpx

        adapter = OllamaEmbeddingsAdapter()

        with patch.object(adapter, "_get_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_client.post.side_effect = httpx.ConnectError("connection failed")
            mock_get_client.return_value = mock_client

            with pytest.raises(EmbeddingConnectionError, match="Failed to connect"):
                await adapter.embed("test text")

    async def test_embed_batch_success(self):
        """embed_batch() returns embeddings for all texts."""
        adapter = OllamaEmbeddingsAdapter()

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"embedding": [0.1] * 768}

        with patch.object(adapter, "_get_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_client.post.return_value = mock_response
            mock_get_client.return_value = mock_client

            embeddings = await adapter.embed_batch(["text1", "text2", "text3"])

            assert len(embeddings) == 3
            assert all(len(e) == 768 for e in embeddings)
            assert mock_client.post.call_count == 3

    async def test_health_success(self):
        """health() returns healthy status on success."""
        adapter = OllamaEmbeddingsAdapter()

        mock_response = MagicMock()
        mock_response.status_code = 200

        with patch.object(adapter, "_get_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_response
            mock_get_client.return_value = mock_client

            health = await adapter.health()

            assert health["healthy"] is True
            assert health["model"] == "nomic-embed-text"
            assert health["dimensions"] == 768

    async def test_health_failure(self):
        """health() returns unhealthy status on failure."""
        adapter = OllamaEmbeddingsAdapter()

        with patch.object(adapter, "_get_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_client.get.side_effect = Exception("connection failed")
            mock_get_client.return_value = mock_client

            health = await adapter.health()

            assert health["healthy"] is False
            assert "error" in health


class TestEmbeddingsFactory:
    """Tests for embeddings factory."""

    def test_create_ollama_provider(self):
        """Factory creates Ollama provider."""
        from adapters.embeddings.factory import create_embeddings_provider

        provider = create_embeddings_provider(provider="ollama")
        assert isinstance(provider, OllamaEmbeddingsAdapter)

    def test_create_unknown_provider_raises(self):
        """Factory raises ValueError for unknown provider."""
        from adapters.embeddings.factory import create_embeddings_provider

        with pytest.raises(ValueError, match="Unknown embeddings provider"):
            create_embeddings_provider(provider="unknown")

    def test_create_with_custom_config(self):
        """Factory passes configuration to adapter."""
        from adapters.embeddings.factory import create_embeddings_provider

        provider = create_embeddings_provider(
            provider="ollama",
            base_url="http://custom:8080",
            model="mxbai-embed-large",
        )
        assert provider._base_url == "http://custom:8080"
        assert provider._model == "mxbai-embed-large"
