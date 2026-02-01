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
