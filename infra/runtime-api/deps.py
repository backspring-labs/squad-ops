"""
FastAPI dependencies for Runtime API (SIP-0048: renamed from task API)
"""

from agents.tasks.base_adapter import TaskAdapterBase
from agents.tasks.registry import get_tasks_adapter


async def get_tasks_adapter_dep() -> TaskAdapterBase:
    """
    FastAPI dependency function that returns the configured tasks adapter.
    
    Used via FastAPI Depends() in route handlers.
    
    Returns:
        TaskAdapterBase instance
    """
    return await get_tasks_adapter()


