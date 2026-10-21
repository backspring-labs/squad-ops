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

    @abstractmethod
    async def commit_message(self, project_id: str, commit: str) -> str:
        """``commit``'s message, as committed.

        Raises:
            SourceUnavailable: The clone does not hold ``commit``.
        """

    @abstractmethod
    async def push_capture(
        self, project_id: str, locator: str, *, ref: str, branch: str, token: str
    ) -> None:
        """Push a captured ref (``refs/squadops/...``) to the product's repository as
        ``refs/heads/<branch>`` (``squadops/...``), authenticated by ``token`` over https, or to
        a local repository under a configured root. Never forced: a branch the product already
        holds with other history is refused (FR-06's review_request).

        Raises:
            SourceUnavailable: The locator is refused or ssh, the branch or ref isn't one of
                ours, or the product refused the push.
        """

    @abstractmethod
    async def initialize(
        self,
        project_id: str,
        locator: str,
        *,
        ref: str,
        files: Mapping[str, bytes],
        executable: Collection[str],
        message: str,
        committed_at: int,
        token: str,
    ) -> str:
        """Make ``files`` the first commit of ``ref`` (``refs/heads/<branch>``) in a product
        repository that holds no commit there yet, and return it (SIP-0112 E.4.6, greenfield).

        The commit has no parent, and its committer date is ``committed_at`` (seconds since the
        epoch), so the same request makes the same commit. It's made in the managed clone, then
        pushed, never forced, with ``token`` over https, or to a local repository under a
        configured root. A branch already at that commit is answered with it, unpushed: a retry
        whose push landed. Any other commit there refuses, and the product is untouched.

        Raises:
            SourceUnavailable: The locator is refused or ssh, the ref isn't a branch, the branch
                holds another commit (``not_empty``), or the product refused the push.
        """

    @abstractmethod
    async def is_ancestor(self, project_id: str, ancestor: str, descendant: str) -> bool:
        """Whether ``ancestor`` is in ``descendant``'s history in the managed clone (a commit is
        its own ancestor). E.4.4 reads a contribution as integrated when its commit is.

        Raises:
            SourceUnavailable: The clone doesn't hold one of them.
        """

    @abstractmethod
    async def file_at(self, project_id: str, commit: str, path: str) -> bytes:
        """One tracked file's bytes at ``commit`` in the managed clone (contract 6's resolver).

        Raises:
            SourceUnavailable: The clone doesn't hold ``commit``, the path isn't a tracked file
                there, or the path isn't a repository-relative one.
        """
