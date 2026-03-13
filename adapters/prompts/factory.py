"""
Factory for creating prompt repository and asset source instances.

Follows the same pattern as other SquadOps adapter factories,
enabling config-driven provider selection.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from adapters.prompts.filesystem import FileSystemPromptRepository
from squadops.ports.prompts.asset_source import PromptAssetSourcePort
from squadops.ports.prompts.repository import PromptRepository

# Default paths for prompt assets
DEFAULT_PROMPTS_PATH = (
    Path(__file__).parent.parent.parent / "src" / "squadops" / "prompts" / "fragments"
)
DEFAULT_TEMPLATES_PATH = (
    Path(__file__).parent.parent.parent / "src" / "squadops" / "prompts" / "request_templates"
)


def create_prompt_repository(
    provider: str = "filesystem",
    base_path: Path | None = None,
    **kwargs,
) -> PromptRepository:
    """
    Create a prompt repository instance based on provider type.

    Args:
        provider: Repository provider type ("filesystem")
        base_path: Base path for filesystem provider (defaults to src/squadops/prompts/fragments)
        **kwargs: Additional provider-specific arguments

    Returns:
        PromptRepository implementation

    Raises:
        ValueError: If provider type is unknown
    """
    if provider == "filesystem":
        path = base_path or DEFAULT_PROMPTS_PATH
        return FileSystemPromptRepository(base_path=path, **kwargs)

    raise ValueError(f"Unknown prompt repository provider: {provider}")


def create_prompt_asset_source(
    provider: str = "filesystem",
    fragments_path: Path | None = None,
    templates_path: Path | None = None,
    **kwargs: Any,
) -> PromptAssetSourcePort:
    """Create a governed prompt asset source based on provider type.

    Args:
        provider: Asset source provider ("filesystem" or "langfuse")
        fragments_path: Path to system fragments (filesystem provider only)
        templates_path: Path to request templates (filesystem provider only)
        **kwargs: Provider-specific arguments (langfuse: public_key, secret_key, host)

    Returns:
        PromptAssetSourcePort implementation

    Raises:
        ValueError: If provider type is unknown
    """
    if provider == "filesystem":
        from adapters.prompts.filesystem_asset_adapter import FilesystemPromptAssetAdapter

        return FilesystemPromptAssetAdapter(
            fragments_path=fragments_path or DEFAULT_PROMPTS_PATH,
            templates_path=templates_path or DEFAULT_TEMPLATES_PATH,
        )

    if provider == "langfuse":
        from adapters.prompts.langfuse_asset_adapter import LangfusePromptAssetAdapter

        return LangfusePromptAssetAdapter(**kwargs)

    raise ValueError(
        f"Unknown prompt asset source provider: '{provider}'. "
        "Valid options: 'filesystem', 'langfuse'"
    )
