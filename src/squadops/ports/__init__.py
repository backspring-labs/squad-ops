"""
SquadOps port interfaces (hexagonal architecture).

Ports define contracts between the domain layer and external systems.
Adapters implement these contracts for specific technologies.
"""

from squadops.ports.audit import AuditPort
from squadops.ports.auth.authentication import AuthPort
from squadops.ports.auth.authorization import AuthorizationPort
from squadops.ports.prompts.repository import PromptRepository
from squadops.ports.prompts.service import PromptService

__all__ = [
    "AuditPort",
    "AuthPort",
    "AuthorizationPort",
    "PromptRepository",
    "PromptService",
]
