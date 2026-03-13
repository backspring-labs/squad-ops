"""
Driven port for governed prompt asset retrieval.

This interface defines the contract for resolving governed prompt assets —
system prompt fragments and request templates — from a pluggable backend
(filesystem, Langfuse, or any future registry).

Two distinct retrieval paths:
- System fragment retrieval: feeds SIP-0057 deterministic layered assembly
- Request template retrieval: feeds handler-side rendering (Stage 2)

These are separate operations with different semantics and must not be
treated as interchangeable.

Introduced by SIP-0084 (Prompt Registry Integration Using Langfuse).
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from squadops.prompts.asset_models import AssetVersionInfo, ResolvedAsset


class PromptAssetSourcePort(ABC):
    """Pluggable backend for retrieving governed prompt assets.

    Serves two distinct retrieval paths:
    - System fragment retrieval: feeds SIP-0057 deterministic layered assembly
    - Request template retrieval: feeds handler-side rendering (Stage 2)

    These are separate operations. System fragments are composed deterministically
    by the PromptAssembler. Request templates are resolved and rendered by handlers.
    """

    @abstractmethod
    async def resolve_system_fragment(
        self, fragment_id: str, role: str | None = None, environment: str = "production"
    ) -> ResolvedAsset:
        """Resolve a system prompt fragment by identity.

        Args:
            fragment_id: Fragment identity (e.g., "identity", "task_type.code_generate")
            role: Optional agent role for role-specific override lookup
            environment: Environment label for version resolution

        Returns:
            Resolved asset with content, version, and content hash

        Raises:
            PromptAssetNotFoundError: If the fragment cannot be resolved
        """

    @abstractmethod
    async def resolve_request_template(
        self, template_id: str, environment: str = "production"
    ) -> ResolvedAsset:
        """Resolve a request template by identity.

        Args:
            template_id: Template identity (e.g., "request.development_develop.code_generate")
            environment: Environment label for version resolution

        Returns:
            Resolved asset with content, version, and content hash

        Raises:
            PromptAssetNotFoundError: If the template cannot be resolved
        """

    @abstractmethod
    async def get_asset_version(self, asset_id: str) -> AssetVersionInfo | None:
        """Retrieve version metadata for a governed asset.

        Args:
            asset_id: Asset identity (fragment or template)

        Returns:
            Version info if the asset exists, None otherwise
        """
