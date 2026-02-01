"""Capability handlers for orchestrating skill execution.

Handlers bridge capability contracts with skill-based execution.
Part of SIP-0.8.8 Phase 5.
"""
from squadops.capabilities.handlers.base import (
    CapabilityHandler,
    HandlerResult,
    HandlerEvidence,
)
from squadops.capabilities.handlers.context import ExecutionContext

__all__ = [
    "CapabilityHandler",
    "HandlerResult",
    "HandlerEvidence",
    "ExecutionContext",
]
