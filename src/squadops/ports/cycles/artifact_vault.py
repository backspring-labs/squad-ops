"""
ArtifactVaultPort — abstract interface for artifact storage (SIP-0064 §7.1).
"""

from abc import ABC, abstractmethod

from squadops.cycles.models import ArtifactRef


class ArtifactVaultPort(ABC):
    """Port for immutable artifact storage, retrieval, and baseline management."""

    @abstractmethod
    async def store(self, artifact: ArtifactRef, content: bytes) -> ArtifactRef:
        """Store artifact bytes and return ref with vault_uri populated."""

    @abstractmethod
    async def retrieve(self, artifact_id: str) -> tuple[ArtifactRef, bytes]:
        """Retrieve artifact metadata and bytes.

        Raises:
            ArtifactNotFoundError: If the artifact_id is not found.
        """

    @abstractmethod
    async def get_metadata(self, artifact_id: str) -> ArtifactRef:
        """Retrieve artifact metadata without bytes.

        Raises:
            ArtifactNotFoundError: If the artifact_id is not found.
        """

    @abstractmethod
    async def list_artifacts(
        self,
        *,
        project_id: str | None = None,
        cycle_id: str | None = None,
        run_id: str | None = None,
        artifact_type: str | None = None,
    ) -> list[ArtifactRef]:
        """List artifacts with optional filters."""

    @abstractmethod
    async def set_baseline(self, project_id: str, artifact_type: str, artifact_id: str) -> None:
        """Promote an artifact as the baseline for the given type.

        Raises:
            ArtifactNotFoundError: If the artifact_id is not found.
        """

    @abstractmethod
    async def get_baseline(self, project_id: str, artifact_type: str) -> ArtifactRef | None:
        """Get the current baseline artifact for the given type, or None."""

    @abstractmethod
    async def list_baselines(self, project_id: str) -> dict[str, ArtifactRef]:
        """List all baselines for a project, keyed by artifact_type."""
