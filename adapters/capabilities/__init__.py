"""
Capability system adapters.

Provides concrete implementations of capability ports:
- FileSystemCapabilityRepository: Filesystem-based contract/workload storage
- ACICapabilityExecutor: ACI queue-based task execution
"""

from adapters.capabilities.aci_executor import ACICapabilityExecutor
from adapters.capabilities.factory import (
    create_capability_executor,
    create_capability_repository,
)
from adapters.capabilities.filesystem import FileSystemCapabilityRepository

__all__ = [
    "FileSystemCapabilityRepository",
    "ACICapabilityExecutor",
    "create_capability_repository",
    "create_capability_executor",
]
