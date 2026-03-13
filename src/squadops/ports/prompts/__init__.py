"""
Port interfaces for the prompt assembly system.

Defines contracts for:
- PromptRepository (driven port): Storage abstraction for fetching fragments
- PromptService (driving port): Agent-facing interface for prompt assembly
- PromptAssetSourcePort (driven port): Governed asset retrieval (SIP-0084)
"""

from squadops.ports.prompts.asset_source import PromptAssetSourcePort
from squadops.ports.prompts.repository import PromptRepository
from squadops.ports.prompts.service import PromptService

__all__ = [
    "PromptAssetSourcePort",
    "PromptRepository",
    "PromptService",
]
