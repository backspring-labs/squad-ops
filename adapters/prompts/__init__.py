"""
Prompt system adapters.

Provides concrete implementations of the PromptRepository port.
"""

from adapters.prompts.filesystem import FileSystemPromptRepository
from adapters.prompts.factory import create_prompt_repository

__all__ = [
    "FileSystemPromptRepository",
    "create_prompt_repository",
]
