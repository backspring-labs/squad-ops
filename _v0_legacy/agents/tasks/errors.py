"""
Task Adapter Error Classes
Standardized exceptions for task adapter backends
"""


class TaskAdapterError(Exception):
    """Base exception for task adapter backends."""
    pass


class TaskNotFoundError(TaskAdapterError):
    """Raised when a task or flow is not found."""
    pass


class TaskConflictError(TaskAdapterError):
    """Raised when attempting to create a duplicate task or flow."""
    pass


class TaskAdapterConfigurationError(TaskAdapterError):
    """Raised when adapter configuration or setup fails."""
    pass


