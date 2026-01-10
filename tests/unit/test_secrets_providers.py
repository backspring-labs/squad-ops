"""
Unit tests for secrets management providers and manager.
"""

import os
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from infra.config.schema import SecretsConfig
from infra.secrets.docker_provider import DockerSecretProvider
from infra.secrets.env_provider import EnvProvider
from infra.secrets.exceptions import (
    InvalidSecretReferenceError,
    SecretNotFoundError,
    SecretResolutionError,
)
from infra.secrets.file_provider import FileProvider
from infra.secrets.manager import SecretManager


class TestEnvProvider:
    """Tests for EnvProvider."""

    def test_default_prefix(self):
        """Test that default prefix is SQUADOPS_."""
        provider = EnvProvider()
        assert provider.env_prefix == "SQUADOPS_"
        assert provider.provider_name == "env"

    def test_prefix_normalization(self):
        """Test that prefix is normalized to end with _."""
        provider = EnvProvider(env_prefix="TEST")
        assert provider.env_prefix == "TEST_"

        provider = EnvProvider(env_prefix="TEST_")
        assert provider.env_prefix == "TEST_"

    def test_resolve_success(self):
        """Test successful secret resolution."""
        provider = EnvProvider(env_prefix="TEST_")
        os.environ["TEST_DB_PASSWORD"] = "secret123"
        
        value = provider.resolve("db_password")
        assert value == "secret123"

    def test_resolve_uppercase(self):
        """Test that provider key is uppercased."""
        provider = EnvProvider(env_prefix="TEST_")
        os.environ["TEST_MY_SECRET"] = "value123"
        
        value = provider.resolve("my_secret")
        assert value == "value123"

    def test_resolve_missing(self):
        """Test that missing env var raises SecretNotFoundError."""
        provider = EnvProvider(env_prefix="TEST_")
        
        with pytest.raises(SecretNotFoundError) as exc_info:
            provider.resolve("nonexistent")
        
        assert "TEST_NONEXISTENT" in str(exc_info.value)
        assert exc_info.value.provider_key == "nonexistent"

    def test_resolve_empty(self):
        """Test that empty env var raises SecretNotFoundError."""
        provider = EnvProvider(env_prefix="TEST_")
        os.environ["TEST_EMPTY"] = ""
        
        with pytest.raises(SecretNotFoundError) as exc_info:
            provider.resolve("empty")
        
        assert "empty" in str(exc_info.value)

    def test_exists(self):
        """Test exists() method."""
        provider = EnvProvider(env_prefix="TEST_")
        os.environ["TEST_EXISTS"] = "value"
        
        assert provider.exists("exists") is True
        assert provider.exists("nonexistent") is False


