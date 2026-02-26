"""Tasks adapters.

Provides implementations of task registry ports:
- SQLTaskAdapter: PostgreSQL-based task persistence
- PrefectTaskAdapter: Stub for Prefect (full implementation in 0.8.8)

Part of SIP-0.8.7 Infrastructure Ports Migration.
"""

from adapters.tasks.factory import create_task_registry_provider
from adapters.tasks.prefect import PrefectTaskAdapter
from adapters.tasks.sql import SQLTaskAdapter

__all__ = [
    "PrefectTaskAdapter",
    "SQLTaskAdapter",
    "create_task_registry_provider",
]
