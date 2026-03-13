"""
Domain layer for prompt assembly system.

This module provides deterministic, versioned prompt assembly following
hexagonal architecture patterns (Ports and Adapters).
"""

from squadops.prompts.asset_models import AssetVersionInfo, RenderedRequest, ResolvedAsset
from squadops.prompts.cache import CyclePromptCache
from squadops.prompts.exceptions import (
    FragmentNotFoundError,
    HashMismatchError,
    MandatoryLayerMissingError,
    ManifestValidationError,
    PromptAssetNotFoundError,
    PromptDomainError,
    PromptRegistryUnavailableError,
    TemplateMissingVariableError,
)
from squadops.prompts.models import AssembledPrompt, PromptFragment, PromptManifest

__all__ = [
    "AssembledPrompt",
    "AssetVersionInfo",
    "CyclePromptCache",
    "FragmentNotFoundError",
    "HashMismatchError",
    "MandatoryLayerMissingError",
    "ManifestValidationError",
    "PromptAssetNotFoundError",
    "PromptDomainError",
    "PromptFragment",
    "PromptManifest",
    "PromptRegistryUnavailableError",
    "RenderedRequest",
    "ResolvedAsset",
    "TemplateMissingVariableError",
]
