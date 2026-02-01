"""Unit tests for VCS adapters."""
import pytest
import subprocess
from pathlib import Path
from unittest.mock import patch, MagicMock

from adapters.tools.git import GitAdapter, PathValidatedVCS
from squadops.tools.exceptions import ToolVCSError
from squadops.tools.security import PathSecurityError, PathSecurityPolicy


class TestGitAdapter:
    """Tests for GitAdapter."""

    def test_status_clean_repo(self, tmp_path):
        """Test status on a clean git repo."""
        # Initialize a git repo
        subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True)
        subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=tmp_path, capture_output=True)
        subprocess.run(["git", "config", "user.name", "Test"], cwd=tmp_path, capture_output=True)

        # Create and commit a file
        (tmp_path / "file.txt").write_text("hello")
        subprocess.run(["git", "add", "."], cwd=tmp_path, capture_output=True)
        subprocess.run(["git", "commit", "-m", "initial"], cwd=tmp_path, capture_output=True)

        adapter = GitAdapter()
        status = adapter.status(tmp_path)

        assert status.is_clean is True
        assert status.modified_files == ()
        assert status.untracked_files == ()

    def test_status_modified_files(self, tmp_path):
        """Test status with modified files."""
        # Initialize a git repo
        subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True)
        subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=tmp_path, capture_output=True)
        subprocess.run(["git", "config", "user.name", "Test"], cwd=tmp_path, capture_output=True)

        # Create and commit a file
        (tmp_path / "file.txt").write_text("hello")
        subprocess.run(["git", "add", "."], cwd=tmp_path, capture_output=True)
        subprocess.run(["git", "commit", "-m", "initial"], cwd=tmp_path, capture_output=True)

        # Modify the file
        (tmp_path / "file.txt").write_text("modified")

        adapter = GitAdapter()
        status = adapter.status(tmp_path)

        assert status.is_clean is False
        assert "file.txt" in status.modified_files

    def test_status_untracked_files(self, tmp_path):
        """Test status with untracked files."""
        # Initialize a git repo
        subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True)
        subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=tmp_path, capture_output=True)
        subprocess.run(["git", "config", "user.name", "Test"], cwd=tmp_path, capture_output=True)

        # Create a file without staging
        (tmp_path / "untracked.txt").write_text("new file")

        adapter = GitAdapter()
        status = adapter.status(tmp_path)

        assert status.is_clean is False
        assert "untracked.txt" in status.untracked_files

    def test_commit_rejects_path_traversal(self, tmp_path):
        """Test that commit rejects files with path traversal."""
        adapter = GitAdapter()

        with pytest.raises(ToolVCSError, match="Path traversal not allowed"):
            adapter.commit(tmp_path, "test", files=["../escape.txt"])


class TestPathValidatedVCS:
    """Tests for PathValidatedVCS wrapper."""

    def test_validates_repo_path(self, tmp_path):
        """Test that repo_path is validated."""
        allowed = tmp_path / "allowed"
        allowed.mkdir()

        # Initialize git in allowed
        subprocess.run(["git", "init"], cwd=allowed, capture_output=True)
        subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=allowed, capture_output=True)
        subprocess.run(["git", "config", "user.name", "Test"], cwd=allowed, capture_output=True)

        raw = GitAdapter()
        policy = PathSecurityPolicy(allowed_roots=(allowed,))
        adapter = PathValidatedVCS(raw, policy)

        # Valid path works
        status = adapter.status(allowed)
        assert status.branch is not None

    def test_rejects_repo_outside_root(self, tmp_path):
        """Test that repo_path outside allowed roots is rejected."""
        allowed = tmp_path / "allowed"
        outside = tmp_path / "outside"
        allowed.mkdir()
        outside.mkdir()

        # Initialize git in outside
        subprocess.run(["git", "init"], cwd=outside, capture_output=True)

        raw = GitAdapter()
        policy = PathSecurityPolicy(allowed_roots=(allowed,))
        adapter = PathValidatedVCS(raw, policy)

        with pytest.raises(PathSecurityError, match="outside allowed roots"):
            adapter.status(outside)
