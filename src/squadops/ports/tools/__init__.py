"""Tools port interfaces.

Provides abstract base classes for tool adapters:
- FileSystemPort: File operations
- ContainerPort: Container runtime operations
- VersionControlPort: VCS operations

Part of SIP-0.8.7 Infrastructure Ports Migration.
"""
from squadops.ports.tools.container import ContainerPort
from squadops.ports.tools.filesystem import FileSystemPort
from squadops.ports.tools.vcs import VersionControlPort

__all__ = [
    "ContainerPort",
    "FileSystemPort",
    "VersionControlPort",
]
