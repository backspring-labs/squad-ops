"""
SquadOps Memory Protocol (SIP-042)
MemoryProvider interface and implementations
"""

from agents.memory.base import MemoryProvider
from agents.memory.lancedb_adapter import LanceDBAdapter
from agents.memory.sql_adapter import SqlAdapter

__all__ = ['MemoryProvider', 'LanceDBAdapter', 'SqlAdapter']