class TestFileProvider:
    """Tests for FileProvider."""

    def test_resolve_success(self, tmp_path):
        """Test successful secret resolution from file."""
        secrets_dir = tmp_path / "secrets"
        secrets_dir.mkdir()
        
        secret_file = secrets_dir / "db_password"
        secret_file.write_text("secret123\n")
        
        provider = FileProvider(file_dir=secrets_dir)
        value = provider.resolve("db_password")
        assert value == "secret123"

    def test_resolve_as_is(self, tmp_path):
        """Test that provider key is used as-is (no casing)."""
        secrets_dir = tmp_path / "secrets"
        secrets_dir.mkdir()
        
        secret_file = secrets_dir / "MySecret"
        secret_file.write_text("value123")
        
        provider = FileProvider(file_dir=secrets_dir)
        value = provider.resolve("MySecret")
        assert value == "value123"

    def test_resolve_missing_file(self, tmp_path):
        """Test that missing file raises SecretNotFoundError."""
        secrets_dir = tmp_path / "secrets"
        secrets_dir.mkdir()
        
        provider = FileProvider(file_dir=secrets_dir)
        
        with pytest.raises(SecretNotFoundError) as exc_info:
            provider.resolve("nonexistent")
        
        assert "nonexistent" in str(exc_info.value)

    def test_resolve_empty_file(self, tmp_path):
        """Test that empty file raises SecretNotFoundError."""
        secrets_dir = tmp_path / "secrets"
        secrets_dir.mkdir()
        
        secret_file = secrets_dir / "empty"
        secret_file.write_text("")
        
        provider = FileProvider(file_dir=secrets_dir)
        
        with pytest.raises(SecretNotFoundError) as exc_info:
            provider.resolve("empty")
        
        assert "empty" in str(exc_info.value)

    def test_invalid_directory(self):
        """Test that invalid directory raises ValueError."""
        with pytest.raises(ValueError, match="does not exist"):
            FileProvider(file_dir=Path("/nonexistent/path"))

    def test_file_not_directory(self, tmp_path):
        """Test that file path (not directory) raises ValueError."""
        file_path = tmp_path / "not_a_dir"
        file_path.write_text("test")
        
        with pytest.raises(ValueError, match="not a directory"):
            FileProvider(file_dir=file_path)

    def test_exists(self, tmp_path):
        """Test exists() method."""
        secrets_dir = tmp_path / "secrets"
        secrets_dir.mkdir()
        
        secret_file = secrets_dir / "exists"
        secret_file.write_text("value")
        
        provider = FileProvider(file_dir=secrets_dir)
        assert provider.exists("exists") is True
        assert provider.exists("nonexistent") is False


class TestDockerSecretProvider:
    """Tests for DockerSecretProvider."""

    def test_resolve_success(self, tmp_path):
        """Test successful secret resolution from Docker secrets."""
        secrets_dir = tmp_path / "run" / "secrets"
        secrets_dir.mkdir(parents=True)
        
        secret_file = secrets_dir / "db_password"
        secret_file.write_text("secret123\n")
        
        provider = DockerSecretProvider(secrets_dir=secrets_dir)
        value = provider.resolve("db_password")
        assert value == "secret123"

    def test_resolve_as_is(self, tmp_path):
        """Test that provider key is used as-is (no casing)."""
        secrets_dir = tmp_path / "run" / "secrets"
        secrets_dir.mkdir(parents=True)
        
        secret_file = secrets_dir / "MySecret"
        secret_file.write_text("value123")
        
        provider = DockerSecretProvider(secrets_dir=secrets_dir)
        value = provider.resolve("MySecret")
        assert value == "value123"

    def test_resolve_missing_secret(self, tmp_path):
        """Test that missing secret raises SecretNotFoundError."""
        secrets_dir = tmp_path / "run" / "secrets"
        secrets_dir.mkdir(parents=True)
        
        provider = DockerSecretProvider(secrets_dir=secrets_dir)
        
        with pytest.raises(SecretNotFoundError) as exc_info:
            provider.resolve("nonexistent")
        
        assert "nonexistent" in str(exc_info.value)

    def test_default_secrets_dir(self):
        """Test that default secrets directory is /run/secrets."""
        provider = DockerSecretProvider()
        assert provider.secrets_dir == Path("/run/secrets").resolve()

    def test_exists(self, tmp_path):
        """Test exists() method."""
        secrets_dir = tmp_path / "run" / "secrets"
        secrets_dir.mkdir(parents=True)
        
        secret_file = secrets_dir / "exists"
        secret_file.write_text("value")
        
        provider = DockerSecretProvider(secrets_dir=secrets_dir)
        assert provider.exists("exists") is True
        assert provider.exists("nonexistent") is False


