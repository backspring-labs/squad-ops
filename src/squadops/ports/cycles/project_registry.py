"""
ProjectRegistryPort — abstract interface for project lookup (SIP-0064 §7.1), and registration
(SIP-0112 FR-02, E.4.1).
"""

from abc import ABC, abstractmethod

from squadops.cycles.models import Project
from squadops.projects.registration import ProjectRegistration


class ProjectRegistryPort(ABC):
    """Port for listing and retrieving pre-registered projects."""

    @abstractmethod
    async def list_projects(self) -> list[Project]:
        """Return all registered projects."""

    @abstractmethod
    async def get_project(self, project_id: str) -> Project:
        """Return a project by ID.

        Raises:
            ProjectNotFoundError: If the project_id is not found.
        """

    @abstractmethod
    async def register_project(
        self, registration: ProjectRegistration, *, actor: str
    ) -> tuple[Project, bool]:
        """Register an existing product, as ``REGISTERING``; return it and whether this was a
        replay of an earlier request with the same idempotency key.

        Raises:
            ProjectRegistryReadOnlyError: The registry refuses writes.
            ProjectIdTakenError: The Project ID is held.
            RegistrationKeyConflictError: The key registered different content.
        """
