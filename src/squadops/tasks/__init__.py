"""Tasks domain layer.

Provides domain models and compatibility bridge for task operations:
- TaskEnvelope: Frozen dataclass for ACI task envelope (SIP-0.8.8)
- TaskResult: Frozen dataclass for ACI task result (SIP-0.8.8)
- TaskIdentity: Frozen dataclass for task identification subset
- types module: Compatibility bridge for legacy Pydantic models

Part of SIP-0.8.7/0.8.8 Infrastructure Ports Migration.
"""

from squadops.tasks.exceptions import (
    TaskError,
    TaskNotFoundError,
    TaskStateError,
    TaskValidationError,
)
from squadops.tasks.models import TaskEnvelope, TaskIdentity, TaskResult

__all__ = [
    "TaskEnvelope",
    "TaskError",
    "TaskIdentity",
    "TaskNotFoundError",
    "TaskResult",
    "TaskStateError",
    "TaskValidationError",
]
