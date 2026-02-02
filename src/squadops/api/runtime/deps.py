"""
FastAPI dependencies for Runtime API (SIP-0048).

Part of SIP-0.8.8 migration from _v0_legacy/infra/runtime-api/deps.py
"""

from squadops.ports.tasks.registry import TaskRegistryPort

# Global adapter instance (initialized at startup)
_adapter: TaskRegistryPort | None = None


def set_tasks_adapter(adapter: TaskRegistryPort) -> None:
    """Set the tasks adapter instance for dependency injection."""
    global _adapter
    _adapter = adapter


async def get_tasks_adapter_dep() -> TaskRegistryPort:
    """
    FastAPI dependency function that returns the configured tasks adapter.

    Used via FastAPI Depends() in route handlers.

    Returns:
        TaskRegistryPort instance

    Raises:
        RuntimeError: If adapter not initialized
    """
    if _adapter is None:
        raise RuntimeError("Tasks adapter not initialized. Call set_tasks_adapter() at startup.")
    return _adapter
