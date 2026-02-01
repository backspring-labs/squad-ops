"""Memory domain exceptions.

Domain-prefixed exceptions to avoid collision with Python built-ins.
Part of SIP-0.8.7 Infrastructure Ports Migration.
"""


class MemoryError(Exception):
    """Base exception for memory operations.

    Note: Named MemoryError but this is our domain exception,
    not Python's built-in MemoryError (which is for out-of-memory).
    Import as: from squadops.memory.exceptions import MemoryError as MemoryStoreError
    """

    pass


class MemoryStoreError(MemoryError):
    """Failed to store memory entry."""

    pass


class MemoryNotFoundError(MemoryError):
    """Memory entry not found."""

    pass


class MemoryEmbeddingError(MemoryError):
    """Failed to generate embeddings."""

    pass
