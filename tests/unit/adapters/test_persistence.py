"""
Unit tests for persistence adapters.
"""

from unittest.mock import Mock, patch

import pytest

from adapters.persistence.factory import validate_db_config
from squadops.core.secrets import SecretManager
from squadops.ports.db import HealthResult


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
        manager._replace_in_string = Mock(
            side_effect=lambda x: x.replace("secret://db_pass", "resolved_password")
        )
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

    @patch("adapters.persistence.factory.PostgresRuntime")
    def test_create_runtime_with_basic_profile(
        self, mock_runtime_class, basic_profile, mock_secret_manager
    ):
        """Test creating runtime with basic profile."""
        from adapters.persistence.factory import get_db_runtime

        mock_runtime = Mock()
        mock_runtime.connection_mode = "direct"
        mock_runtime.migration_mode = "off"
        mock_runtime_class.return_value = mock_runtime

        runtime = get_db_runtime(basic_profile, mock_secret_manager)

        assert runtime.connection_mode == "direct"
        assert runtime.migration_mode == "off"
        mock_runtime_class.assert_called_once()

    @patch("adapters.persistence.factory.PostgresRuntime")
    def test_create_runtime_with_secret_reference(self, mock_runtime_class, mock_secret_manager):
        """Test creating runtime with secret:// reference in DSN."""
        from adapters.persistence.factory import get_db_runtime

        profile = {
            "db": {
                "dsn": "postgresql://user:secret://db_pass@localhost/testdb",
                "pool": {"size": 5},
            }
        }

        mock_runtime = Mock()
        mock_runtime_class.return_value = mock_runtime

        get_db_runtime(profile, mock_secret_manager)

        mock_runtime_class.assert_called_once()
        # Verify the DSN was passed (secret resolution happens in PostgresRuntime)
        call_kwargs = mock_runtime_class.call_args[1]
        assert "secret://db_pass" in call_kwargs["dsn"]

    @patch("adapters.persistence.factory.PostgresRuntime")
    def test_create_runtime_with_legacy_url(self, mock_runtime_class, mock_secret_manager):
        """Test creating runtime with legacy url field (instead of dsn)."""
        from adapters.persistence.factory import get_db_runtime

        profile = {
            "db": {
                "url": "postgresql://user:pass@localhost/db",
            }
        }

        mock_runtime = Mock()
        mock_runtime_class.return_value = mock_runtime

        get_db_runtime(profile, mock_secret_manager)

        mock_runtime_class.assert_called_once()
        call_kwargs = mock_runtime_class.call_args[1]
        # url should be passed as dsn
        assert call_kwargs["dsn"] == "postgresql://user:pass@localhost/db"

    @patch("adapters.persistence.factory.PostgresRuntime")
    def test_create_runtime_with_ssl_config(self, mock_runtime_class, mock_secret_manager):
        """Test creating runtime with SSL configuration."""
        from adapters.persistence.factory import get_db_runtime

        profile = {
            "db": {
                "dsn": "postgresql://user:pass@localhost/db",
                "ssl": {"mode": "require", "ca_bundle_path": "/path/to/ca.crt"},
            }
        }

        mock_runtime = Mock()
        mock_runtime_class.return_value = mock_runtime

        get_db_runtime(profile, mock_secret_manager)

        call_kwargs = mock_runtime_class.call_args[1]
        assert call_kwargs["ssl_mode"] == "require"
        assert call_kwargs["ssl_ca_bundle_path"] == "/path/to/ca.crt"

    def test_create_runtime_missing_db_section(self, mock_secret_manager):
        """Test creating runtime without db section raises error."""
        from adapters.persistence.factory import get_db_runtime

        profile = {"other": {}}  # Missing db section
        with pytest.raises(ValueError, match="Database configuration"):
            get_db_runtime(profile, mock_secret_manager)

    def test_create_runtime_missing_dsn(self, mock_secret_manager):
        """Test creating runtime without dsn/url raises error."""
        from adapters.persistence.factory import get_db_runtime

        profile = {"db": {"pool_size": 5}}  # Has db section but no dsn/url
        with pytest.raises(ValueError, match="Either 'db.dsn' or 'db.url' must be provided"):
            get_db_runtime(profile, mock_secret_manager)


