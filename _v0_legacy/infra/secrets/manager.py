"""
Secret manager for resolving secret:// references in configuration.
"""

import re
from typing import Any

from infra.config.schema import SecretsConfig
from infra.secrets.docker_provider import DockerSecretProvider
from infra.secrets.env_provider import EnvProvider
from infra.secrets.exceptions import InvalidSecretReferenceError, SecretResolutionError
from infra.secrets.file_provider import FileProvider
from infra.secrets.provider import SecretProvider


class SecretManager:
    """Manages secret resolution with name mapping and provider delegation."""

    # Regex pattern for secret:// references
    # Must match: [A-Za-z][A-Za-z0-9_]* (start with letter, followed by letters/digits/underscores)
    SECRET_REF_PATTERN = re.compile(r"secret://([A-Za-z][A-Za-z0-9_]*)")

    def __init__(self, provider: SecretProvider, name_map: dict[str, str]):
        """
        Initialize secret manager.

        Args:
            provider: Secret provider instance
            name_map: Mapping from logical names to provider keys
        """
        self.provider = provider
        # MANDATORY: name_map must always be a dict, never None
        self.name_map = name_map if name_map is not None else {}

    @classmethod
    def from_config(cls, secrets_config: SecretsConfig) -> "SecretManager":
        """
        Create SecretManager from validated SecretsConfig.

        MANDATORY: Normalizes name_map to {} if None.

        Args:
            secrets_config: Validated SecretsConfig instance

        Returns:
            SecretManager instance
        """
        # MANDATORY: Normalize name_map to {} if None
        name_map = secrets_config.name_map if secrets_config.name_map is not None else {}

        # Create provider based on config
        if secrets_config.provider == "env":
            # Default env_prefix to "SQUADOPS_" if not provided
            env_prefix = secrets_config.env_prefix
            if env_prefix is None:
                env_prefix = "SQUADOPS_"
            provider = EnvProvider(env_prefix=env_prefix)
        elif secrets_config.provider == "file":
            if secrets_config.file_dir is None:
                raise ValueError("file_dir is required when provider=file")
            provider = FileProvider(file_dir=secrets_config.file_dir)
        elif secrets_config.provider == "docker_secret":
            provider = DockerSecretProvider()
        else:
            raise ValueError(f"Unknown secrets provider: {secrets_config.provider}")

        return cls(provider=provider, name_map=name_map)

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
    def _has_secret_references(config_dict: dict[str, Any], exclude_keys: list[str] | None = None) -> bool:
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

