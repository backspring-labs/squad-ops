"""
PostgreSQL runtime implementation for DbRuntime port.
"""

import logging
import time
from typing import Any
from urllib.parse import urlparse, urlunparse, parse_qs, urlencode

from sqlalchemy import Engine, create_engine, text
from sqlalchemy.orm import sessionmaker

from squadops.core.secrets import SecretManager
from squadops.ports.db import DbRuntime, HealthResult

logger = logging.getLogger(__name__)


class PostgresRuntime(DbRuntime):
    """
    PostgreSQL implementation of DbRuntime port.

    Handles:
    - Profile-driven DSN selection (direct vs. proxy)
    - SSL/TLS mode configuration
    - Connection pooling with pool_pre_ping=True default
    - Secret resolution via SecretManager
    - Migration mode gating (exposed as property, no automatic execution)
    """

    def __init__(
        self,
        dsn: str,
        secret_manager: SecretManager | None = None,
        ssl_mode: str = "disable",
        ssl_ca_bundle_path: str | None = None,
        pool_size: int = 5,
        max_overflow: int = 10,
        pool_timeout: int = 30,
        pool_pre_ping: bool = True,
        echo: bool = False,
        connection_mode: str = "direct",
        migration_mode: str = "off",
    ):
        """
        Initialize PostgreSQL runtime.

        Args:
            dsn: Database connection string (may contain secret:// references)
            secret_manager: SecretManager instance for resolving secret:// references
            ssl_mode: SSL mode (disable, require, verify-full)
            ssl_ca_bundle_path: Path to CA bundle file (optional)
            pool_size: Connection pool size
            max_overflow: Max pool overflow connections
            pool_timeout: Pool timeout in seconds
            pool_pre_ping: Enable connection health checks (default: True)
            echo: Enable SQL query logging
            connection_mode: Connection mode (direct, proxy)
            migration_mode: Migration mode (off, startup, job)
        """
        self._secret_manager = secret_manager
        self._connection_mode = connection_mode
        self._migration_mode = migration_mode
        self._echo = echo

        # Resolve secret:// references in DSN if secret_manager is provided
        resolved_dsn = dsn
        if secret_manager and "secret://" in dsn:
            # Resolve all secret:// references in the DSN
            resolved_dsn = secret_manager._replace_in_string(dsn)
            logger.debug("Resolved secret:// references in DSN (redacted in logs)")

        # Build SQLAlchemy connection URL with SSL parameters
        final_dsn = self._build_connection_url(
            resolved_dsn, ssl_mode, ssl_ca_bundle_path
        )

        # Log configuration (never log secrets or unredacted DSNs)
        logger.info(
            f"Initializing PostgresRuntime: connection_mode={connection_mode}, "
            f"ssl_mode={ssl_mode}, pool_size={pool_size}, migration_mode={migration_mode}"
        )

        # Create SQLAlchemy engine
        self._engine = create_engine(
            final_dsn,
            pool_size=pool_size,
            max_overflow=max_overflow,
            pool_timeout=pool_timeout,
            pool_pre_ping=pool_pre_ping,
            echo=echo,
        )

        # Create session factory
        self._session_factory = sessionmaker(bind=self._engine)

    def _build_connection_url(
        self, dsn: str, ssl_mode: str, ssl_ca_bundle_path: str | None
    ) -> str:
        """
        Build SQLAlchemy connection URL with SSL parameters.

        Args:
            dsn: Base connection string
            ssl_mode: SSL mode (disable, require, verify-full)
            ssl_ca_bundle_path: Path to CA bundle file (optional)

        Returns:
            Final connection URL with SSL parameters
        """
        # Parse the DSN
        parsed = urlparse(dsn)

        # Parse existing query parameters
        query_params = parse_qs(parsed.query)

        # Set SSL mode based on configuration
        if ssl_mode == "disable":
            query_params["sslmode"] = ["disable"]
        elif ssl_mode == "require":
            query_params["sslmode"] = ["require"]
        elif ssl_mode == "verify-full":
            query_params["sslmode"] = ["verify-full"]
            if ssl_ca_bundle_path:
                query_params["sslrootcert"] = [ssl_ca_bundle_path]

        # Rebuild URL with updated query parameters
        new_query = urlencode(query_params, doseq=True)
        final_url = urlunparse(
            (parsed.scheme, parsed.netloc, parsed.path, parsed.params, new_query, parsed.fragment)
        )

        return final_url

    @property
    def engine(self) -> Engine:
        """Return the SQLAlchemy engine instance."""
        return self._engine

    @property
    def session_factory(self) -> sessionmaker:
        """Return the SQLAlchemy sessionmaker instance."""
        return self._session_factory

    @property
    def connection_mode(self) -> str:
        """Return the connection mode (direct, proxy)."""
        return self._connection_mode

    @property
    def migration_mode(self) -> str:
        """Return the migration mode (off, startup, job)."""
        return self._migration_mode

    def db_health_check(self) -> HealthResult:
        """
        Perform a database connectivity health check.

        Returns:
            HealthResult indicating the health status of the database connection
        """
        try:
            start_time = time.time()
            with self._engine.connect() as conn:
                # Execute a simple query to verify connectivity
                result = conn.execute(text("SELECT 1"))
                result.fetchone()
            latency_ms = (time.time() - start_time) * 1000

            return HealthResult(
                status="healthy",
                message="Database connection successful",
                latency_ms=latency_ms,
            )
        except Exception as e:
            logger.error(f"Database health check failed: {e}")
            return HealthResult(
                status="unhealthy",
                message=f"Database connection failed: {str(e)}",
            )

    def dispose(self) -> None:
        """Dispose of database resources and close connections."""
        logger.info("Disposing PostgresRuntime resources")
        if self._engine:
            self._engine.dispose()
