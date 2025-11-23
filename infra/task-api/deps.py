"""
FastAPI dependencies for task API
"""

from agents.tasks.registry import get_tasks_adapter
from agents.tasks.base_adapter import TaskAdapterBase


async def get_tasks_adapter_dep() -> TaskAdapterBase:
    """
    FastAPI dependency function that returns the configured tasks adapter.
    
    Used via FastAPI Depends() in route handlers.
    
    Returns:
        TaskAdapterBase instance
    """
    return await get_tasks_adapter()


