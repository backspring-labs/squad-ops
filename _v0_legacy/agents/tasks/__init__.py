"""
Tasks Adapter Framework
Provides pluggable backend adapters for task management

DEPRECATED: This module is deprecated as of SIP-0.8.7.
Use squadops.tasks, squadops.ports.tasks, and adapters.tasks instead.

NOTE: For TaskEnvelope/Task models, use squadops.tasks.types which provides
the compatibility bridge to these legacy models.
"""
import warnings

warnings.warn(
    "Importing from _v0_legacy.agents.tasks is deprecated. "
    "Use squadops.tasks, squadops.ports.tasks, and adapters.tasks instead. "
    "This module will be removed in version 0.9.0.",
    DeprecationWarning,
    stacklevel=2,
)

# Legacy exports (preserved for backwards compatibility)
from agents.tasks.base_adapter import TaskAdapterBase
from agents.tasks.errors import (
    TaskAdapterConfigurationError,
    TaskAdapterError,
    TaskConflictError,
    TaskNotFoundError,
)
from agents.tasks.models import (
    Artifact,
    FlowCreate,
    FlowRun,
    FlowState,
    FlowUpdate,
    Task,
    TaskCreate,
    TaskFilters,
    TaskState,
    TaskStatus,
    TaskSummary,
)

__all__ = [
    "TaskAdapterBase",
    "Task",
    "TaskCreate",
    "TaskState",
    "TaskFilters",
    "Artifact",
    "FlowRun",
    "FlowCreate",
    "FlowUpdate",
    "FlowState",
    "TaskStatus",
    "TaskSummary",
    "TaskAdapterError",
    "TaskNotFoundError",
    "TaskConflictError",
    "TaskAdapterConfigurationError",
]

