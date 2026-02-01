"""Tasks domain layer.

Provides domain models and compatibility bridge for task operations:
- TaskIdentity: New frozen dataclass for task identification
- types module: Compatibility bridge for legacy TaskEnvelope

Part of SIP-0.8.7 Infrastructure Ports Migration.
"""
from squadops.tasks.exceptions import (
    TaskError,
    TaskNotFoundError,
    TaskStateError,
    TaskValidationError,
)
from squadops.tasks.models import TaskIdentity

__all__ = [
    "TaskError",
    "TaskIdentity",
    "TaskNotFoundError",
    "TaskStateError",
    "TaskValidationError",
]
