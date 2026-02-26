"""
Integration smoke test for Persistence (0.8.3) and Secrets (0.8.2) handshake.

This test serves as the "Definition of Done" for the 0.8.3 migration,
proving that Core, Ports, and Adapters are working together under the new DDD rules
without legacy infrastructure leakage.
"""

import os
import sys

import pytest

from adapters.persistence.factory import get_db_runtime
from adapters.secrets.factory import create_provider
from squadops.core.secrets import SecretManager
from squadops.ports.db import DbRuntime, HealthResult


class TestPersistenceHandshake:
    """End-to-end smoke test for Secrets + Persistence integration."""

    @pytest.fixture
    def mock_db_password(self, monkeypatch):
        """Set up mock DB password in environment."""
        monkeypatch.setenv("SQUADOPS_DB_PASS", "smoke_test_pass")
        yield "smoke_test_pass"
        # Cleanup
        monkeypatch.delenv("SQUADOPS_DB_PASS", raising=False)

    @pytest.fixture
    def secret_manager(self, mock_db_password):
        """Create SecretManager using EnvProvider via factory."""
        provider = create_provider(
            provider="env",
            env_prefix="SQUADOPS_",
        )
        manager = SecretManager(provider=provider)
        return manager

    @pytest.fixture
    def mock_profile_with_secret_dsn(self):
        """Create mock deployment profile with secret:// reference in DSN."""
        return {
            "db": {
                "dsn": "postgresql://user:secret://db_pass@localhost:5432/testdb",
                "pool": {"size": 5, "max_overflow": 10, "timeout_seconds": 30},
                "ssl": {"mode": "disable"},
                "migrations": {"mode": "off"},
                "connection": "direct",
            }
        }

    def test_secrets_initialization(self, secret_manager, mock_db_password):
        """Test 1: Secrets initialization via factory."""
        # Verify SecretManager was created
        assert secret_manager is not None
        assert secret_manager.provider.provider_name == "env"

        # Verify it can resolve the secret
        resolved = secret_manager._resolve_reference("db_pass")
        assert resolved == mock_db_password

    def test_persistence_initialization_with_secret(
        self, secret_manager, mock_profile_with_secret_dsn
    ):
        """Test 2: Persistence initialization with secret:// reference."""
        # Track modules loaded before
        modules_before = set(sys.modules.keys())

        # Create DbRuntime via factory
        runtime = get_db_runtime(mock_profile_with_secret_dsn, secret_manager)

        # Track modules loaded after
        modules_after = set(sys.modules.keys())
        new_modules = modules_after - modules_before

        # Verify runtime was created
        assert runtime is not None
        assert isinstance(runtime, DbRuntime)
        assert runtime.engine is not None
        assert runtime.session_factory is not None

    def test_secret_resolution_handshake(
        self, secret_manager, mock_profile_with_secret_dsn, mock_db_password
    ):
        """Test 3: Verify SecretManager was called during runtime creation."""
        # Create a spy on the secret manager's resolve method
        original_resolve = secret_manager._resolve_reference
        call_count = {"count": 0}

        def counting_resolve(logical_name: str) -> str:
            call_count["count"] += 1
            return original_resolve(logical_name)

        secret_manager._resolve_reference = counting_resolve

        # Create runtime
        runtime = get_db_runtime(mock_profile_with_secret_dsn, secret_manager)

        # Verify SecretManager was called
        assert call_count["count"] > 0, (
            "SecretManager should have been called to resolve secret:// references"
        )

    def test_engine_contains_resolved_password(
        self, secret_manager, mock_profile_with_secret_dsn, mock_db_password
    ):
        """Test 4: Verify engine contains resolved password (redacted in logs)."""
        runtime = get_db_runtime(mock_profile_with_secret_dsn, secret_manager)

        # Get the engine's URL (this is safe to check in tests)
        engine_url = str(runtime.engine.url)

        # Verify the secret:// reference is NOT in the URL (i.e., it was resolved)
        assert "secret://" not in engine_url, "Engine URL should not contain secret:// references"

        # Access actual password via SQLAlchemy's URL object (str() masks it for security)
        # SQLAlchemy 2.0 hides password in __str__ with *** but stores it in url.password
        actual_password = runtime.engine.url.password
        assert actual_password == mock_db_password, "Engine URL should contain resolved password"

    def test_no_legacy_infrastructure_loaded(self, secret_manager, mock_profile_with_secret_dsn):
        """Test 5: Invariance check - no legacy infra.db or infra.secrets modules loaded."""
        # Create runtime (this triggers all necessary imports)
        runtime = get_db_runtime(mock_profile_with_secret_dsn, secret_manager)

        # Check ALL loaded modules for legacy infrastructure
        all_modules = set(sys.modules.keys())

        # Check for legacy module imports (these should NOT exist after v0 removal)
        legacy_modules = [
            mod
            for mod in all_modules
            if mod.startswith("infra.db") or mod.startswith("infra.secrets")
        ]

        assert len(legacy_modules) == 0, (
            f"Legacy infrastructure modules should not be loaded. Found: {legacy_modules}"
        )

        # Verify we're using new architecture (check all modules, not just new ones)
        new_arch_modules = [
            mod for mod in all_modules if mod.startswith("squadops.") or mod.startswith("adapters.")
        ]
        assert len(new_arch_modules) > 0, "New architecture modules should be loaded"

    @pytest.mark.skipif(
        os.getenv("SKIP_DB_CONNECTIVITY_TEST") == "1",
        reason="Skipping connectivity test (set SKIP_DB_CONNECTIVITY_TEST=1 to skip)",
    )
    def test_connectivity_check_optional(self, secret_manager, mock_profile_with_secret_dsn):
        """Test 6: Optional connectivity check if local Postgres is available."""
        runtime = get_db_runtime(mock_profile_with_secret_dsn, secret_manager)

        # Perform health check
        result = runtime.db_health_check()

        # Verify HealthResult structure
        assert isinstance(result, HealthResult)
        assert result.status in ["healthy", "unhealthy"]

        # If healthy, verify latency is recorded
        if result.status == "healthy":
            assert result.latency_ms is not None
            assert result.latency_ms >= 0
