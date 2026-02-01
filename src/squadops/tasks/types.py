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
# Migrated from _v0_legacy as part of SIP-0.8.9
from squadops.tasks.legacy_models import (
    Artifact,
    FlowState,
    LegacyTaskEnvelope,
    LegacyTaskResult,
    Task,
    TaskCreate,
    TaskFilters,
    TaskState,
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
