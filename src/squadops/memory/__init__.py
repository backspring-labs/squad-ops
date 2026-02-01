"""Memory domain layer.

Provides domain models for memory operations:
- MemoryEntry: Entry to store in memory
- MemoryQuery: Query specification for search
- MemoryResult: Search result with score

Part of SIP-0.8.7 Infrastructure Ports Migration.
"""
from squadops.memory.exceptions import (
    MemoryEmbeddingError,
    MemoryError,
    MemoryNotFoundError,
    MemoryStoreError,
)
from squadops.memory.models import MemoryEntry, MemoryQuery, MemoryResult

__all__ = [
    "MemoryEmbeddingError",
    "MemoryEntry",
    "MemoryError",
    "MemoryNotFoundError",
    "MemoryQuery",
    "MemoryResult",
    "MemoryStoreError",
]
