"""Capability handlers.

Handlers fulfill capability contracts by executing against ports.
Part of SIP-0.8.8 Phase 5.
"""

from squadops.capabilities.handlers.base import (
    CapabilityHandler,
    HandlerEvidence,
    HandlerResult,
)
from squadops.capabilities.handlers.context import ExecutionContext

__all__ = [
    "CapabilityHandler",
    "HandlerResult",
    "HandlerEvidence",
    "ExecutionContext",
]
