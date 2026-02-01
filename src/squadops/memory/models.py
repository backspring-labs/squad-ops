"""Memory domain models.

Frozen dataclasses for memory operations.
Part of SIP-0.8.7 Infrastructure Ports Migration.
"""
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class MemoryEntry:
    """Entry to store in memory.

    Immutable memory entry for MemoryPort.store().
    """

    content: str
    namespace: str = "role"
    agent_id: str | None = None
    cycle_id: str | None = None
    tags: tuple[str, ...] = ()
    importance: float = 0.7
    metadata: tuple[tuple[str, Any], ...] = ()


@dataclass(frozen=True)
class MemoryQuery:
    """Query for memory search.

    Immutable query specification for MemoryPort.search().
    """

    text: str
    limit: int = 8
    threshold: float = 0.7
    namespace: str | None = None
    tags: tuple[str, ...] = ()


@dataclass(frozen=True)
class MemoryResult:
    """Result from memory search.

    Immutable result from MemoryPort.search().
    """

    entry: MemoryEntry
    memory_id: str
    score: float
