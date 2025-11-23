"""
Tasks Adapter Registry - Factory for creating and managing task adapters
"""

import os
import logging
import asyncpg
from typing import Optional
from agents.tasks.base_adapter import TaskAdapterBase
from agents.tasks.sql_adapter import SqlTasksAdapter
from config.unified_config import get_config

logger = logging.getLogger(__name__)

# Global adapter instance (singleton)
_adapter: Optional[TaskAdapterBase] = None
_test_adapter: Optional[TaskAdapterBase] = None


def set_adapter_for_testing(adapter: TaskAdapterBase) -> None:
    """
    Set adapter instance for testing (injection support).
    
    Args:
        adapter: Adapter instance to use for tests
    """
    global _test_adapter
    _test_adapter = adapter


def clear_test_adapter() -> None:
    """Clear test adapter (for test cleanup)"""
    global _test_adapter
    _test_adapter = None


async def get_tasks_adapter() -> TaskAdapterBase:
    """
    Get the configured tasks adapter instance (singleton).
    
    Reads TASKS_BACKEND env var (default: 'sql') and returns appropriate adapter.
    Supports test injection via set_adapter_for_testing().
    
    Returns:
        TaskAdapterBase instance
        
    Raises:
        ValueError: If backend is not supported or adapter creation fails
    """
    global _adapter, _test_adapter
    
    # Test injection takes precedence
    if _test_adapter is not None:
        return _test_adapter
    
    # Return existing singleton if available
    if _adapter is not None:
        return _adapter
    
    # Create new adapter based on backend selection
    backend = os.getenv("TASKS_BACKEND", "sql").lower()
    
    if backend == "sql":
        try:
            config = get_config()
            postgres_url = config.get_postgres_url()
            
            # Create connection pool
            db_pool = await asyncpg.create_pool(
                postgres_url, min_size=1, max_size=10
            )
            
            _adapter = SqlTasksAdapter(db_pool)
            logger.info("Initialized SQL tasks adapter")
            return _adapter
        except Exception as e:
            logger.error(f"Failed to create SQL tasks adapter: {e}")
            raise ValueError(f"Failed to initialize SQL tasks adapter: {e}")
    
    elif backend == "prefect":
        try:
            from agents.tasks.prefect_adapter import PrefectTasksAdapter
            _adapter = PrefectTasksAdapter()
            logger.info("Initialized Prefect tasks adapter")
            return _adapter
        except ImportError:
            raise ValueError(
                "Prefect adapter not available. Install prefect package or use TASKS_BACKEND=sql"
            )
        except Exception as e:
            logger.error(f"Failed to create Prefect tasks adapter: {e}")
            raise ValueError(f"Failed to initialize Prefect tasks adapter: {e}")
    
    else:
        raise ValueError(
            f"Unsupported TASKS_BACKEND: {backend}. Supported values: 'sql', 'prefect'"
        )


async def close_adapter() -> None:
    """Close adapter and cleanup resources"""
    global _adapter
    if _adapter and hasattr(_adapter, "db_pool"):
        # If it's a SQL adapter, close the pool
        if hasattr(_adapter.db_pool, "close"):
            await _adapter.db_pool.close()
    _adapter = None


