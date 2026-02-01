"""Tasks compatibility bridge.

Single-source import point for legacy TaskEnvelope types.
Full migration to frozen dataclasses deferred to 0.8.8.

Part of SIP-0.8.7 Infrastructure Ports Migration.
"""
# This is the ONLY file allowed to import from _v0_legacy.agents.tasks.models
# (enforced by CI legacy import checker)
from _v0_legacy.agents.tasks.models import (
    Artifact,
    FlowState,
    Task,
    TaskCreate,
    TaskFilters,
    TaskResult,
    TaskState,
)

# Type alias for documentation clarity
LegacyTaskEnvelope = Task

__all__ = [
    "Artifact",
    "FlowState",
    "LegacyTaskEnvelope",
    "Task",
    "TaskCreate",
    "TaskFilters",
    "TaskResult",
    "TaskState",
]
