"""Version Control port interface.

Abstract base class for VCS adapters.
Part of SIP-0.8.7 Infrastructure Ports Migration.
"""
from abc import ABC, abstractmethod
from pathlib import Path

from squadops.tools.models import VCSStatus


class VersionControlPort(ABC):
    """Port interface for version control operations.

    Adapters implement VCS operations (Git, etc.).
    repo_path is validated via PathSecurityPolicy wrapper.
    """

    @abstractmethod
    def status(self, repo_path: Path) -> VCSStatus:
        """Get repository status.

        Args:
            repo_path: Absolute path to repository root (validated via PathSecurityPolicy)

        Returns:
            Repository status

        Raises:
            ToolVCSError: Not a repository or VCS error
        """
        ...

    @abstractmethod
    def commit(
        self,
        repo_path: Path,
        message: str,
        files: list[str] | None = None,
    ) -> str:
        """Commit changes to repository.

        Args:
            repo_path: Absolute path to repository root (validated via PathSecurityPolicy)
            message: Commit message
            files: Repo-relative POSIX paths (e.g., "src/main.py", "tests/test_foo.py").
                   If None, commits all staged changes.
                   Paths are validated: must not escape repo root (no ".." traversal).

        Returns:
            Commit hash

        Raises:
            ToolVCSError: Commit failed
        """
        ...

    @abstractmethod
    def push(
        self,
        repo_path: Path,
        remote: str = "origin",
        branch: str | None = None,
    ) -> None:
        """Push commits to remote.

        Args:
            repo_path: Absolute path to repository root
            remote: Remote name (default: "origin")
            branch: Branch to push (default: current branch)

        Raises:
            ToolVCSError: Push failed
        """
        ...
