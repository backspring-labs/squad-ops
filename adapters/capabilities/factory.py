"""
Factory for creating capability system instances.

Follows the same pattern as other SquadOps adapter factories,
enabling config-driven provider selection.
"""

from pathlib import Path

from squadops.ports.capabilities.repository import CapabilityRepository
from squadops.ports.capabilities.executor import CapabilityExecutor
from squadops.ports.comms.queue import QueuePort
from adapters.capabilities.filesystem import FileSystemCapabilityRepository
from adapters.capabilities.aci_executor import ACICapabilityExecutor

# Default path for capability manifests
DEFAULT_MANIFESTS_PATH = (
    Path(__file__).parent.parent.parent
    / "src"
    / "squadops"
    / "capabilities"
    / "manifests"
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


def create_capability_executor(
    provider: str = "aci",
    queue: QueuePort | None = None,
    **kwargs,
) -> CapabilityExecutor:
    """
    Create a capability executor instance based on provider type.

    Args:
        provider: Executor provider type ("aci")
        queue: QueuePort implementation (required for ACI)
        **kwargs: Additional provider-specific arguments

    Returns:
        CapabilityExecutor implementation

    Raises:
        ValueError: If provider type is unknown or required args missing
    """
    if provider == "aci":
        if queue is None:
            raise ValueError("ACI executor requires a QueuePort instance")
        return ACICapabilityExecutor(queue=queue, **kwargs)

    raise ValueError(f"Unknown capability executor provider: {provider}")
