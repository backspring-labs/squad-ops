"""
Port interfaces for the capability contracts system.

Defines contracts for:
- CapabilityRepository (driven port): Storage abstraction for contracts and workloads
- CapabilityExecutor (driven port): Execution abstraction for task invocation
"""

from squadops.ports.capabilities.executor import CapabilityExecutor
from squadops.ports.capabilities.repository import CapabilityRepository

__all__ = [
    "CapabilityRepository",
    "CapabilityExecutor",
]
