"""
Squad shims for 1.0 execution layer.

These are thin subclasses of the DI-first `BaseAgent` that only provide a default
identity (agent_id) and are ready for future 1.0-style config entrypoints.
"""

from squadops.execution.squad.data import DataAgent
from squadops.execution.squad.dev import DevAgent
from squadops.execution.squad.lead import LeadAgent
from squadops.execution.squad.qa import QaAgent
from squadops.execution.squad.strat import StrategyAgent

__all__ = ["LeadAgent", "StrategyAgent", "DevAgent", "QaAgent", "DataAgent"]

