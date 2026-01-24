"""
Port interface for database runtime.
Defines the contract that any database runtime implementation must satisfy.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Literal

from sqlalchemy import Engine
from sqlalchemy.orm import sessionmaker


@dataclass
class HealthResult:
    """Result of a database health check."""

    status: Literal["healthy", "unhealthy"]
    message: str | None = None
    latency_ms: float | None = None


class DbRuntime(ABC):
    """Abstract base class for database runtime implementations."""

    @property
    @abstractmethod
    def engine(self) -> Engine:
        """
        Return the SQLAlchemy engine instance.

        Returns:
            SQLAlchemy Engine instance
        """
        pass

    @property
    @abstractmethod
    def session_factory(self) -> sessionmaker:
        """
        Return the SQLAlchemy sessionmaker instance.

        Returns:
            SQLAlchemy sessionmaker instance for creating database sessions
        """
        pass

    @abstractmethod
    def db_health_check(self) -> HealthResult:
        """
        Perform a database connectivity health check.

        Returns:
            HealthResult indicating the health status of the database connection
        """
        pass

    def health_check(self) -> HealthResult:
        """
        Alias for `db_health_check()` (ergonomics).

        The 1.0 execution layer uses `health_check()` as the standardized name.
        Implementations may override this, but by default it delegates to `db_health_check()`.
        """
        return self.db_health_check()

    @abstractmethod
    def dispose(self) -> None:
        """
        Dispose of database resources and close connections.

        This method should clean up the engine, connection pool, and any other
        resources associated with the database runtime.
        """
        pass
