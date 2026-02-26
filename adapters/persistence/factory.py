"""
Factory for creating database runtime instances.
"""

import logging
from typing import Any

from adapters.persistence.postgres import PostgresRuntime
from squadops.core.secrets import SecretManager
from squadops.ports.db import DbRuntime

logger = logging.getLogger(__name__)


def validate_db_config(profile: dict[str, Any]) -> None:
    """
    Validate database configuration from profile.

    Args:
        profile: Configuration profile dictionary

    Raises:
        ValueError: If required configuration keys are missing or invalid
    """
    db_config = profile.get("db")
    if not db_config:
        raise ValueError("Database configuration ('db') not found in profile")

    # Check that at least one of dsn or url is provided
    dsn = db_config.get("dsn")
    url = db_config.get("url")
    if not dsn and not url:
        raise ValueError("Either 'db.dsn' or 'db.url' must be provided")


def get_db_runtime(profile: dict[str, Any], secret_manager: SecretManager) -> DbRuntime:
    """
    Create a database runtime instance based on profile configuration.

    This factory function:
    1. Validates the database configuration
    2. Resolves secret:// references in DSN/password fields via SecretManager
    3. Creates and returns the appropriate DbRuntime implementation

    Args:
        profile: Configuration profile dictionary containing 'db' section
        secret_manager: SecretManager instance for resolving secret:// references

    Returns:
        DbRuntime instance (currently only PostgresRuntime is supported)

    Raises:
        ValueError: If configuration is invalid
    """
    # Validate configuration
    validate_db_config(profile)

    db_config = profile["db"]

    # Extract DSN (prefer dsn over url for backward compatibility)
    dsn = db_config.get("dsn") or db_config.get("url")
    if not dsn:
        raise ValueError("Either 'db.dsn' or 'db.url' must be provided")

    # Extract SSL configuration
    ssl_config = db_config.get("ssl", {})
    ssl_mode = ssl_config.get("mode", "disable") if isinstance(ssl_config, dict) else "disable"
    ssl_ca_bundle_path = ssl_config.get("ca_bundle_path") if isinstance(ssl_config, dict) else None

    # Extract pool configuration
    pool_config = db_config.get("pool", {})
    if isinstance(pool_config, dict):
        pool_size = pool_config.get("size", 5)
        max_overflow = pool_config.get("max_overflow", 10)
        pool_timeout = pool_config.get("timeout_seconds", 30)
    else:
        # Fallback to legacy fields
        pool_size = db_config.get("pool_size", 5)
        max_overflow = db_config.get("max_overflow", 10)
        pool_timeout = db_config.get("pool_timeout", 30)

    # Extract other configuration
    echo = db_config.get("echo", False)
    connection_mode = db_config.get("connection", "direct")
    migration_mode = (
        db_config.get("migrations", {}).get("mode", "off")
        if isinstance(db_config.get("migrations"), dict)
        else "off"
    )

    # Create PostgresRuntime instance
    # Note: Secret resolution happens inside PostgresRuntime.__init__ if DSN contains secret://
    runtime = PostgresRuntime(
        dsn=dsn,
        secret_manager=secret_manager,
        ssl_mode=ssl_mode,
        ssl_ca_bundle_path=ssl_ca_bundle_path,
        pool_size=pool_size,
        max_overflow=max_overflow,
        pool_timeout=pool_timeout,
        pool_pre_ping=True,  # Default as per SIP-0.8.3 Rule 3
        echo=echo,
        connection_mode=connection_mode,
        migration_mode=migration_mode,
    )

    logger.info(
        f"Created PostgresRuntime instance (connection_mode={connection_mode}, migration_mode={migration_mode})"
    )

    return runtime
