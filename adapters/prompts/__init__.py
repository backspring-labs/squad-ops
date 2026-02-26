"""
Prompt system adapters.

Provides concrete implementations of the PromptRepository port.
"""

from adapters.prompts.factory import create_prompt_repository
from adapters.prompts.filesystem import FileSystemPromptRepository

__all__ = [
    "FileSystemPromptRepository",
    "create_prompt_repository",
]
