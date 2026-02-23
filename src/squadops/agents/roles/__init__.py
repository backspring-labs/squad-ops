"""SquadOps Agent Roles.

Concrete role implementations for the agent framework.
Part of SIP-0.8.8 Phase 3.
"""
from squadops.agents.roles.builder import BuilderAgent
from squadops.agents.roles.data import DataAgent
from squadops.agents.roles.dev import DevAgent
from squadops.agents.roles.lead import LeadAgent
from squadops.agents.roles.qa import QAAgent
from squadops.agents.roles.strat import StratAgent

__all__ = [
    "LeadAgent",
    "DevAgent",
    "QAAgent",
    "StratAgent",
    "DataAgent",
    "BuilderAgent",
]
