"""
Prompt system adapters.

Provides concrete implementations of PromptRepository and PromptAssetSourcePort.
"""

from adapters.prompts.factory import create_prompt_asset_source, create_prompt_repository
from adapters.prompts.filesystem import FileSystemPromptRepository
from adapters.prompts.filesystem_asset_adapter import FilesystemPromptAssetAdapter

__all__ = [
    "FileSystemPromptRepository",
    "FilesystemPromptAssetAdapter",
    "create_prompt_asset_source",
    "create_prompt_repository",
]
