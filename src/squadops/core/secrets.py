"""
Core secret manager for resolving secret:// references in configuration.
This module contains the domain logic for secret resolution and MUST only
import from squadops.ports.secrets (never from adapters).
"""

import re
from typing import Any

from squadops.ports.secrets import SecretProvider


# Core domain exceptions - placed directly in this module
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


class SecretManager:
    """Manages secret resolution with name mapping and provider delegation."""

    # Regex pattern for secret:// references
    # Must match: [A-Za-z][A-Za-z0-9_]* (start with letter, followed by letters/digits/underscores)
    SECRET_REF_PATTERN = re.compile(r"secret://([A-Za-z][A-Za-z0-9_]*)")

    def __init__(self, provider: SecretProvider, name_map: dict[str, str] | None = None):
        """
        Initialize secret manager.

        Args:
            provider: Secret provider instance (must implement SecretProvider from ports)
            name_map: Mapping from logical names to provider keys (defaults to empty dict)
        """
        self.provider = provider
        # MANDATORY: name_map must always be a dict, never None
        self.name_map = name_map if name_map is not None else {}

    def resolve_all_references(self, config_dict: dict[str, Any]) -> dict[str, Any]:
        """
        Resolve all secret:// references in configuration dict.

        MANDATORY: Returns NEW dict, does not mutate original.
        MANDATORY: Skips 'secrets' section (does not traverse or modify it).

        Args:
            config_dict: Configuration dictionary to process

        Returns:
            New dictionary with all secret:// references resolved
        """
        # Return new dict, don't mutate original
        return self._resolve_dict(config_dict, exclude_keys=["secrets"])

    def resolve(self, value: str) -> str:
        """
        Resolve secrets for a single value.

        - If `value` contains one or more `secret://...` references, all are replaced.
        - Otherwise, `value` is treated as a logical secret name and resolved directly.
        """
        if "secret://" in value:
            return self._replace_in_string(value)
        return self._resolve_reference(value)

    def _resolve_dict(self, d: dict[str, Any], exclude_keys: list[str] | None = None) -> dict[str, Any]:
        """
        Recursively resolve secret:// references in a dictionary.

        Args:
            d: Dictionary to process
            exclude_keys: Keys to skip (e.g., ["secrets"])

        Returns:
            New dictionary with resolved references
        """
        if exclude_keys is None:
            exclude_keys = []

        result = {}
        for key, value in d.items():
            if key in exclude_keys:
                # Skip excluded keys (e.g., "secrets" section)
                result[key] = value
            elif isinstance(value, dict):
                # Recursively process nested dicts
                result[key] = self._resolve_dict(value, exclude_keys=[])
            elif isinstance(value, list):
                # Recursively process lists
                result[key] = self._resolve_list(value)
            elif isinstance(value, str):
                # Process string values
                result[key] = self._replace_in_string(value)
            else:
                # Other types (int, bool, etc.) - no processing needed
                result[key] = value

        return result

    def _resolve_list(self, lst: list[Any]) -> list[Any]:
        """
        Recursively resolve secret:// references in a list.

        Args:
            lst: List to process

        Returns:
            New list with resolved references
        """
        result = []
        for item in lst:
            if isinstance(item, dict):
                result.append(self._resolve_dict(item, exclude_keys=[]))
            elif isinstance(item, list):
                result.append(self._resolve_list(item))
            elif isinstance(item, str):
                result.append(self._replace_in_string(item))
            else:
                result.append(item)

        return result

    def _replace_in_string(self, value: str) -> str:
        """
        Replace all secret:// references in a string with resolved values.

        Args:
            value: String value that may contain secret:// references

        Returns:
            String with all secret:// references replaced

        Raises:
            InvalidSecretReferenceError: If logical name format is invalid
            SecretResolutionError: If resolved value contains secret:// (recursive reference)
        """
        def replace_match(match: re.Match[str]) -> str:
            logical_name = match.group(1)
            resolved_value = self._resolve_reference(logical_name)
            return resolved_value

        # Replace all secret:// references
        result = self.SECRET_REF_PATTERN.sub(replace_match, value)

        # Check for recursive references (resolved value contains secret://)
        if "secret://" in result:
            # This means a resolved secret value itself contained secret://
            # This is forbidden (no chained/recursive references)
            raise SecretResolutionError(
                f"Resolved secret value contains 'secret://' reference (recursive/chained references are forbidden)"
            )

        return result

    def _resolve_reference(self, logical_name: str) -> str:
        """
        Resolve a single secret reference by logical name.

        Args:
            logical_name: Logical secret name (must match [A-Za-z][A-Za-z0-9_]*)

        Returns:
            Resolved secret value

        Raises:
            InvalidSecretReferenceError: If logical name format is invalid
            SecretResolutionError: If resolution fails
        """
        # Validate logical name format
        # Use fullmatch to ensure entire string matches (not just a prefix)
        full_ref = f"secret://{logical_name}"
        if not self.SECRET_REF_PATTERN.fullmatch(full_ref):
            raise InvalidSecretReferenceError(
                logical_name=logical_name,
                reason=f"Logical name '{logical_name}' does not match pattern [A-Za-z][A-Za-z0-9_]*",
            )

        # Resolve provider key using name_map
        provider_key = self.name_map.get(logical_name, logical_name)

        # Delegate to provider
        try:
            resolved_value = self.provider.resolve(provider_key)
        except Exception as e:
            if isinstance(e, SecretResolutionError):
                raise
            raise SecretResolutionError(
                f"Failed to resolve secret '{logical_name}': {e}"
            ) from e

        return resolved_value

    @staticmethod
    def has_secret_references(config_dict: dict[str, Any], exclude_keys: list[str] | None = None) -> bool:
        """
        Check if configuration dict contains any secret:// references.

        Args:
            config_dict: Configuration dictionary to scan
            exclude_keys: Keys to exclude from scanning (e.g., ["secrets"])

        Returns:
            True if any secret:// references are found
        """
        if exclude_keys is None:
            exclude_keys = []

        def scan_value(value: Any) -> bool:
            """Recursively scan a value for secret:// references."""
            if isinstance(value, dict):
                for key, val in value.items():
                    if key not in exclude_keys:
                        if scan_value(val):
                            return True
            elif isinstance(value, list):
                for item in value:
                    if scan_value(item):
                        return True
            elif isinstance(value, str):
                if SecretManager.SECRET_REF_PATTERN.search(value):
                    return True
            return False

        return scan_value(config_dict)
