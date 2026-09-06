"""
Factory for creating capability system instances.

Follows the same pattern as other SquadOps adapter factories,
enabling config-driven provider selection.
"""

from pathlib import Path

from adapters.capabilities.filesystem import FileSystemCapabilityRepository
from squadops.ports.capabilities.repository import CapabilityRepository

# Default path for capability manifests
DEFAULT_MANIFESTS_PATH = (
    Path(__file__).parent.parent.parent / "src" / "squadops" / "capabilities" / "manifests"
)


def create_capability_repository(
    provider: str = "filesystem",
    base_path: Path | None = None,
    validate_schemas: bool = True,
    **kwargs,
) -> CapabilityRepository:
    """
    Create a capability repository instance based on provider type.

    Args:
        provider: Repository provider type ("filesystem")
        base_path: Base path for filesystem provider (defaults to manifests dir)
        validate_schemas: Whether to validate against JSON schemas
        **kwargs: Additional provider-specific arguments

    Returns:
        CapabilityRepository implementation

    Raises:
        ValueError: If provider type is unknown
    """
    if provider == "filesystem":
        path = base_path or DEFAULT_MANIFESTS_PATH
        return FileSystemCapabilityRepository(
            base_path=path,
            validate_schemas=validate_schemas,
            **kwargs,
        )

    raise ValueError(f"Unknown capability repository provider: {provider}")
