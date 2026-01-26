"""
Domain layer for prompt assembly system.

This module provides deterministic, versioned prompt assembly following
hexagonal architecture patterns (Ports and Adapters).
"""

from squadops.prompts.models import AssembledPrompt, PromptFragment, PromptManifest
from squadops.prompts.exceptions import (
    PromptDomainError,
    FragmentNotFoundError,
    HashMismatchError,
    MandatoryLayerMissingError,
    ManifestValidationError,
)

__all__ = [
    "AssembledPrompt",
    "PromptFragment",
    "PromptManifest",
    "PromptDomainError",
    "FragmentNotFoundError",
    "HashMismatchError",
    "MandatoryLayerMissingError",
    "ManifestValidationError",
]