class TestSecretManager:
    """Tests for SecretManager."""

    def test_from_config_env_provider(self):
        """Test creating manager from env provider config."""
        config = SecretsConfig(
            provider="env",
            env_prefix="TEST_",
            name_map={"db_password": "DB_PASSWORD"},
        )
        
        manager = SecretManager.from_config(config)
        assert manager.provider.provider_name == "env"
        assert manager.name_map == {"db_password": "DB_PASSWORD"}

    def test_from_config_env_provider_default_prefix(self):
        """Test that env provider defaults prefix to SQUADOPS_."""
        config = SecretsConfig(provider="env")
        
        manager = SecretManager.from_config(config)
        assert manager.provider.provider_name == "env"
        assert manager.provider.env_prefix == "SQUADOPS_"

    def test_from_config_file_provider(self, tmp_path):
        """Test creating manager from file provider config."""
        secrets_dir = tmp_path / "secrets"
        secrets_dir.mkdir()
        
        config = SecretsConfig(
            provider="file",
            file_dir=secrets_dir,
            name_map={"db_password": "db_pass"},
        )
        
        manager = SecretManager.from_config(config)
        assert manager.provider.provider_name == "file"
        assert manager.name_map == {"db_password": "db_pass"}

    def test_from_config_docker_provider(self):
        """Test creating manager from docker_secret provider config."""
        config = SecretsConfig(
            provider="docker_secret",
            name_map={"db_password": "db_pass"},
        )
        
        manager = SecretManager.from_config(config)
        assert manager.provider.provider_name == "docker_secret"
        assert manager.name_map == {"db_password": "db_pass"}

    def test_name_map_normalization(self):
        """Test that name_map is normalized to {} if None."""
        config = SecretsConfig(provider="env", name_map=None)
        
        manager = SecretManager.from_config(config)
        assert manager.name_map == {}
        assert isinstance(manager.name_map, dict)

    def test_inline_string_replacement(self):
        """Test inline string replacement of secret:// references."""
        config = SecretsConfig(provider="env", env_prefix="TEST_")
        manager = SecretManager.from_config(config)
        
        os.environ["TEST_DB_PASSWORD"] = "secret123"
        
        value = "postgresql://user:secret://db_password@host:5432/db"
        result = manager._replace_in_string(value)
        assert result == "postgresql://user:secret123@host:5432/db"

    def test_inline_string_replacement_multiple(self):
        """Test inline string replacement with multiple references."""
        config = SecretsConfig(provider="env", env_prefix="TEST_")
        manager = SecretManager.from_config(config)
        
        os.environ["TEST_DB_PASSWORD"] = "db123"
        os.environ["TEST_RABBITMQ_PASSWORD"] = "mq123"
        
        value = "db=secret://db_password&mq=secret://rabbitmq_password"
        result = manager._replace_in_string(value)
        assert result == "db=db123&mq=mq123"

    def test_logical_name_validation_valid(self):
        """Test that valid logical names are accepted."""
        config = SecretsConfig(provider="env", env_prefix="TEST_")
        manager = SecretManager.from_config(config)
        
        os.environ["TEST_VALID_NAME"] = "value"
        
        # Valid names
        valid_names = ["db_password", "my_secret", "Secret123", "a", "A1"]
        for name in valid_names:
            os.environ[f"TEST_{name.upper()}"] = "value"
            result = manager._resolve_reference(name)
            assert result == "value"

    def test_logical_name_validation_invalid(self):
        """Test that invalid logical names raise InvalidSecretReferenceError."""
        config = SecretsConfig(provider="env", env_prefix="TEST_")
        manager = SecretManager.from_config(config)
        
        # Invalid names - these should fail validation in _resolve_reference
        invalid_names = ["123invalid", "_invalid", "invalid-name", "invalid.name", ""]
        for name in invalid_names:
            # The validation happens in _resolve_reference via SECRET_REF_PATTERN.match
            with pytest.raises(InvalidSecretReferenceError) as exc_info:
                manager._resolve_reference(name)
            assert name in str(exc_info.value)

    def test_name_mapping(self):
        """Test name mapping from logical name to provider key."""
        config = SecretsConfig(
            provider="env",
            env_prefix="TEST_",
            name_map={"db_password": "DB_PASS"},
        )
        manager = SecretManager.from_config(config)
        
        os.environ["TEST_DB_PASS"] = "mapped_value"
        
        value = manager._resolve_reference("db_password")
        assert value == "mapped_value"

    def test_name_mapping_fallback(self):
        """Test that missing name_map entry falls back to logical_name."""
        config = SecretsConfig(
            provider="env",
            env_prefix="TEST_",
            name_map={"other": "OTHER"},
        )
        manager = SecretManager.from_config(config)
        
        os.environ["TEST_DB_PASSWORD"] = "fallback_value"
        
        value = manager._resolve_reference("db_password")
        assert value == "fallback_value"

    def test_recursive_reference_detection(self):
        """Test that recursive/chained references are detected."""
        config = SecretsConfig(provider="env", env_prefix="TEST_")
        manager = SecretManager.from_config(config)
        
        # Set up a secret that resolves to a value containing secret://
        os.environ["TEST_RECURSIVE"] = "secret://other_secret"
        
        # The recursive detection happens in _replace_in_string after resolution
        with pytest.raises(SecretResolutionError, match="recursive"):
            manager._replace_in_string("secret://recursive")

    def test_resolve_all_references_dict(self):
        """Test resolving references in a dictionary."""
        config = SecretsConfig(provider="env", env_prefix="TEST_")
        manager = SecretManager.from_config(config)
        
        os.environ["TEST_DB_PASSWORD"] = "db123"
        os.environ["TEST_RABBITMQ_PASSWORD"] = "mq123"
        
        config_dict = {
            "db": {
                "url": "postgresql://user:secret://db_password@host:5432/db"
            },
            "comms": {
                "rabbitmq": {
                    "url": "amqp://user:secret://rabbitmq_password@host:5672/"
                }
            },
            "secrets": {
                "provider": "env"
            }
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
        config = SecretsConfig(provider="env", env_prefix="TEST_")
        manager = SecretManager.from_config(config)
        
        os.environ["TEST_SECRET1"] = "value1"
        os.environ["TEST_SECRET2"] = "value2"
        
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
        config = SecretsConfig(provider="env", env_prefix="TEST_")
        manager = SecretManager.from_config(config)
        
        os.environ["TEST_SECRET"] = "value"
        
        original = {"key": "secret://secret"}
        result = manager.resolve_all_references(original)
        
        assert result is not original
        assert result["key"] == "value"
        assert original["key"] == "secret://secret"

    def test_has_secret_references(self):
        """Test _has_secret_references method."""
        config_dict = {
            "db": {"url": "postgresql://user:secret://db_password@host:5432/db"},
            "comms": {"rabbitmq": {"url": "amqp://user:pass@host:5672/"}},
        }
        
        assert SecretManager._has_secret_references(config_dict) is True
        
        config_dict_no_refs = {
            "db": {"url": "postgresql://user:pass@host:5432/db"},
        }
        
        assert SecretManager._has_secret_references(config_dict_no_refs) is False

    def test_has_secret_references_exclude_keys(self):
        """Test _has_secret_references with exclude_keys."""
        config_dict = {
            "db": {"url": "postgresql://user:secret://db_password@host:5432/db"},
            "secrets": {"provider": "env"},
        }
        
        # Should find references when not excluding secrets
        assert SecretManager._has_secret_references(config_dict, exclude_keys=[]) is True
        
        # Should not find references when excluding secrets (but there are none in secrets section)
        # Actually, there are references in db section, so should still find them
        assert SecretManager._has_secret_references(config_dict, exclude_keys=["secrets"]) is True

    def test_error_propagation(self):
        """Test that provider errors are properly propagated."""
        config = SecretsConfig(provider="env", env_prefix="TEST_")
        manager = SecretManager.from_config(config)
        
        # Missing secret should raise SecretNotFoundError
        with pytest.raises(SecretNotFoundError):
            manager._resolve_reference("nonexistent")

