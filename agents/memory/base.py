"""
MemoryProvider base interface (SIP-042)
"""

from abc import ABC, abstractmethod


class MemoryProvider(ABC):
    """
    Abstract base class for memory providers.
    All agent memory operations go through this interface.
    """
    
    @abstractmethod
    async def put(self, item: dict) -> str:
        """
        Store a memory item.
        
        Args:
            item: Dictionary containing memory data with keys:
                - ns: namespace (e.g., 'role', 'squad')
                - agent: agent name
                - tags: list of tags
                - content: memory content (dict)
                - importance: importance score (float)
        
        Returns:
            Memory ID as string
        """
        pass
    
    @abstractmethod
    async def get(self, query: str, k: int = 8, **kw) -> list[dict]:
        """
        Retrieve memories matching query.
        
        Args:
            query: Search query string
            k: Maximum number of results to return
            **kw: Additional provider-specific parameters
        
        Returns:
            List of memory dictionaries
        """
        pass
    
    @abstractmethod
    async def promote(self, mem_id: str, validator: str, to_ns: str = "squad") -> str:
        """
        Promote a memory to a higher namespace (e.g., role -> squad).
        
        Args:
            mem_id: Memory ID to promote
            validator: Agent/entity performing the promotion
            to_ns: Target namespace
        
        Returns:
            New memory ID in promoted namespace
        """
        pass
    
    @abstractmethod
    async def put_if_not_exists(self, item: dict) -> str | None:
        """
        Store a memory item only if it doesn't already exist (singleton pattern).
        
        Uses deterministic ID generation (agent + ns + content hash) to check
        for existing memories. If a memory with the same ID exists, returns None.
        Otherwise, stores and returns the memory ID.
        
        Args:
            item: Dictionary containing memory data with keys:
                - ns: namespace (e.g., 'role', 'squad')
                - agent: agent name
                - tags: list of tags
                - content: memory content (dict)
                - importance: importance score (float)
        
        Returns:
            Memory ID as string if stored, None if already exists
        """
        pass

