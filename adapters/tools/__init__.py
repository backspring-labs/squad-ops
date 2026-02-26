"""Tools adapters.

Provides implementations of tool ports:
- LocalFileSystemAdapter: Local filesystem operations
- PathValidatedFileSystem: Filesystem with path security
- DockerAdapter: Docker container operations
- GitAdapter: Git version control operations
- PathValidatedVCS: VCS with path security

Part of SIP-0.8.7 Infrastructure Ports Migration.
"""

from adapters.tools.docker import DockerAdapter
from adapters.tools.factory import (
    create_container_provider,
    create_filesystem_provider,
    create_vcs_provider,
)
from adapters.tools.git import GitAdapter, PathValidatedVCS
from adapters.tools.local_filesystem import (
    LocalFileSystemAdapter,
    PathValidatedFileSystem,
)

__all__ = [
    "DockerAdapter",
    "GitAdapter",
    "LocalFileSystemAdapter",
    "PathValidatedFileSystem",
    "PathValidatedVCS",
    "create_container_provider",
    "create_filesystem_provider",
    "create_vcs_provider",
]
