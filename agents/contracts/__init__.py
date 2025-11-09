"""
Contract definitions for SquadOps agent communication.

Defines structured data contracts for agent requests, responses,
and other inter-agent communication protocols.
"""

from .agent_request import AgentRequest
from .agent_response import AgentResponse, Error, Timing

__all__ = ['AgentRequest', 'AgentResponse', 'Error', 'Timing']




