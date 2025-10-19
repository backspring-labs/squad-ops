"""
LLMClient protocol definition for SquadOps agents.

Defines the interface that all LLM providers must implement.
"""

from typing import Protocol, List, Dict, Any


class LLMClient(Protocol):
    """Protocol for LLM providers"""
    
    async def complete(
        self, 
        prompt: str, 
        temperature: float = 0.7,
        max_tokens: int = 4000,
        **kwargs
    ) -> str:
        """Generate completion from prompt"""
        ...
    
    async def chat(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 4000,
        **kwargs
    ) -> str:
        """Generate chat completion"""
        ...



