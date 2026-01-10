"""
Redaction utilities for safe configuration logging.
"""

import re
from typing import Any


# Keys that should always be redacted
REDACTED_KEYS = {
    "password",
    "secret",
    "token",
    "api_key",
    "apiKey",
    "private_key",
    "privateKey",
    "client_secret",
    "clientSecret",
    "access_token",
    "accessToken",
    "refresh_token",
    "refreshToken",
}


def _is_redacted_key(key: str) -> bool:
    """Check if a key should be redacted."""
    key_lower = key.lower()
    return any(redacted in key_lower for redacted in REDACTED_KEYS)


def _redact_dsn(value: str) -> str:
    """
    Redact credentials from DSN/URL strings.

    Examples:
        postgresql://user:pass@host:port/db -> postgresql://***:***@host:port/db
        amqp://user:pass@host:port/vhost -> amqp://***:***@host:port/vhost
        redis://:pass@host:port/db -> redis://:***@host:port/db
    """
    if not isinstance(value, str):
        return value

    # Pattern: scheme://[user[:password]@]host[:port][/path]
    # Match credentials in URLs
    patterns = [
        # postgresql://user:pass@host
        (r"(postgresql?://)([^:]+):([^@]+)@", r"\1***:***@"),
        # amqp://user:pass@host
        (r"(amqp://)([^:]+):([^@]+)@", r"\1***:***@"),
        # redis://:pass@host or redis://user:pass@host
        (r"(redis://)([^:]*):([^@]+)@", r"\1***:***@"),
        # http://user:pass@host
        (r"(https?://)([^:]+):([^@]+)@", r"\1***:***@"),
    ]

    result = value
    for pattern, replacement in patterns:
        result = re.sub(pattern, replacement, result)

    return result


def redact_value(value: Any, key: str | None = None) -> Any:
    """
    Redact a single value based on its key or content.

    Args:
        value: Value to potentially redact
        key: Optional key name (used to determine if value should be redacted)

    Returns:
        Redacted value or original value if no redaction needed
    """
    if value is None:
        return value

    # Redact based on key name
    if key and _is_redacted_key(key):
        return "***"

    # Redact DSN/URL strings
    if isinstance(value, str):
        # Check if it looks like a connection string with credentials
        if any(scheme in value for scheme in ["postgresql://", "postgres://", "amqp://", "redis://", "http://", "https://"]):
            return _redact_dsn(value)

    return value


def redact_config(config: dict[str, Any]) -> dict[str, Any]:
    """
    Redact sensitive values from configuration dictionary.

    Preserves structure while redacting values. Handles nested dictionaries
    and common patterns like connection strings.

    Args:
        config: Configuration dictionary to redact

    Returns:
        Redacted configuration dictionary (safe for logging)
    """
    if not isinstance(config, dict):
        return config

    redacted: dict[str, Any] = {}

    for key, value in config.items():
        if isinstance(value, dict):
            # Recursively redact nested dictionaries
            redacted[key] = redact_config(value)
        elif isinstance(value, list):
            # Redact list items (preserve structure)
            redacted[key] = [
                redact_config(item) if isinstance(item, dict) else redact_value(item, key)
                for item in value
            ]
        else:
            # Redact scalar values
            redacted[key] = redact_value(value, key)

    return redacted

