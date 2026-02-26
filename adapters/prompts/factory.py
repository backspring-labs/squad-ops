"""
Factory for creating prompt repository instances.

Follows the same pattern as other SquadOps adapter factories,
enabling config-driven provider selection.
"""

from pathlib import Path

from adapters.prompts.filesystem import FileSystemPromptRepository
from squadops.ports.prompts.repository import PromptRepository

# Default path for prompt fragments
DEFAULT_PROMPTS_PATH = (
    Path(__file__).parent.parent.parent / "src" / "squadops" / "prompts" / "fragments"
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
