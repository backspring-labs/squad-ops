"""Unit tests for LanceDBAdapter with EmbeddingsPort injection.

Tests the SIP-0.8.8 update that replaced embed_fn seam with EmbeddingsPort.
"""

from unittest.mock import MagicMock, patch

import pytest

from squadops.ports.embeddings.provider import EmbeddingsPort


class MockEmbeddingsAdapter(EmbeddingsPort):
    """Mock embeddings adapter for testing."""

    def __init__(self, dimensions: int = 384):
        self._dimensions = dimensions
        self.embed_calls = []

    async def embed(self, text: str) -> list[float]:
        self.embed_calls.append(text)
        return [0.1] * self._dimensions

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        return [await self.embed(t) for t in texts]

    def dimensions(self) -> int:
        return self._dimensions

    async def health(self) -> dict:
        return {"healthy": True}


@pytest.fixture
def mock_embeddings():
    """Create mock embeddings adapter."""
    return MockEmbeddingsAdapter(dimensions=384)


@pytest.fixture
def mock_lancedb():
    """Mock LanceDB module and pyarrow."""
    mock_db = MagicMock()
    mock_table = MagicMock()
    mock_db.open_table = MagicMock(side_effect=Exception("Table not found"))
    mock_db.create_table = MagicMock(return_value=mock_table)

    mock_lancedb_module = MagicMock()
    mock_lancedb_module.connect = MagicMock(return_value=mock_db)

    mock_pa = MagicMock()
    mock_pa.schema = MagicMock()
    mock_pa.field = MagicMock()
    mock_pa.string = MagicMock()
    mock_pa.list_ = MagicMock(return_value=MagicMock())
    mock_pa.float32 = MagicMock()

    with patch.dict("sys.modules", {"lancedb": mock_lancedb_module, "pyarrow": mock_pa}):
        yield mock_db, mock_table


class TestLanceDBAdapterWithEmbeddingsPort:
    """Tests for LanceDBAdapter using EmbeddingsPort injection."""

    def test_adapter_accepts_embeddings_port(self, mock_embeddings, mock_lancedb):
        """LanceDBAdapter accepts EmbeddingsPort in constructor."""
        from adapters.memory.lancedb import LanceDBAdapter

        adapter = LanceDBAdapter(
            db_path="/tmp/test.lancedb",
            embeddings=mock_embeddings,
        )

        assert adapter._embeddings is mock_embeddings
        assert adapter._embedding_dim == 384

    def test_adapter_uses_embeddings_dimensions(self, mock_lancedb):
        """LanceDBAdapter gets dimensions from EmbeddingsPort."""
        from adapters.memory.lancedb import LanceDBAdapter

        embeddings_768 = MockEmbeddingsAdapter(dimensions=768)
        adapter = LanceDBAdapter(
            db_path="/tmp/test.lancedb",
            embeddings=embeddings_768,
        )
        assert adapter._embedding_dim == 768

        embeddings_1024 = MockEmbeddingsAdapter(dimensions=1024)
        adapter = LanceDBAdapter(
            db_path="/tmp/test.lancedb",
            embeddings=embeddings_1024,
        )
        assert adapter._embedding_dim == 1024

    @pytest.mark.asyncio
    async def test_store_calls_embeddings_port(self, mock_embeddings, mock_lancedb):
        """store() uses EmbeddingsPort.embed() for vectorization."""
        from adapters.memory.lancedb import LanceDBAdapter
        from squadops.memory.models import MemoryEntry

        mock_db, mock_table = mock_lancedb

        adapter = LanceDBAdapter(
            db_path="/tmp/test.lancedb",
            embeddings=mock_embeddings,
        )
        adapter._table = mock_table

        entry = MemoryEntry(
            content="Test memory content",
            namespace="test",
        )

        memory_id = await adapter.store(entry)

        assert memory_id is not None
        assert "Test memory content" in mock_embeddings.embed_calls
        mock_table.add.assert_called_once()

    @pytest.mark.asyncio
    async def test_search_calls_embeddings_port(self, mock_embeddings, mock_lancedb):
        """search() uses EmbeddingsPort.embed() for query vectorization."""
        from adapters.memory.lancedb import LanceDBAdapter
        from squadops.memory.models import MemoryQuery

        mock_db, mock_table = mock_lancedb

        # Setup search mock
        mock_search = MagicMock()
        mock_search.limit.return_value.to_list.return_value = []
        mock_table.search.return_value = mock_search

        adapter = LanceDBAdapter(
            db_path="/tmp/test.lancedb",
            embeddings=mock_embeddings,
        )
        adapter._table = mock_table

        query = MemoryQuery(text="search query", limit=5)

        await adapter.search(query)

        assert "search query" in mock_embeddings.embed_calls
        mock_table.search.assert_called_once()


class TestMemoryFactoryWithEmbeddings:
    """Tests for memory factory with embeddings integration."""

    def test_factory_accepts_embeddings_port(self, mock_embeddings, mock_lancedb):
        """Factory accepts and passes EmbeddingsPort to adapter."""
        from adapters.memory.factory import create_memory_provider

        provider = create_memory_provider(
            provider="lancedb",
            embeddings=mock_embeddings,
            db_path="/tmp/test.lancedb",
        )

        assert provider._embeddings is mock_embeddings

    def test_factory_creates_default_embeddings_when_none_provided(self, mock_lancedb):
        """Factory creates default Ollama embeddings if none provided."""
        from adapters.embeddings.ollama import OllamaEmbeddingsAdapter
        from adapters.memory.factory import create_memory_provider

        # Since the import is inside the function, we test by verifying
        # that without providing embeddings, the adapter still works
        # and has an embeddings port that's an OllamaEmbeddingsAdapter
        provider = create_memory_provider(
            provider="lancedb",
            db_path="/tmp/test.lancedb",
        )

        # Verify an embeddings adapter was created
        assert provider._embeddings is not None
        assert isinstance(provider._embeddings, OllamaEmbeddingsAdapter)
