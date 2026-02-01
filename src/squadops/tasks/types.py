"""Tasks compatibility bridge.

Single-source import point for task types.
Combines new frozen dataclasses with legacy Pydantic models during migration.

Part of SIP-0.8.7/0.8.8 Infrastructure Ports Migration.
"""
# New frozen dataclass models (SIP-0.8.8)
from squadops.tasks.models import (
    TaskEnvelope,
    TaskIdentity,
    TaskResult,
)

# Legacy Pydantic models (still needed for DB operations)
# This is the ONLY file allowed to import from _v0_legacy.agents.tasks.models
# (enforced by CI legacy import checker)
from _v0_legacy.agents.tasks.models import (
    Artifact,
    FlowState,
    Task,
    TaskCreate,
    TaskFilters,
    TaskResult as LegacyTaskResult,
    TaskState,
    TaskEnvelope as LegacyTaskEnvelope,
)

__all__ = [
    # New frozen dataclass models
    "TaskEnvelope",
    "TaskIdentity",
    "TaskResult",
    # Legacy Pydantic models
    "Artifact",
    "FlowState",
    "LegacyTaskEnvelope",
    "LegacyTaskResult",
    "Task",
    "TaskCreate",
    "TaskFilters",
    "TaskState",
]
