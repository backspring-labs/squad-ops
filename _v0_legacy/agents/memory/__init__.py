"""
SquadOps Memory Protocol (SIP-042)
MemoryProvider interface and implementations

DEPRECATED: This module is deprecated as of SIP-0.8.7.
Use squadops.memory, squadops.ports.memory, and adapters.memory instead.
"""
import warnings

warnings.warn(
    "Importing from _v0_legacy.agents.memory is deprecated. "
    "Use squadops.memory, squadops.ports.memory, and adapters.memory instead. "
    "This module will be removed in version 0.9.0.",
    DeprecationWarning,
    stacklevel=2,
)

# Legacy exports (preserved for backwards compatibility)
from agents.memory.base import MemoryProvider
from agents.memory.lancedb_adapter import LanceDBAdapter
from agents.memory.sql_adapter import SqlAdapter

__all__ = [
    'MemoryProvider',
    'LanceDBAdapter',
    'SqlAdapter',
]

