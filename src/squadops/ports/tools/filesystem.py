"""FileSystem port interface.

Abstract base class for filesystem adapters.
Part of SIP-0.8.7 Infrastructure Ports Migration.
"""

from abc import ABC, abstractmethod
from pathlib import Path


class FileSystemPort(ABC):
    """Port interface for filesystem operations.

    Adapters implement raw filesystem operations.
    Path validation is handled by PathValidatedFileSystem wrapper.
    """

    @abstractmethod
    def read(self, path: Path) -> str:
        """Read file contents.

        Args:
            path: Absolute path to file

        Returns:
            File contents as string

        Raises:
            ToolFileNotFoundError: File not found
            ToolPermissionError: Permission denied
            ToolIOError: I/O error
        """
        ...

    @abstractmethod
    def write(self, path: Path, content: str) -> None:
        """Write content to file.

        Uses atomic write (temp file + rename) for safety.

        Args:
            path: Absolute path to file
            content: Content to write

        Raises:
            ToolPermissionError: Permission denied
            ToolIOError: I/O error
        """
        ...

    @abstractmethod
    def exists(self, path: Path) -> bool:
        """Check if path exists.

        Args:
            path: Absolute path to check

        Returns:
            True if path exists
        """
        ...

    @abstractmethod
    def list_dir(self, path: Path, pattern: str | None = None) -> list[Path]:
        """List directory contents.

        Args:
            path: Absolute path to directory
            pattern: Optional glob pattern to filter results

        Returns:
            List of paths in directory

        Raises:
            ToolFileNotFoundError: Directory not found
            ToolPermissionError: Permission denied
        """
        ...

    @abstractmethod
    def mkdir(self, path: Path, parents: bool = True) -> None:
        """Create directory.

        Args:
            path: Absolute path to directory
            parents: If True, create parent directories as needed

        Raises:
            ToolPermissionError: Permission denied
            ToolIOError: I/O error
        """
        ...

    @abstractmethod
    def delete(self, path: Path) -> None:
        """Delete file or directory.

        Args:
            path: Absolute path to delete

        Raises:
            ToolFileNotFoundError: Path not found
            ToolPermissionError: Permission denied
            ToolIOError: I/O error
        """
        ...
