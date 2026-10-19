"""SourceRepositoryPort: the managed clone of an external product's repository (SIP-0112 FR-02,
FR-05, FR-06; E.4.2).

The runtime API's own port, separate from the agents' ``VersionControlPort`` tool: a managed clone
reaches a repository the owner registered, and an agent's tool must never be able to. The Git
implementation reuses the agents' Git conventions (``adapters/tools``) under its own isolation.
"""

from abc import ABC, abstractmethod

from squadops.projects.models import CheckoutTree


class SourceRepositoryPort(ABC):
    @abstractmethod
    async def sync(self, project_id: str, locator: str, ref: str) -> str:
        """Clone the repository into the managed cache, or fetch it there, and return the commit
        ``ref`` names now (40 hexadecimal characters).

        Raises:
            SourceUnavailable: The repository or the ref could not be reached, with the reason.
        """

    @abstractmethod
    async def tree_at(self, project_id: str, commit: str) -> CheckoutTree:
        """Every tracked file at ``commit`` in the managed clone, read as bytes, with its
        executable bit; and the tracked symlinks and submodules, which no tree here carries.

        Raises:
            SourceUnavailable: The clone does not hold ``commit``.
        """
