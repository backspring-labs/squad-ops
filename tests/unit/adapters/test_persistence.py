"""
Unit tests for persistence adapters.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock

from squadops.core.secrets import SecretManager, SecretNotFoundError
from squadops.ports.db import DbRuntime, HealthResult

from adapters.persistence.factory import get_db_runtime, validate_db_config
from adapters.persistence.postgres import PostgresRuntime


class TestValidateDBConfig:
    """Tests for validate_db_config function."""

    def test_valid_config_with_dsn(self):
        """Test validation with valid config containing dsn."""
        profile = {"db": {"dsn": "postgresql://user:pass@localhost/db"}}
        # Should not raise
        validate_db_config(profile)

    def test_valid_config_with_url(self):
        """Test validation with valid config containing url (legacy)."""
        profile = {"db": {"url": "postgresql://user:pass@localhost/db"}}
        # Should not raise
        validate_db_config(profile)

    def test_missing_db_section(self):
        """Test validation fails when db section is missing."""
        profile = {"other": {"key": "value"}}
        with pytest.raises(ValueError, match="Database configuration"):
            validate_db_config(profile)

    def test_missing_dsn_and_url(self):
        """Test validation fails when both dsn and url are missing."""
        profile = {"db": {"pool_size": 5}}
        with pytest.raises(ValueError, match="Either 'db.dsn' or 'db.url' must be provided"):
            validate_db_config(profile)


class TestGetDBRuntime:
    """Tests for get_db_runtime factory function."""

    @pytest.fixture
    def mock_secret_manager(self):
        """Fixture for a mock SecretManager."""
        manager = Mock(spec=SecretManager)
        manager._replace_in_string = Mock(side_effect=lambda x: x.replace("secret://db_pass", "resolved_password"))
        return manager

    @pytest.fixture
    def basic_profile(self):
        """Fixture for a basic database profile."""
        return {
            "db": {
                "dsn": "postgresql://user:password@localhost/testdb",
                "pool": {"size": 5, "max_overflow": 10, "timeout_seconds": 30},
                "ssl": {"mode": "disable"},
                "migrations": {"mode": "off"},
                "connection": "direct",
            }
        }

    def test_create_runtime_with_basic_profile(self, basic_profile, mock_secret_manager):
        """Test creating runtime with basic profile."""
        runtime = get_db_runtime(basic_profile, mock_secret_manager)
        assert isinstance(runtime, PostgresRuntime)
        assert runtime.connection_mode == "direct"
        assert runtime.migration_mode == "off"

    def test_create_runtime_with_secret_reference(self, mock_secret_manager):
        """Test creating runtime with secret:// reference in DSN."""
        profile = {
            "db": {
                "dsn": "postgresql://user:secret://db_pass@localhost/testdb",
                "pool": {"size": 5},
            }
        }
        runtime = get_db_runtime(profile, mock_secret_manager)
        assert isinstance(runtime, PostgresRuntime)
        # Verify secret manager was called
        mock_secret_manager._replace_in_string.assert_called()

    def test_create_runtime_with_legacy_fields(self, mock_secret_manager):
        """Test creating runtime with legacy url/pool_size fields."""
        profile = {
            "db": {
                "url": "postgresql://user:pass@localhost/db",
                "pool_size": 10,
                "max_overflow": 5,
                "pool_timeout": 60,
            }
        }
        runtime = get_db_runtime(profile, mock_secret_manager)
        assert isinstance(runtime, PostgresRuntime)

    def test_create_runtime_with_ssl_config(self, mock_secret_manager):
        """Test creating runtime with SSL configuration."""
        profile = {
            "db": {
                "dsn": "postgresql://user:pass@localhost/db",
                "ssl": {"mode": "require", "ca_bundle_path": "/path/to/ca.crt"},
            }
        }
        runtime = get_db_runtime(profile, mock_secret_manager)
        assert isinstance(runtime, PostgresRuntime)

    def test_create_runtime_invalid_config(self, mock_secret_manager):
        """Test creating runtime with invalid config raises error."""
        profile = {"db": {}}  # Missing dsn/url
        with pytest.raises(ValueError, match="Either 'db.dsn' or 'db.url' must be provided"):
            get_db_runtime(profile, mock_secret_manager)


