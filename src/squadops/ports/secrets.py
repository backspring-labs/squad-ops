"""
Port interface for secret providers.
Defines the contract that any secrets provider must satisfy.
"""

from abc import ABC, abstractmethod


class SecretProvider(ABC):
    """Abstract base class for secret providers."""

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Return the name of this provider (e.g., 'env', 'file', 'docker_secret')."""
        pass

    @abstractmethod
    def resolve(self, provider_key: str) -> str:
        """
        Resolve a secret value by provider key.

        Args:
            provider_key: Provider-specific key for the secret

        Returns:
            Resolved secret value as string

        Raises:
            SecretNotFoundError: If the secret cannot be found
            SecretResolutionError: For other resolution failures
        """
        pass

    @abstractmethod
    def exists(self, provider_key: str) -> bool:
        """
        Check if a secret exists for the given provider key.

        Args:
            provider_key: Provider-specific key for the secret

        Returns:
            True if the secret exists, False otherwise
        """
        pass
