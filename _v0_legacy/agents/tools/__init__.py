"""
Tools - Shared integration adapters for capabilities.

DEPRECATED: This module is deprecated as of SIP-0.8.7.
Use squadops.tools, squadops.ports.tools, and adapters.tools instead.

Tools are integration adapters for external systems (CLI, SDK, HTTP API, etc.)
that provide I/O, rate limits, and error handling. They are used by capabilities
to perform specific operations.

Tools in this directory:
- AppBuilder: JSON workflow application building using LLM
- DockerManager: Docker image and container management
- FileManager: File system operations
- VersionManager: Application version management
"""
import warnings

warnings.warn(
    "Importing from _v0_legacy.agents.tools is deprecated. "
    "Use squadops.tools, squadops.ports.tools, and adapters.tools instead. "
    "This module will be removed in version 0.9.0.",
    DeprecationWarning,
    stacklevel=2,
)

# Re-export new canonical symbols for migration convenience
from adapters.tools.factory import (
    create_container_provider,
    create_filesystem_provider,
    create_vcs_provider,
)
from squadops.tools.models import ContainerResult, ContainerSpec, VCSStatus
from squadops.tools.security import PathSecurityError, PathSecurityPolicy

__all__ = [
    # New (canonical)
    'create_container_provider',
    'create_filesystem_provider',
    'create_vcs_provider',
    'ContainerResult',
    'ContainerSpec',
    'VCSStatus',
    'PathSecurityError',
    'PathSecurityPolicy',
]

