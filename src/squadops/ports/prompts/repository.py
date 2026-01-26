"""
Driven port for prompt storage abstraction.

This interface defines the contract for fetching prompt fragments,
allowing the domain logic to remain isolated from physical storage
implementation details.
"""

from abc import ABC, abstractmethod

from squadops.prompts.models import PromptFragment, PromptManifest


class PromptRepository(ABC):
    """
    Abstract contract for fetching prompt fragments.

    Implementations handle the actual storage medium (filesystem, S3, etc.)
    while the domain layer works against this abstraction.
    """

    @abstractmethod
    def get_fragment(self, fragment_id: str, role: str | None = None) -> PromptFragment:
        """
        Get a fragment by ID, optionally with role-specific override.

        Search path (winning rule - first match wins):
        1. Role-specific: prompts/roles/{role}/{fragment_id}.md
        2. Shared: prompts/shared/{layer}/{fragment_id}.md

        Args:
            fragment_id: Unique identifier for the fragment
            role: Optional role ID for role-specific override lookup

        Returns:
            The resolved PromptFragment

        Raises:
            FragmentNotFoundError: If fragment cannot be found
        """
        pass

    @abstractmethod
    def get_manifest(self) -> PromptManifest:
        """
        Load the prompt manifest.

        Returns:
            The current PromptManifest with all fragment metadata

        Raises:
            ManifestValidationError: If manifest is invalid or missing
        """
        pass

    @abstractmethod
    def list_fragments(
        self, layer: str | None = None, role: str | None = None
    ) -> list[PromptFragment]:
        """
        List available fragments, optionally filtered.

        Args:
            layer: Optional layer filter (identity, constraints, etc.)
            role: Optional role filter

        Returns:
            List of matching PromptFragment objects
        """
        pass

    @abstractmethod
    def validate_integrity(self) -> bool:
        """
        Verify all fragment hashes match the manifest.

        Performs a full integrity check of all fragments against
        their declared hashes in the manifest.

        Returns:
            True if all hashes match

        Raises:
            HashMismatchError: If any fragment fails integrity check
        """
        pass

    @abstractmethod
    def fragment_exists(self, fragment_id: str, role: str | None = None) -> bool:
        """
        Check if a fragment exists without loading it.

        Args:
            fragment_id: Unique identifier for the fragment
            role: Optional role for role-specific check

        Returns:
            True if the fragment exists
        """
        pass
