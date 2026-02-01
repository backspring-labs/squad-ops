"""Unit tests for filesystem adapters."""
import pytest
from pathlib import Path

from adapters.tools.local_filesystem import (
    LocalFileSystemAdapter,
    PathValidatedFileSystem,
)
from squadops.tools.exceptions import ToolFileNotFoundError, ToolPermissionError
from squadops.tools.security import PathSecurityError, PathSecurityPolicy


class TestLocalFileSystemAdapter:
    """Tests for LocalFileSystemAdapter."""

    def test_read_file(self, tmp_path):
        adapter = LocalFileSystemAdapter()
        test_file = tmp_path / "test.txt"
        test_file.write_text("hello world")

        content = adapter.read(test_file)
        assert content == "hello world"

    def test_read_file_not_found(self, tmp_path):
        adapter = LocalFileSystemAdapter()
        with pytest.raises(ToolFileNotFoundError):
            adapter.read(tmp_path / "nonexistent.txt")

    def test_write_file(self, tmp_path):
        adapter = LocalFileSystemAdapter()
        test_file = tmp_path / "test.txt"

        adapter.write(test_file, "hello world")

        assert test_file.read_text() == "hello world"

    def test_write_creates_parent_dirs(self, tmp_path):
        adapter = LocalFileSystemAdapter()
        test_file = tmp_path / "subdir" / "deep" / "test.txt"

        adapter.write(test_file, "content")

        assert test_file.read_text() == "content"

    def test_exists(self, tmp_path):
        adapter = LocalFileSystemAdapter()
        test_file = tmp_path / "test.txt"

        assert adapter.exists(test_file) is False
        test_file.touch()
        assert adapter.exists(test_file) is True

    def test_list_dir(self, tmp_path):
        adapter = LocalFileSystemAdapter()
        (tmp_path / "file1.txt").touch()
        (tmp_path / "file2.txt").touch()
        (tmp_path / "file3.py").touch()

        files = adapter.list_dir(tmp_path)
        assert len(files) == 3

    def test_list_dir_with_pattern(self, tmp_path):
        adapter = LocalFileSystemAdapter()
        (tmp_path / "file1.txt").touch()
        (tmp_path / "file2.txt").touch()
        (tmp_path / "file3.py").touch()

        files = adapter.list_dir(tmp_path, pattern="*.txt")
        assert len(files) == 2

    def test_mkdir(self, tmp_path):
        adapter = LocalFileSystemAdapter()
        new_dir = tmp_path / "new" / "nested" / "dir"

        adapter.mkdir(new_dir)

        assert new_dir.is_dir()

    def test_delete_file(self, tmp_path):
        adapter = LocalFileSystemAdapter()
        test_file = tmp_path / "test.txt"
        test_file.touch()

        adapter.delete(test_file)

        assert not test_file.exists()

    def test_delete_directory(self, tmp_path):
        adapter = LocalFileSystemAdapter()
        test_dir = tmp_path / "testdir"
        test_dir.mkdir()
        (test_dir / "file.txt").touch()

        adapter.delete(test_dir)

        assert not test_dir.exists()

    def test_delete_not_found(self, tmp_path):
        adapter = LocalFileSystemAdapter()
        with pytest.raises(ToolFileNotFoundError):
            adapter.delete(tmp_path / "nonexistent")


class TestPathValidatedFileSystem:
    """Tests for PathValidatedFileSystem wrapper."""

    def test_validates_path_on_read(self, tmp_path):
        raw = LocalFileSystemAdapter()
        policy = PathSecurityPolicy(allowed_roots=(tmp_path,))
        adapter = PathValidatedFileSystem(raw, policy)

        test_file = tmp_path / "test.txt"
        test_file.write_text("hello")

        # Valid path works
        content = adapter.read(test_file)
        assert content == "hello"

    def test_rejects_path_outside_root(self, tmp_path):
        allowed = tmp_path / "allowed"
        allowed.mkdir()

        raw = LocalFileSystemAdapter()
        policy = PathSecurityPolicy(allowed_roots=(allowed,))
        adapter = PathValidatedFileSystem(raw, policy)

        outside = tmp_path / "outside.txt"
        outside.touch()

        with pytest.raises(PathSecurityError, match="outside allowed roots"):
            adapter.read(outside)

    def test_validates_path_on_write(self, tmp_path):
        allowed = tmp_path / "allowed"
        allowed.mkdir()

        raw = LocalFileSystemAdapter()
        policy = PathSecurityPolicy(allowed_roots=(allowed,))
        adapter = PathValidatedFileSystem(raw, policy)

        # Valid path works
        valid_file = allowed / "test.txt"
        adapter.write(valid_file, "content")
        assert valid_file.read_text() == "content"

        # Invalid path rejected
        invalid_file = tmp_path / "outside.txt"
        with pytest.raises(PathSecurityError):
            adapter.write(invalid_file, "content")
