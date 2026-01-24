"""
Persistence adapters package.
"""

from adapters.persistence.factory import get_db_runtime
from adapters.persistence.postgres import PostgresRuntime

__all__ = ["get_db_runtime", "PostgresRuntime"]