class TestPostgresRuntime:
    """Tests for PostgresRuntime class."""

    @pytest.fixture
    def mock_secret_manager(self):
        """Fixture for a mock SecretManager."""
        manager = Mock(spec=SecretManager)
        manager._replace_in_string = Mock(
            side_effect=lambda x: x.replace("secret://db_pass", "resolved_password")
        )
        return manager

    @pytest.fixture
    def basic_dsn(self):
        """Fixture for a basic DSN."""
        return "postgresql://user:password@localhost/testdb"

    @patch("adapters.persistence.postgres.runtime.create_engine")
    @patch("adapters.persistence.postgres.runtime.sessionmaker")
    def test_init_with_basic_dsn(self, mock_sessionmaker, mock_create_engine, basic_dsn):
        """Test initialization with basic DSN."""
        from adapters.persistence.postgres import PostgresRuntime

        mock_engine = Mock()
        mock_create_engine.return_value = mock_engine

        runtime = PostgresRuntime(dsn=basic_dsn)

        assert runtime.engine is mock_engine
        assert runtime.connection_mode == "direct"
        assert runtime.migration_mode == "off"
        mock_create_engine.assert_called_once()

    @patch("adapters.persistence.postgres.runtime.create_engine")
    @patch("adapters.persistence.postgres.runtime.sessionmaker")
    def test_init_with_secret_reference(
        self, mock_sessionmaker, mock_create_engine, basic_dsn, mock_secret_manager
    ):
        """Test initialization with secret:// reference."""
        from adapters.persistence.postgres import PostgresRuntime

        dsn_with_secret = "postgresql://user:secret://db_pass@localhost/testdb"

        mock_engine = Mock()
        mock_create_engine.return_value = mock_engine

        PostgresRuntime(dsn=dsn_with_secret, secret_manager=mock_secret_manager)

        # Verify secret manager was called
        mock_secret_manager._replace_in_string.assert_called_once_with(dsn_with_secret)
        # Verify engine was created with resolved DSN
        call_args = mock_create_engine.call_args
        assert "resolved_password" in call_args[0][0]

    @patch("adapters.persistence.postgres.runtime.create_engine")
    @patch("adapters.persistence.postgres.runtime.sessionmaker")
    def test_init_with_ssl_mode(self, mock_sessionmaker, mock_create_engine, basic_dsn):
        """Test initialization with SSL mode."""
        from adapters.persistence.postgres import PostgresRuntime

        mock_engine = Mock()
        mock_create_engine.return_value = mock_engine

        PostgresRuntime(dsn=basic_dsn, ssl_mode="require")

        # Verify SSL mode was added to connection URL
        call_args = mock_create_engine.call_args
        assert "sslmode=require" in call_args[0][0]

    @patch("adapters.persistence.postgres.runtime.create_engine")
    @patch("adapters.persistence.postgres.runtime.sessionmaker")
    def test_init_with_pool_config(self, mock_sessionmaker, mock_create_engine, basic_dsn):
        """Test initialization with pool configuration."""
        from adapters.persistence.postgres import PostgresRuntime

        mock_engine = Mock()
        mock_create_engine.return_value = mock_engine

        PostgresRuntime(
            dsn=basic_dsn,
            pool_size=10,
            max_overflow=5,
            pool_timeout=60,
            pool_pre_ping=True,
        )

        call_kwargs = mock_create_engine.call_args[1]
        assert call_kwargs["pool_size"] == 10
        assert call_kwargs["max_overflow"] == 5
        assert call_kwargs["pool_timeout"] == 60
        assert call_kwargs["pool_pre_ping"] is True

    @patch("adapters.persistence.postgres.runtime.create_engine")
    @patch("adapters.persistence.postgres.runtime.sessionmaker")
    def test_db_health_check_success(self, mock_sessionmaker, mock_create_engine, basic_dsn):
        """Test successful health check."""
        from adapters.persistence.postgres import PostgresRuntime

        mock_engine = Mock()
        mock_conn = Mock()
        mock_result = Mock()
        mock_engine.connect.return_value.__enter__ = Mock(return_value=mock_conn)
        mock_engine.connect.return_value.__exit__ = Mock(return_value=False)
        mock_conn.execute.return_value = mock_result
        mock_create_engine.return_value = mock_engine

        runtime = PostgresRuntime(dsn=basic_dsn)
        result = runtime.db_health_check()

        assert isinstance(result, HealthResult)
        assert result.status == "healthy"

    @patch("adapters.persistence.postgres.runtime.create_engine")
    @patch("adapters.persistence.postgres.runtime.sessionmaker")
    def test_db_health_check_failure(self, mock_sessionmaker, mock_create_engine, basic_dsn):
        """Test health check failure."""
        from adapters.persistence.postgres import PostgresRuntime

        mock_engine = Mock()
        mock_engine.connect.side_effect = Exception("Connection failed")
        mock_create_engine.return_value = mock_engine

        runtime = PostgresRuntime(dsn=basic_dsn)
        result = runtime.db_health_check()

        assert isinstance(result, HealthResult)
        assert result.status == "unhealthy"
        assert "Connection failed" in result.message

    @patch("adapters.persistence.postgres.runtime.create_engine")
    @patch("adapters.persistence.postgres.runtime.sessionmaker")
    def test_dispose(self, mock_sessionmaker, mock_create_engine, basic_dsn):
        """Test resource disposal."""
        from adapters.persistence.postgres import PostgresRuntime

        mock_engine = Mock()
        mock_create_engine.return_value = mock_engine

        runtime = PostgresRuntime(dsn=basic_dsn)
        runtime.dispose()

        mock_engine.dispose.assert_called_once()

    @patch("adapters.persistence.postgres.runtime.create_engine")
    @patch("adapters.persistence.postgres.runtime.sessionmaker")
    def test_build_connection_url_with_ssl(self, mock_sessionmaker, mock_create_engine, basic_dsn):
        """Test initialization with SSL parameters."""
        from adapters.persistence.postgres import PostgresRuntime

        mock_engine = Mock()
        mock_create_engine.return_value = mock_engine

        PostgresRuntime(dsn=basic_dsn, ssl_mode="verify-full", ssl_ca_bundle_path="/path/to/ca.crt")

        call_args = mock_create_engine.call_args
        dsn_used = call_args[0][0]
        assert "sslmode=verify-full" in dsn_used
        assert "sslrootcert" in dsn_used
