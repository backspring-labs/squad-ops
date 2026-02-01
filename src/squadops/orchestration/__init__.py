"""SquadOps Orchestration Layer.

Provides coordination between agents, handlers, and capabilities:
- AgentOrchestrator for multi-agent coordination
- HandlerRegistry for capability handler discovery
- HandlerExecutor implementing CapabilityExecutor interface

Part of SIP-0.8.8 Phase 6.
"""
from squadops.orchestration.orchestrator import AgentOrchestrator
from squadops.orchestration.handler_registry import HandlerRegistry
from squadops.orchestration.handler_executor import HandlerExecutor

__all__ = [
    "AgentOrchestrator",
    "HandlerRegistry",
    "HandlerExecutor",
]
