"""
Factory for creating secret provider instances from configuration.
This factory maps configuration strings to concrete adapter instances.
Called from config loader (outside core), not from core itself.
"""

from pathlib import Path

from adapters.secrets.docker import DockerSecretProvider
from adapters.secrets.env import EnvProvider
from adapters.secrets.file import FileProvider
from squadops.ports.secrets import SecretProvider


def create_provider(
    provider: str,
    env_prefix: str | None = None,
    file_dir: Path | None = None,
) -> SecretProvider:
    """
    Create a secret provider instance based on configuration.

    Args:
        provider: Provider type ('env', 'file', or 'docker_secret')
        env_prefix: Environment variable prefix (for 'env' provider, defaults to 'SQUADOPS_')
        file_dir: Directory containing secret files (required for 'file' provider)

    Returns:
        SecretProvider instance

    Raises:
        ValueError: If provider type is unknown or required parameters are missing
    """
    if provider == "env":
        # Default env_prefix to "SQUADOPS_" if not provided
        if env_prefix is None:
            env_prefix = "SQUADOPS_"
        return EnvProvider(env_prefix=env_prefix)
    elif provider == "file":
        if file_dir is None:
            raise ValueError("file_dir is required when provider=file")
        return FileProvider(file_dir=file_dir)
    elif provider == "docker_secret":
        return DockerSecretProvider()
    else:
        raise ValueError(f"Unknown secrets provider: {provider}")
