"""
Verification tests for squadops.core.secrets module.
Tests core purity and secret resolution with mock provider injection.
"""

import pytest

from squadops.core.secrets import (
    SecretManager,
    SecretNotFoundError,
    SecretResolutionError,
)
from squadops.ports.secrets import SecretProvider


class MockSecretProvider(SecretProvider):
    """Mock provider for testing core secrets module."""

    def __init__(self, secrets: dict[str, str]):
        """
        Initialize mock provider with a dictionary of secrets.

        Args:
            secrets: Dictionary mapping provider keys to secret values
        """
        self._secrets = secrets

    @property
    def provider_name(self) -> str:
        """Return provider name."""
        return "mock"

    def resolve(self, provider_key: str) -> str:
        """
        Resolve secret from mock dictionary.

        Args:
            provider_key: Provider key

        Returns:
            Secret value

        Raises:
            SecretNotFoundError: If secret not found
        """
        if provider_key not in self._secrets:
            raise SecretNotFoundError(
                provider_key=provider_key,
                provider_name=self.provider_name,
                message=f"Secret '{provider_key}' not found in mock provider",
            )
        return self._secrets[provider_key]

    def exists(self, provider_key: str) -> bool:
        """
        Check if secret exists in mock dictionary.

        Args:
            provider_key: Provider key

        Returns:
            True if secret exists
        """
        return provider_key in self._secrets


class TestSecretManagerCorePurity:
    """Test that core secrets module maintains purity (no adapter imports)."""

    def test_core_imports_only_from_ports(self):
        """Verify that core.secrets only imports from ports.secrets."""
        import inspect

        import squadops.core.secrets as secrets_module

        # Get all imports in the module
        imports = []
        for name, obj in inspect.getmembers(secrets_module):
            if inspect.ismodule(obj):
                imports.append(obj.__name__)

        # Check that no adapter modules are imported
        adapter_imports = [imp for imp in imports if "adapters" in imp]
        assert len(adapter_imports) == 0, f"Core module imports adapters: {adapter_imports}"

    def test_core_does_not_import_factory(self):
        """Verify that core.secrets does not import the factory."""
        import inspect

        import squadops.core.secrets as secrets_module

        # Check module source for factory imports
        source = inspect.getsource(secrets_module)
        assert "adapters.secrets.factory" not in source
        assert "factory" not in source.lower() or "from" not in source.lower()


