"""Tools domain exceptions.

Domain-prefixed exceptions to avoid collision with Python built-ins.
Part of SIP-0.8.7 Infrastructure Ports Migration.
"""


class ToolError(Exception):
    """Base exception for tool operations."""

    pass


class ToolFileNotFoundError(ToolError):
    """File not found (domain-prefixed to avoid FileNotFoundError collision)."""

    pass


class ToolPermissionError(ToolError):
    """Permission denied (domain-prefixed to avoid PermissionError collision)."""

    pass


class ToolIOError(ToolError):
    """I/O error (domain-prefixed to avoid IOError collision)."""

    pass


class ToolContainerError(ToolError):
    """Container operation failed."""

    pass


class ToolVCSError(ToolError):
    """Version control operation failed."""

    pass
