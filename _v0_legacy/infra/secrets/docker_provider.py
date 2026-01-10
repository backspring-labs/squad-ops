"""
Docker secrets provider (reads from /run/secrets).
"""

from pathlib import Path

from infra.secrets.exceptions import SecretNotFoundError
from infra.secrets.provider import SecretProvider


class DockerSecretProvider(SecretProvider):
    """Secret provider that reads from Docker's /run/secrets directory."""

    def __init__(self, secrets_dir: Path | None = None):
        """
        Initialize Docker secret provider.

        Args:
            secrets_dir: Directory containing Docker secrets (default: /run/secrets)
        """
        if secrets_dir is None:
            secrets_dir = Path("/run/secrets")
        elif not isinstance(secrets_dir, Path):
            secrets_dir = Path(secrets_dir)

        self.secrets_dir = secrets_dir.resolve()

    @property
    def provider_name(self) -> str:
        """Return provider name."""
        return "docker_secret"

    def resolve(self, provider_key: str) -> str:
        """
        Resolve secret from Docker secrets directory.

        Args:
            provider_key: Secret key (used as-is, no casing or normalization)

        Returns:
            Secret value from file (stripped of whitespace)

        Raises:
            SecretNotFoundError: If secret file does not exist or cannot be read
        """
        # Use provider_key as-is (no casing or normalization)
        secret_path = self.secrets_dir / provider_key

        if not secret_path.exists():
            raise SecretNotFoundError(
                provider_key=provider_key,
                provider_name=self.provider_name,
                message=f"Docker secret does not exist: {secret_path}",
            )

        if not secret_path.is_file():
            raise SecretNotFoundError(
                provider_key=provider_key,
                provider_name=self.provider_name,
                message=f"Docker secret path is not a file: {secret_path}",
            )

        try:
            value = secret_path.read_text(encoding="utf-8").strip()
            if not value:
                raise SecretNotFoundError(
                    provider_key=provider_key,
                    provider_name=self.provider_name,
                    message=f"Docker secret file is empty: {secret_path}",
                )
            return value
        except Exception as e:
            raise SecretNotFoundError(
                provider_key=provider_key,
                provider_name=self.provider_name,
                message=f"Failed to read Docker secret {secret_path}: {e}",
            ) from e

    def exists(self, provider_key: str) -> bool:
        """
        Check if Docker secret exists and is readable.

        Args:
            provider_key: Secret key (used as-is)

        Returns:
            True if secret file exists and is readable
        """
        secret_path = self.secrets_dir / provider_key
        return secret_path.exists() and secret_path.is_file() and secret_path.is_file()

