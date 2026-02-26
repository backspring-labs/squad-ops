"""Unit tests for PathSecurityPolicy."""

from pathlib import Path

import pytest

from squadops.tools.security import PathSecurityError, PathSecurityPolicy


class TestPathSecurityPolicy:
    """Tests for PathSecurityPolicy."""

    def test_requires_allowed_roots(self):
        """Must provide allowed_roots."""
        with pytest.raises(ValueError, match="allowed_roots must be explicitly configured"):
            PathSecurityPolicy(allowed_roots=())

    def test_valid_path_under_root(self, tmp_path):
        """Valid absolute path under allowed root passes."""
        policy = PathSecurityPolicy(allowed_roots=(tmp_path,))
        test_file = tmp_path / "test.txt"
        test_file.touch()

        result = policy.validate(test_file)
        assert result == test_file.resolve()

    def test_rejects_relative_path(self, tmp_path):
        """Relative paths are rejected."""
        policy = PathSecurityPolicy(allowed_roots=(tmp_path,))

        with pytest.raises(PathSecurityError, match="Path must be absolute"):
            policy.validate(Path("relative/path.txt"))

    def test_rejects_path_traversal(self, tmp_path):
        """Paths with '..' are rejected."""
        policy = PathSecurityPolicy(allowed_roots=(tmp_path,))

        with pytest.raises(PathSecurityError, match="Path traversal not allowed"):
            policy.validate(tmp_path / "subdir" / ".." / ".." / "escape.txt")

    def test_rejects_path_outside_roots(self, tmp_path):
        """Paths outside allowed roots are rejected."""
        policy = PathSecurityPolicy(allowed_roots=(tmp_path / "allowed",))
        (tmp_path / "allowed").mkdir()

        outside_path = tmp_path / "outside" / "file.txt"
        (tmp_path / "outside").mkdir()

        with pytest.raises(PathSecurityError, match="Path outside allowed roots"):
            policy.validate(outside_path)

    def test_multiple_allowed_roots(self, tmp_path):
        """Paths under any allowed root pass."""
        root1 = tmp_path / "root1"
        root2 = tmp_path / "root2"
        root1.mkdir()
        root2.mkdir()

        policy = PathSecurityPolicy(allowed_roots=(root1, root2))

        file1 = root1 / "file.txt"
        file2 = root2 / "file.txt"
        file1.touch()
        file2.touch()

        # Both should pass
        assert policy.validate(file1) == file1.resolve()
        assert policy.validate(file2) == file2.resolve()

    def test_symlink_resolution(self, tmp_path):
        """Symlinks are resolved before checking."""
        allowed = tmp_path / "allowed"
        outside = tmp_path / "outside"
        allowed.mkdir()
        outside.mkdir()

        # Create a symlink inside allowed that points outside
        symlink = allowed / "sneaky_link"
        target = outside / "secret.txt"
        target.touch()

        try:
            symlink.symlink_to(target)
        except OSError:
            pytest.skip("Symlinks not supported on this platform")

        policy = PathSecurityPolicy(allowed_roots=(allowed,))

        # Should reject because resolved path is outside
        with pytest.raises(PathSecurityError, match="Path outside allowed roots"):
            policy.validate(symlink)

    def test_allowed_roots_property(self, tmp_path):
        """Can access allowed_roots property."""
        policy = PathSecurityPolicy(allowed_roots=(tmp_path,))
        assert policy.allowed_roots == (tmp_path.resolve(),)

    def test_nested_path_under_root(self, tmp_path):
        """Deeply nested paths under root pass."""
        policy = PathSecurityPolicy(allowed_roots=(tmp_path,))

        deep_path = tmp_path / "a" / "b" / "c" / "d" / "file.txt"
        deep_path.parent.mkdir(parents=True)
        deep_path.touch()

        result = policy.validate(deep_path)
        assert result == deep_path.resolve()
