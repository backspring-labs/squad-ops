"""
File-based secret provider.
"""

from pathlib import Path

from infra.secrets.exceptions import SecretNotFoundError
from infra.secrets.provider import SecretProvider


class FileProvider(SecretProvider):
    """Secret provider that reads from local files."""

    def __init__(self, file_dir: Path):
        """
        Initialize file provider.

        Args:
            file_dir: Directory containing secret files
        """
        if not isinstance(file_dir, Path):
            file_dir = Path(file_dir)
        self.file_dir = file_dir.resolve()

        if not self.file_dir.exists():
            raise ValueError(f"Secret file directory does not exist: {self.file_dir}")

        if not self.file_dir.is_dir():
            raise ValueError(f"Secret file path is not a directory: {self.file_dir}")

    @property
    def provider_name(self) -> str:
        """Return provider name."""
        return "file"

    def resolve(self, provider_key: str) -> str:
        """
        Resolve secret from file.

        Args:
            provider_key: Filename (used as-is, no casing or normalization)

        Returns:
            Secret value from file (stripped of whitespace)

        Raises:
            SecretNotFoundError: If file does not exist or cannot be read
        """
        # Use provider_key as-is (no casing or normalization)
        file_path = self.file_dir / provider_key

        if not file_path.exists():
            raise SecretNotFoundError(
                provider_key=provider_key,
                provider_name=self.provider_name,
                message=f"Secret file does not exist: {file_path}",
            )

        if not file_path.is_file():
            raise SecretNotFoundError(
                provider_key=provider_key,
                provider_name=self.provider_name,
                message=f"Secret path is not a file: {file_path}",
            )

        try:
            value = file_path.read_text(encoding="utf-8").strip()
            if not value:
                raise SecretNotFoundError(
                    provider_key=provider_key,
                    provider_name=self.provider_name,
                    message=f"Secret file is empty: {file_path}",
                )
            return value
        except Exception as e:
            raise SecretNotFoundError(
                provider_key=provider_key,
                provider_name=self.provider_name,
                message=f"Failed to read secret file {file_path}: {e}",
            ) from e

    def exists(self, provider_key: str) -> bool:
        """
        Check if secret file exists and is readable.

        Args:
            provider_key: Filename (used as-is)

        Returns:
            True if file exists and is readable
        """
        file_path = self.file_dir / provider_key
        return file_path.exists() and file_path.is_file() and file_path.is_file()

