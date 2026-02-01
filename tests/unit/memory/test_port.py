"""Unit tests for Memory port interface."""
import pytest

from squadops.ports.memory.store import MemoryPort


class TestMemoryPort:
    """Tests for MemoryPort interface."""

    def test_cannot_instantiate_directly(self):
        """MemoryPort is abstract and cannot be instantiated."""
        with pytest.raises(TypeError):
            MemoryPort()  # type: ignore

    def test_has_store_method(self):
        assert hasattr(MemoryPort, "store")

    def test_has_search_method(self):
        assert hasattr(MemoryPort, "search")

    def test_has_get_method(self):
        assert hasattr(MemoryPort, "get")

    def test_has_delete_method(self):
        assert hasattr(MemoryPort, "delete")
