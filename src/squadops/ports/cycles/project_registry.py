"""
ProjectRegistryPort — abstract interface for project lookup (SIP-0064 §7.1).
"""

from abc import ABC, abstractmethod

from squadops.cycles.models import Project


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
