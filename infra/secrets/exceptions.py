"""
Custom exceptions for secret resolution failures.
"""


class SecretResolutionError(Exception):
    """Base exception for all secret resolution errors."""

    pass


class SecretNotFoundError(SecretResolutionError):
    """Raised when a secret cannot be found by the provider."""

    def __init__(self, provider_key: str, provider_name: str, message: str | None = None):
        self.provider_key = provider_key
        self.provider_name = provider_name
        msg = message or f"Secret '{provider_key}' not found in {provider_name} provider"
        super().__init__(msg)


class InvalidSecretReferenceError(SecretResolutionError):
    """Raised when a secret reference has an invalid format or logical name."""

    def __init__(self, logical_name: str, reason: str | None = None):
        self.logical_name = logical_name
        msg = reason or f"Invalid secret reference logical name: '{logical_name}'. Must match pattern [A-Za-z][A-Za-z0-9_]*"
        super().__init__(msg)

