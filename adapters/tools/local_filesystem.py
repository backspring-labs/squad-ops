"""Local filesystem adapter.

Implementation of FileSystemPort for local filesystem operations.
Part of SIP-0.8.7 Infrastructure Ports Migration.
"""

import os
import shutil
import tempfile
from pathlib import Path

from squadops.ports.tools.filesystem import FileSystemPort
from squadops.tools.exceptions import (
    ToolFileNotFoundError,
    ToolIOError,
    ToolPermissionError,
)
from squadops.tools.security import PathSecurityPolicy


class LocalFileSystemAdapter(FileSystemPort):
    """Local filesystem adapter.

    Implements FileSystemPort for local file operations.
    Uses atomic writes (temp file + rename) for safety.

    Note: This is the raw adapter. For production use, wrap with
    PathValidatedFileSystem for path security validation.
    """

    def read(self, path: Path) -> str:
        """Read file contents."""
        try:
            return path.read_text(encoding="utf-8")
        except FileNotFoundError as e:
            raise ToolFileNotFoundError(f"File not found: {path}") from e
        except PermissionError as e:
            raise ToolPermissionError(f"Permission denied: {path}") from e
        except OSError as e:
            raise ToolIOError(f"I/O error reading {path}: {e}") from e

    def write(self, path: Path, content: str) -> None:
        """Write content to file using atomic write."""
        try:
            # Ensure parent directory exists
            path.parent.mkdir(parents=True, exist_ok=True)

            # Atomic write: write to temp file, then rename
            fd, temp_path = tempfile.mkstemp(
                dir=path.parent,
                prefix=f".{path.name}.",
                suffix=".tmp",
            )
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as f:
                    f.write(content)
                # Atomic rename
                os.replace(temp_path, path)
            except Exception:
                # Clean up temp file on error
                try:
                    os.unlink(temp_path)
                except OSError:
                    pass
                raise
        except PermissionError as e:
            raise ToolPermissionError(f"Permission denied: {path}") from e
        except OSError as e:
            raise ToolIOError(f"I/O error writing {path}: {e}") from e

    def exists(self, path: Path) -> bool:
        """Check if path exists."""
        return path.exists()

    def list_dir(self, path: Path, pattern: str | None = None) -> list[Path]:
        """List directory contents."""
        try:
            if not path.is_dir():
                raise ToolFileNotFoundError(f"Directory not found: {path}")

            if pattern:
                return list(path.glob(pattern))
            return list(path.iterdir())
        except PermissionError as e:
            raise ToolPermissionError(f"Permission denied: {path}") from e
        except OSError as e:
            raise ToolIOError(f"I/O error listing {path}: {e}") from e

    def mkdir(self, path: Path, parents: bool = True) -> None:
        """Create directory."""
        try:
            path.mkdir(parents=parents, exist_ok=True)
        except PermissionError as e:
            raise ToolPermissionError(f"Permission denied: {path}") from e
        except OSError as e:
            raise ToolIOError(f"I/O error creating directory {path}: {e}") from e

    def delete(self, path: Path) -> None:
        """Delete file or directory."""
        try:
            if not path.exists():
                raise ToolFileNotFoundError(f"Path not found: {path}")

            if path.is_dir():
                shutil.rmtree(path)
            else:
                path.unlink()
        except FileNotFoundError as e:
            raise ToolFileNotFoundError(f"Path not found: {path}") from e
        except PermissionError as e:
            raise ToolPermissionError(f"Permission denied: {path}") from e
        except OSError as e:
            raise ToolIOError(f"I/O error deleting {path}: {e}") from e


class PathValidatedFileSystem(FileSystemPort):
    """Wrapper that validates paths before delegating to underlying adapter.

    This is the recommended adapter for production use. Validates all paths
    against PathSecurityPolicy before delegating to the raw adapter.
    """

    def __init__(self, delegate: FileSystemPort, policy: PathSecurityPolicy):
        """Initialize with delegate adapter and security policy.

        Args:
            delegate: Underlying filesystem adapter
            policy: Path security policy for validation
        """
        self._delegate = delegate
        self._policy = policy

    def read(self, path: Path) -> str:
        """Read file with path validation."""
        return self._delegate.read(self._policy.validate(path))

    def write(self, path: Path, content: str) -> None:
        """Write file with path validation."""
        self._delegate.write(self._policy.validate(path), content)

    def exists(self, path: Path) -> bool:
        """Check existence with path validation."""
        return self._delegate.exists(self._policy.validate(path))

    def list_dir(self, path: Path, pattern: str | None = None) -> list[Path]:
        """List directory with path validation."""
        return self._delegate.list_dir(self._policy.validate(path), pattern)

    def mkdir(self, path: Path, parents: bool = True) -> None:
        """Create directory with path validation."""
        self._delegate.mkdir(self._policy.validate(path), parents)

    def delete(self, path: Path) -> None:
        """Delete with path validation."""
        self._delegate.delete(self._policy.validate(path))
