"""
Capability system adapters.

Provides concrete implementations of capability ports:
- FileSystemCapabilityRepository: Filesystem-based contract/workload storage

(#1241: ``ACICapabilityExecutor`` and ``create_capability_executor`` were deleted — a
queue-backed executor nothing constructed, importing a package that did not exist, which
made this whole package unimportable. Task dispatch over the queue is
``adapters.cycles.task_dispatcher.TaskDispatcher``.)
"""

from adapters.capabilities.factory import create_capability_repository
from adapters.capabilities.filesystem import FileSystemCapabilityRepository

__all__ = [
    "FileSystemCapabilityRepository",
    "create_capability_repository",
]
