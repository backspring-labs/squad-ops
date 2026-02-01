"""Memory port interface.

Abstract base class for memory storage adapters.
Part of SIP-0.8.7 Infrastructure Ports Migration.
"""
from abc import ABC, abstractmethod

from squadops.memory.models import MemoryEntry, MemoryQuery, MemoryResult


class MemoryPort(ABC):
    """Port interface for memory storage operations.

    Adapters implement vector-based semantic memory storage and retrieval.
    All methods are async to support non-blocking embedding operations.
    """

    @abstractmethod
    async def store(self, entry: MemoryEntry) -> str:
        """Store a memory entry.

        Args:
            entry: Memory entry to store

        Returns:
            Memory ID of the stored entry

        Raises:
            MemoryStoreError: Failed to store entry
            MemoryEmbeddingError: Failed to generate embeddings
        """
        ...

    @abstractmethod
    async def search(self, query: MemoryQuery) -> list[MemoryResult]:
        """Search for relevant memories.

        Args:
            query: Search query specification

        Returns:
            List of matching results sorted by relevance score

        Raises:
            MemoryEmbeddingError: Failed to generate query embeddings
        """
        ...

    @abstractmethod
    async def get(self, memory_id: str) -> MemoryEntry | None:
        """Get a specific memory entry by ID.

        Args:
            memory_id: ID of the memory to retrieve

        Returns:
            Memory entry if found, None otherwise
        """
        ...

    @abstractmethod
    async def delete(self, memory_id: str) -> bool:
        """Delete a memory entry.

        Args:
            memory_id: ID of the memory to delete

        Returns:
            True if deleted, False if not found
        """
        ...
