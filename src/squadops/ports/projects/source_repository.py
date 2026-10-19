"""SourceRepositoryPort: the managed clone of an external product's repository (SIP-0112 FR-02,
FR-05, FR-06; E.4.2).

The runtime API's own port, separate from the agents' ``VersionControlPort`` tool: a managed clone
reaches a repository the owner registered, and an agent's tool must never be able to. The Git
implementation reuses the agents' Git conventions (``adapters/tools``) under its own isolation.
"""

from abc import ABC, abstractmethod
from collections.abc import Collection, Mapping

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

    @abstractmethod
    async def commit_tree(
        self,
        project_id: str,
        *,
        parent: str,
        files: Mapping[str, bytes],
        executable: Collection[str],
        ref: str,
        message: str,
    ) -> str:
        """Commit ``files``, the whole tree, as one commit on ``parent`` in the managed clone, set
        ``ref`` (under ``refs/squadops/``) to it, and return the commit. The external repository
        is never touched, and a later sync never prunes the ref (E.4.3, contract 3's capture).

        Raises:
            SourceUnavailable: The clone does not hold ``parent``, or the ref is not one of ours.
        """

    @abstractmethod
    async def export_patch(self, project_id: str, commit: str) -> bytes:
        """``commit``'s change from its parent as a mail-formatted patch, binary-safe, that
        ``git am`` applies: FR-06's ``patch_export`` contribution.

        Raises:
            SourceUnavailable: The clone does not hold ``commit``.
        """
