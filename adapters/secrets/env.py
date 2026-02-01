"""
Environment variable-based secret provider.
"""

import os

from squadops.core.secrets import SecretNotFoundError
from squadops.ports.secrets import SecretProvider


class EnvProvider(SecretProvider):
    """Secret provider that reads from environment variables."""

    def __init__(self, env_prefix: str = "SQUADOPS_"):
        """
        Initialize environment variable provider.

        Args:
            env_prefix: Prefix for environment variable names (default: "SQUADOPS_")
                       Must end with "_" (will be normalized if not)
        """
        # Normalize env_prefix to end with "_"
        if not env_prefix.endswith("_"):
            env_prefix = env_prefix + "_"
        self.env_prefix = env_prefix

    @property
    def provider_name(self) -> str:
        """Return provider name."""
        return "env"

    def resolve(self, provider_key: str) -> str:
        """
        Resolve secret from environment variable.

        Args:
            provider_key: Logical name (will be uppercased and prefixed)

        Returns:
            Secret value from environment variable

        Raises:
            SecretNotFoundError: If environment variable is not set
        """
        # Uppercase provider key and prepend prefix
        env_var_name = self.env_prefix + provider_key.upper()

        if env_var_name not in os.environ:
            raise SecretNotFoundError(
                provider_key=provider_key,
                provider_name=self.provider_name,
                message=f"Environment variable '{env_var_name}' not set",
            )

        value = os.environ[env_var_name]
        if not value:
            raise SecretNotFoundError(
                provider_key=provider_key,
                provider_name=self.provider_name,
                message=f"Environment variable '{env_var_name}' is empty",
            )

        return value

    def exists(self, provider_key: str) -> bool:
        """
        Check if environment variable exists and is non-empty.

        Args:
            provider_key: Logical name (will be uppercased and prefixed)

        Returns:
            True if environment variable exists and is non-empty
        """
        env_var_name = self.env_prefix + provider_key.upper()
        return env_var_name in os.environ and bool(os.environ[env_var_name])
