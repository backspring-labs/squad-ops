"""Unit tests for EmbeddingsPort interface."""

from abc import ABC

import pytest

from squadops.ports.embeddings.provider import EmbeddingsPort


class TestEmbeddingsPortInterface:
    """Tests for EmbeddingsPort ABC."""

    def test_is_abstract_class(self):
        """EmbeddingsPort is an abstract base class."""
        assert issubclass(EmbeddingsPort, ABC)

    def test_cannot_instantiate_directly(self):
        """Cannot instantiate EmbeddingsPort directly."""
        with pytest.raises(TypeError):
            EmbeddingsPort()

    def test_has_required_methods(self):
        """EmbeddingsPort defines required abstract methods."""
        abstract_methods = EmbeddingsPort.__abstractmethods__
        assert "embed" in abstract_methods
        assert "embed_batch" in abstract_methods
        assert "dimensions" in abstract_methods
        assert "health" in abstract_methods


class TestEmbeddingsPortImplementation:
    """Tests for concrete implementations of EmbeddingsPort."""

    def test_mock_implementation_works(self):
        """A mock implementation can be created and used."""

        class MockEmbeddingsAdapter(EmbeddingsPort):
            async def embed(self, text: str) -> list[float]:
                return [0.1] * 768

            async def embed_batch(self, texts: list[str]) -> list[list[float]]:
                return [[0.1] * 768 for _ in texts]

            def dimensions(self) -> int:
                return 768

            async def health(self) -> dict:
                return {"healthy": True}

        adapter = MockEmbeddingsAdapter()
        assert adapter.dimensions() == 768

    @pytest.mark.asyncio
    async def test_mock_embed(self):
        """Mock implementation can embed text."""

        class MockEmbeddingsAdapter(EmbeddingsPort):
            async def embed(self, text: str) -> list[float]:
                return [0.1] * 768

            async def embed_batch(self, texts: list[str]) -> list[list[float]]:
                return [[0.1] * 768 for _ in texts]

            def dimensions(self) -> int:
                return 768

            async def health(self) -> dict:
                return {"healthy": True}

        adapter = MockEmbeddingsAdapter()
        embedding = await adapter.embed("test text")
        assert len(embedding) == 768
        assert all(isinstance(x, float) for x in embedding)

    @pytest.mark.asyncio
    async def test_mock_embed_batch(self):
        """Mock implementation can batch embed texts."""

        class MockEmbeddingsAdapter(EmbeddingsPort):
            async def embed(self, text: str) -> list[float]:
                return [0.1] * 768

            async def embed_batch(self, texts: list[str]) -> list[list[float]]:
                return [[0.1] * 768 for _ in texts]

            def dimensions(self) -> int:
                return 768

            async def health(self) -> dict:
                return {"healthy": True}

        adapter = MockEmbeddingsAdapter()
        embeddings = await adapter.embed_batch(["text1", "text2", "text3"])
        assert len(embeddings) == 3
        assert all(len(e) == 768 for e in embeddings)
