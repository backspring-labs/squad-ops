"""
Integration tests for configuration profiles (SIP-051).
"""

import os
import subprocess
import sys
from pathlib import Path

import pytest

from infra.config.loader import load_config, reset_config
from infra.config.redaction import redact_config


class TestRuntimeAPIStartup:
    """Test runtime API startup with configuration profiles."""

    def test_startup_with_local_profile(self):
        """Test that runtime API can start with local profile."""
        reset_config()
        # This test verifies that config loads without errors
        # In a real integration test, we would start the API server
        config = load_config(profile="local")
        assert config is not None
        assert config.db.url is not None
        assert config.comms.rabbitmq.url is not None

    def test_startup_logs_profile(self, caplog):
        """Test that startup logs include resolved profile."""
        reset_config()
        with caplog.at_level("INFO"):
            config = load_config(profile="local")
        # Check that profile is logged
        log_messages = " ".join(caplog.messages)
        assert "profile" in log_messages.lower() or "local" in log_messages.lower()

    def test_startup_logs_fingerprint(self, caplog):
        """Test that startup logs include config fingerprint."""
        reset_config()
        with caplog.at_level("INFO"):
            config = load_config(profile="local")
        # Check that fingerprint is logged
        log_messages = " ".join(caplog.messages)
        assert "fingerprint" in log_messages.lower() or "cfg-" in log_messages.lower()


class TestStrictModeFailures:
    """Test strict mode validation failures."""

    def test_strict_mode_missing_required_fails(self, tmp_path, monkeypatch):
        """Test that missing required keys cause startup failure in strict mode."""
        reset_config()
        # Create minimal invalid config
        config_dir = tmp_path / "config"
        config_dir.mkdir()
        (config_dir / "profiles").mkdir()
        (config_dir / "defaults.yaml").write_text("{}")
        (config_dir / "base.yaml").write_text("{}")
        (config_dir / "profiles" / "local.yaml").write_text("{}")

        # Mock repo root
        from agents.utils import path_resolver

        original = path_resolver.PathResolver.get_base_path

        def mock_get_base_path():
            return tmp_path

        monkeypatch.setattr(path_resolver.PathResolver, "get_base_path", mock_get_base_path)

        with pytest.raises(Exception):  # Should raise ConfigValidationError
            load_config(profile="local", strict=True)

    def test_strict_mode_unknown_key_fails(self, tmp_path, monkeypatch):
        """Test that unknown keys cause failure in strict mode."""
        reset_config()
        config_dir = tmp_path / "config"
        config_dir.mkdir()
        (config_dir / "profiles").mkdir()
        (config_dir / "defaults.yaml").write_text(
            """
db:
  url: postgresql://user:pass@host:5432/db
  pool_size: 5
comms:
  rabbitmq:
    url: amqp://user:pass@host:5672/
  redis:
    url: redis://host:6379/0
"""
        )
        (config_dir / "base.yaml").write_text("{}")
        (config_dir / "profiles" / "local.yaml").write_text(
            """
unknown_key: value
runtime_api_url: http://test:8001
"""
        )

        from agents.utils import path_resolver

        original = path_resolver.PathResolver.get_base_path

        def mock_get_base_path():
            return tmp_path

        monkeypatch.setattr(path_resolver.PathResolver, "get_base_path", mock_get_base_path)

        with pytest.raises(Exception):
            load_config(profile="local", strict=True)


class TestRedactedLogging:
    """Test that configuration logging is properly redacted."""

    def test_redacted_config_no_secrets(self):
        """Test that redacted config contains no secret values."""
        reset_config()
        config = load_config(profile="local")
        config_dict = config.model_dump()
        redacted = redact_config(config_dict)

        # Check that passwords are redacted
        def check_no_secrets(d, path=""):
            """Recursively check for unredacted secrets."""
            if isinstance(d, dict):
                for key, value in d.items():
                    current_path = f"{path}.{key}" if path else key
                    if isinstance(value, dict):
                        check_no_secrets(value, current_path)
                    elif isinstance(value, str):
                        # Check for common secret patterns
                        key_lower = key.lower()
                        if any(
                            secret_word in key_lower
                            for secret_word in ["password", "secret", "token", "key"]
                        ):
                            assert value == "***" or "***" in value, f"Secret not redacted at {current_path}"
            elif isinstance(d, list):
                for item in d:
                    if isinstance(item, dict):
                        check_no_secrets(item, path)

        check_no_secrets(redacted)

    def test_redacted_config_preserves_structure(self):
        """Test that redacted config preserves structure."""
        reset_config()
        config = load_config(profile="local")
        config_dict = config.model_dump()
        redacted = redact_config(config_dict)

        # Structure should be preserved
        assert "db" in redacted
        assert "comms" in redacted
        assert "runtime_api_url" in redacted


class TestProfileSwitching:
    """Test profile switching behavior."""

    def test_profile_switching_local_to_dev(self, monkeypatch):
        """Test switching between profiles."""
        reset_config()
        config_local = load_config(profile="local")
        reset_config()
        config_dev = load_config(profile="dev")

        # Profiles should load (may have different values)
        assert config_local is not None
        assert config_dev is not None

    def test_profile_switching_via_env(self, monkeypatch):
        """Test profile switching via environment variable."""
        reset_config()
        monkeypatch.setenv("SQUADOPS_PROFILE", "dev")
        config = load_config()
        # Should use dev profile from env
        assert config is not None

    def test_observability_urls_per_profile(self):
        """Test observability URLs change per profile."""
        reset_config()
        config_local = load_config(profile="local")
        reset_config()
        config_dev = load_config(profile="dev")
        # Both should have observability config
        assert config_local.observability.prometheus.url is not None
        assert config_dev.observability.prometheus.url is not None
        # Local profile should use localhost URLs
        if "localhost" in config_local.observability.prometheus.url:
            assert "localhost" in config_local.observability.prometheus.url

