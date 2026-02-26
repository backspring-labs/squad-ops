"""Git version control adapter.

Implementation of VersionControlPort for Git.
Part of SIP-0.8.7 Infrastructure Ports Migration.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from squadops.ports.tools.vcs import VersionControlPort
from squadops.tools.exceptions import ToolVCSError
from squadops.tools.models import VCSStatus
from squadops.tools.security import PathSecurityPolicy


class GitAdapter(VersionControlPort):
    """Git version control adapter.

    Implements VersionControlPort for Git operations.
    Uses git CLI for operations.
    """

    def _run_git(
        self,
        repo_path: Path,
        *args: str,
        check: bool = True,
    ) -> subprocess.CompletedProcess:
        """Run git command in repository.

        Args:
            repo_path: Path to repository
            *args: Git command arguments
            check: If True, raise on non-zero exit

        Returns:
            Completed process result
        """
        try:
            return subprocess.run(
                ["git", *args],
                cwd=repo_path,
                capture_output=True,
                text=True,
                check=check,
            )
        except subprocess.CalledProcessError as e:
            raise ToolVCSError(f"Git command failed: {e.stderr}") from e
        except Exception as e:
            raise ToolVCSError(f"Git command failed: {e}") from e

    def status(self, repo_path: Path) -> VCSStatus:
        """Get repository status."""
        # Get current branch
        result = self._run_git(repo_path, "branch", "--show-current")
        branch = result.stdout.strip() or "HEAD"

        # Get status
        result = self._run_git(repo_path, "status", "--porcelain")
        # Use rstrip() to preserve leading spaces in porcelain format (e.g., " M file.txt")
        output = result.stdout.rstrip("\n")
        lines = output.split("\n") if output else []

        modified = []
        untracked = []
        for line in lines:
            if not line or len(line) < 4:
                continue
            status = line[:2]
            # Porcelain format: XY PATH (XY is 2 chars, then space, then path)
            # Handle both space-separated and tab-separated formats
            filepath = line[3:].strip()
            if status == "??":
                untracked.append(filepath)
            elif status.strip():  # Any non-empty status indicates modification
                modified.append(filepath)

        # Get ahead/behind
        ahead = 0
        behind = 0
        try:
            result = self._run_git(
                repo_path,
                "rev-list",
                "--left-right",
                "--count",
                f"{branch}...@{{upstream}}",
                check=False,
            )
            if result.returncode == 0 and result.stdout.strip():
                parts = result.stdout.strip().split()
                if len(parts) == 2:
                    ahead = int(parts[0])
                    behind = int(parts[1])
        except Exception:
            pass  # No upstream or other issue

        return VCSStatus(
            branch=branch,
            is_clean=len(modified) == 0 and len(untracked) == 0,
            modified_files=tuple(modified),
            untracked_files=tuple(untracked),
            ahead=ahead,
            behind=behind,
        )

    def commit(
        self,
        repo_path: Path,
        message: str,
        files: list[str] | None = None,
    ) -> str:
        """Commit changes to repository."""
        # Validate files don't escape repo root
        if files:
            for f in files:
                if ".." in f:
                    raise ToolVCSError(f"Path traversal not allowed in files: {f}")
                # Add files to staging
                self._run_git(repo_path, "add", f)
        else:
            # Stage all changes
            self._run_git(repo_path, "add", "-A")

        # Commit
        self._run_git(repo_path, "commit", "-m", message)

        # Get commit hash
        result = self._run_git(repo_path, "rev-parse", "HEAD")
        return result.stdout.strip()

    def push(
        self,
        repo_path: Path,
        remote: str = "origin",
        branch: str | None = None,
    ) -> None:
        """Push commits to remote."""
        args = ["push", remote]
        if branch:
            args.append(branch)

        self._run_git(repo_path, *args)


class PathValidatedVCS(VersionControlPort):
    """Wrapper that validates repo_path before delegating to underlying adapter.

    This is the recommended adapter for production use. Validates repo_path
    against PathSecurityPolicy before delegating to the raw adapter.
    """

    def __init__(self, delegate: VersionControlPort, policy: PathSecurityPolicy):
        """Initialize with delegate adapter and security policy.

        Args:
            delegate: Underlying VCS adapter
            policy: Path security policy for validation
        """
        self._delegate = delegate
        self._policy = policy

    def status(self, repo_path: Path) -> VCSStatus:
        """Get status with path validation."""
        return self._delegate.status(self._policy.validate(repo_path))

    def commit(
        self,
        repo_path: Path,
        message: str,
        files: list[str] | None = None,
    ) -> str:
        """Commit with path validation."""
        return self._delegate.commit(self._policy.validate(repo_path), message, files)

    def push(
        self,
        repo_path: Path,
        remote: str = "origin",
        branch: str | None = None,
    ) -> None:
        """Push with path validation."""
        self._delegate.push(self._policy.validate(repo_path), remote, branch)
