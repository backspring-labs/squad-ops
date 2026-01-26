"""
SquadOps port interfaces (hexagonal architecture).

Ports define contracts between the domain layer and external systems.
Adapters implement these contracts for specific technologies.
"""

from squadops.ports.prompts.repository import PromptRepository
from squadops.ports.prompts.service import PromptService

__all__ = [
    "PromptRepository",
    "PromptService",
]
