"""Container port interface.

Abstract base class for container runtime adapters.
Part of SIP-0.8.7 Infrastructure Ports Migration.
"""

from abc import ABC, abstractmethod
from typing import Any

from squadops.tools.models import ContainerResult, ContainerSpec


class ContainerPort(ABC):
    """Port interface for container operations.

    Adapters implement container runtime operations (Docker, Podman, etc.).
    """

    @abstractmethod
    async def run(self, spec: ContainerSpec) -> ContainerResult:
        """Run a container.

        Args:
            spec: Container specification

        Returns:
            Container execution result

        Raises:
            ToolContainerError: Container execution failed
        """
        ...

    @abstractmethod
    async def stop(self, container_id: str) -> None:
        """Stop a running container.

        Args:
            container_id: ID of container to stop

        Raises:
            ToolContainerError: Failed to stop container
        """
        ...

    @abstractmethod
    async def logs(self, container_id: str, tail: int | None = None) -> str:
        """Get container logs.

        Args:
            container_id: ID of container
            tail: Optional number of lines from end

        Returns:
            Container logs

        Raises:
            ToolContainerError: Failed to get logs
        """
        ...

    @abstractmethod
    async def health(self) -> dict[str, Any]:
        """Check container runtime health.

        Returns:
            Health status dictionary with at least {"healthy": bool}
        """
        ...

    @abstractmethod
    async def run_detached(self, spec: ContainerSpec) -> str:
        """Start a container without waiting for it to exit (SIP-0102 runtime
        unit). Ports listed in ``spec.publish_ports`` are published to
        loopback-only ephemeral host ports.

        Returns:
            The started container's id (use with stop/logs/resolve_host_port)

        Raises:
            ToolContainerError: Container could not be started
        """
        ...

    @abstractmethod
    async def resolve_host_port(self, container_id: str, container_port: int) -> int:
        """The ephemeral host port a published container port was mapped to.

        Raises:
            ToolContainerError: Mapping could not be resolved
        """
        ...

    @abstractmethod
    async def has_image(self, image: str) -> bool:
        """Whether the image is present locally (SIP-0102 preflight).

        Returns:
            True if present, False if definitively absent

        Raises:
            ToolContainerError: Presence could not be determined (daemon down)
        """
        ...
