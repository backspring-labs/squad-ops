"""
Secrets management module for SquadOps.

Provides centralized secret resolution with support for multiple providers
(env, file, docker_secret) and name mapping for cloud portability.
"""

from infra.secrets.exceptions import (
    InvalidSecretReferenceError,
    SecretNotFoundError,
    SecretResolutionError,
)
from infra.secrets.manager import SecretManager
from infra.secrets.provider import SecretProvider

__all__ = [
    "SecretManager",
    "SecretProvider",
    "SecretResolutionError",
    "SecretNotFoundError",
    "InvalidSecretReferenceError",
]

