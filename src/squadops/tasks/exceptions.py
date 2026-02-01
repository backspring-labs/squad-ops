"""Tasks domain exceptions.

Part of SIP-0.8.7 Infrastructure Ports Migration.
"""


class TaskError(Exception):
    """Base exception for task operations."""

    pass


class TaskNotFoundError(TaskError):
    """Task not found."""

    pass


class TaskValidationError(TaskError):
    """Task validation failed."""

    pass


class TaskStateError(TaskError):
    """Invalid task state transition."""

    pass
