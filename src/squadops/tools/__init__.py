"""Tools domain layer.

Provides domain models and security policy for tool operations:
- ContainerSpec, ContainerResult: Container execution models
- VCSStatus: Version control status model
- PathSecurityPolicy: Path validation for filesystem operations

Part of SIP-0.8.7 Infrastructure Ports Migration.
"""

from squadops.tools.exceptions import (
    ToolContainerError,
    ToolError,
    ToolFileNotFoundError,
    ToolIOError,
    ToolPermissionError,
    ToolVCSError,
)
from squadops.tools.models import ContainerResult, ContainerSpec, VCSStatus
from squadops.tools.security import PathSecurityError, PathSecurityPolicy

__all__ = [
    "ContainerResult",
    "ContainerSpec",
    "PathSecurityError",
    "PathSecurityPolicy",
    "ToolContainerError",
    "ToolError",
    "ToolFileNotFoundError",
    "ToolIOError",
    "ToolPermissionError",
    "ToolVCSError",
    "VCSStatus",
]