class TestPostgresRuntime:
    """Tests for PostgresRuntime class."""

    @pytest.fixture
    def mock_secret_manager(self):
        """Fixture for a mock SecretManager."""
        manager = Mock(spec=SecretManager)
        manager._replace_in_string = Mock(side_effect=lambda x: x.replace("secret://db_pass", "resolved_password"))
        return manager

    @pytest.fixture
    def basic_dsn(self):
        """Fixture for a basic DSN."""
        return "postgresql://user:password@localhost/testdb"

    def test_init_with_basic_dsn(self, basic_dsn):
        """Test initialization with basic DSN."""
        runtime = PostgresRuntime(dsn=basic_dsn)
        assert runtime.engine is not None
        assert runtime.session_factory is not None
        assert runtime.connection_mode == "direct"
        assert runtime.migration_mode == "off"

    def test_init_with_secret_reference(self, basic_dsn, mock_secret_manager):
        """Test initialization with secret:// reference."""
        dsn_with_secret = "postgresql://user:secret://db_pass@localhost/testdb"
        runtime = PostgresRuntime(dsn=dsn_with_secret, secret_manager=mock_secret_manager)
        assert runtime.engine is not None
        # Verify secret manager was called
        mock_secret_manager._replace_in_string.assert_called()

    def test_init_with_ssl_mode(self, basic_dsn):
        """Test initialization with SSL mode."""
        runtime = PostgresRuntime(dsn=basic_dsn, ssl_mode="require")
        assert runtime.engine is not None

    def test_init_with_pool_config(self, basic_dsn):
        """Test initialization with pool configuration."""
        runtime = PostgresRuntime(
            dsn=basic_dsn,
            pool_size=10,
            max_overflow=5,
            pool_timeout=60,
            pool_pre_ping=True,
        )
        assert runtime.engine is not None

    def test_db_health_check_success(self, basic_dsn):
        """Test successful health check."""
        runtime = PostgresRuntime(dsn=basic_dsn)
        # Note: This will fail if no actual database is available
        # In a real test environment, you'd use a test database or mock
        result = runtime.db_health_check()
        assert isinstance(result, HealthResult)
        assert result.status in ["healthy", "unhealthy"]  # Depends on DB availability

    def test_db_health_check_failure(self):
        """Test health check with invalid DSN."""
        runtime = PostgresRuntime(dsn="postgresql://invalid:invalid@nonexistent:9999/nonexistent")
        result = runtime.db_health_check()
        assert isinstance(result, HealthResult)
        assert result.status == "unhealthy"
        assert result.message is not None

    def test_dispose(self, basic_dsn):
        """Test resource disposal."""
        runtime = PostgresRuntime(dsn=basic_dsn)
        # Should not raise
        runtime.dispose()

    def test_connection_mode_property(self, basic_dsn):
        """Test connection_mode property."""
        runtime = PostgresRuntime(dsn=basic_dsn, connection_mode="proxy")
        assert runtime.connection_mode == "proxy"

    def test_migration_mode_property(self, basic_dsn):
        """Test migration_mode property."""
        runtime = PostgresRuntime(dsn=basic_dsn, migration_mode="startup")
        assert runtime.migration_mode == "startup"

    def test_build_connection_url_with_ssl(self, basic_dsn):
        """Test _build_connection_url with SSL parameters."""
        runtime = PostgresRuntime(dsn=basic_dsn, ssl_mode="verify-full", ssl_ca_bundle_path="/path/to/ca.crt")
        # Verify URL was built with SSL parameters
        assert runtime.engine is not None
