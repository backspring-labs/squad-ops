"""
LLMClient protocol definition for SquadOps agents.

Defines the interface that all LLM providers must implement.
"""

from typing import Protocol, List, Dict, Optional


class LLMClient(Protocol):
    """Protocol for LLM providers"""
    
    async def complete(
        self, 
        prompt: str, 
        temperature: float = 0.7,
        max_tokens: int = 4000,
        **kwargs
    ) -> str:
        """
        Generate completion from prompt
        
        Returns:
            str: Generated text response
        """
        ...
    
    async def chat(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 4000,
        **kwargs
    ) -> str:
        """
        Generate chat completion
        
        Returns:
            str: Generated text response
        """
        ...
    
    def get_token_usage(self) -> Optional[Dict[str, int]]:
        """
        Get token usage from the last LLM call (if available)
        
        Returns:
            Dict with keys: 'prompt_tokens', 'completion_tokens', 'total_tokens'
            Returns None if token usage is not available
        """
        ...