class TestSecretManagerWithMockProvider:
    """Test SecretManager with injected mock provider."""

    def test_resolve_simple_reference(self):
        """Test resolving a simple secret:// reference."""
        provider = MockSecretProvider(secrets={"db_password": "secret123"})
        manager = SecretManager(provider=provider, name_map={})

        result = manager._resolve_reference("db_password")
        assert result == "secret123"

    def test_resolve_with_name_mapping(self):
        """Test resolving with name mapping."""
        provider = MockSecretProvider(secrets={"DB_PASS": "mapped_secret"})
        manager = SecretManager(
            provider=provider,
            name_map={"db_password": "DB_PASS"},
        )

        result = manager._resolve_reference("db_password")
        assert result == "mapped_secret"

    def test_resolve_without_name_mapping_fallback(self):
        """Test that missing name_map entry falls back to logical_name."""
        provider = MockSecretProvider(secrets={"db_password": "fallback_secret"})
        manager = SecretManager(provider=provider, name_map={"other": "OTHER"})

        result = manager._resolve_reference("db_password")
        assert result == "fallback_secret"

    def test_resolve_invalid_logical_name(self):
        """Test that invalid logical names are rejected.

        Invalid names don't match the secret:// pattern, so they're left unchanged
        and then detected as unresolved references (SecretResolutionError).
        """
        provider = MockSecretProvider(secrets={})
        manager = SecretManager(provider=provider, name_map={})

        invalid_names = ["123invalid", "_invalid", "invalid-name", "invalid.name", ""]
        for name in invalid_names:
            # Invalid names don't match the pattern, so they trigger
            # the recursive reference check (unresolved secret:// in result)
            with pytest.raises(SecretResolutionError):
                manager._replace_in_string(f"secret://{name}")

    def test_replace_in_string_simple(self):
        """Test inline string replacement of secret:// references."""
        provider = MockSecretProvider(secrets={"db_password": "secret123"})
        manager = SecretManager(provider=provider, name_map={})

        value = "postgresql://user:secret://db_password@host:5432/db"
        result = manager._replace_in_string(value)
        assert result == "postgresql://user:secret123@host:5432/db"

    def test_replace_in_string_multiple(self):
        """Test inline string replacement with multiple references."""
        provider = MockSecretProvider(
            secrets={"db_password": "db123", "rabbitmq_password": "mq123"}
        )
        manager = SecretManager(provider=provider, name_map={})

        value = "db=secret://db_password&mq=secret://rabbitmq_password"
        result = manager._replace_in_string(value)
        assert result == "db=db123&mq=mq123"

    def test_replace_in_string_recursive_detection(self):
        """Test that recursive/chained references are detected."""
        provider = MockSecretProvider(secrets={"recursive": "secret://other_secret"})
        manager = SecretManager(provider=provider, name_map={})

        # The recursive detection happens in _replace_in_string after resolution
        with pytest.raises(SecretResolutionError, match="recursive"):
            manager._replace_in_string("secret://recursive")

    def test_resolve_all_references_dict(self):
        """Test resolving references in a dictionary."""
        provider = MockSecretProvider(
            secrets={"db_password": "db123", "rabbitmq_password": "mq123"}
        )
        manager = SecretManager(provider=provider, name_map={})

        config_dict = {
            "db": {"url": "postgresql://user:secret://db_password@host:5432/db"},
            "comms": {"rabbitmq": {"url": "amqp://user:secret://rabbitmq_password@host:5672/"}},
            "secrets": {"provider": "env"},
        }

        result = manager.resolve_all_references(config_dict)

        assert result["db"]["url"] == "postgresql://user:db123@host:5432/db"
        assert result["comms"]["rabbitmq"]["url"] == "amqp://user:mq123@host:5672/"
        # secrets section should be unchanged
        assert result["secrets"] == config_dict["secrets"]
        # Original should not be mutated
        assert "secret://" in config_dict["db"]["url"]

    def test_resolve_all_references_list(self):
        """Test resolving references in a list."""
        provider = MockSecretProvider(secrets={"secret1": "value1", "secret2": "value2"})
        manager = SecretManager(provider=provider, name_map={})

        config_list = [
            "secret://secret1",
            {"nested": "secret://secret2"},
            ["nested_list", "secret://secret1"],
        ]

        result = manager.resolve_all_references({"list": config_list})

        assert result["list"][0] == "value1"
        assert result["list"][1]["nested"] == "value2"
        assert result["list"][2][1] == "value1"
        # Original should not be mutated
        assert config_list[0] == "secret://secret1"

    def test_resolve_all_references_returns_new_dict(self):
        """Test that resolve_all_references returns a new dict."""
        provider = MockSecretProvider(secrets={"secret": "value"})
        manager = SecretManager(provider=provider, name_map={})

        original = {"key": "secret://secret"}
        result = manager.resolve_all_references(original)

        assert result is not original
        assert result["key"] == "value"
        assert original["key"] == "secret://secret"

    def test_has_secret_references(self):
        """Test has_secret_references static method."""
        config_dict = {
            "db": {"url": "postgresql://user:secret://db_password@host:5432/db"},
            "comms": {"rabbitmq": {"url": "amqp://user:pass@host:5672/"}},
        }

        assert SecretManager.has_secret_references(config_dict) is True

        config_dict_no_refs = {
            "db": {"url": "postgresql://user:pass@host:5432/db"},
        }

        assert SecretManager.has_secret_references(config_dict_no_refs) is False

    def test_has_secret_references_exclude_keys(self):
        """Test has_secret_references with exclude_keys."""
        config_dict = {
            "db": {"url": "postgresql://user:secret://db_password@host:5432/db"},
            "secrets": {"provider": "env"},
        }

        # Should find references when not excluding secrets
        assert SecretManager.has_secret_references(config_dict, exclude_keys=[]) is True

        # Should still find references when excluding secrets (references are in db section)
        assert SecretManager.has_secret_references(config_dict, exclude_keys=["secrets"]) is True

    def test_error_propagation(self):
        """Test that provider errors are properly propagated."""
        provider = MockSecretProvider(secrets={})
        manager = SecretManager(provider=provider, name_map={})

        # Missing secret should raise SecretNotFoundError
        with pytest.raises(SecretNotFoundError):
            manager._resolve_reference("nonexistent")

    def test_name_map_normalization(self):
        """Test that name_map is normalized to {} if None."""
        provider = MockSecretProvider(secrets={})
        manager = SecretManager(provider=provider, name_map=None)

        assert manager.name_map == {}
        assert isinstance(manager.name_map, dict)
