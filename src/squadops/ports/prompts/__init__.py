"""
Port interfaces for the prompt assembly system.

Defines contracts for:
- PromptRepository (driven port): Storage abstraction for fetching fragments
- PromptService (driving port): Agent-facing interface for prompt assembly
"""

from squadops.ports.prompts.repository import PromptRepository
from squadops.ports.prompts.service import PromptService

__all__ = [
    "PromptRepository",
    "PromptService",
]
