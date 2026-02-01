"""SquadOps Skills Infrastructure.

Provides the foundation for agent skills:
- Skill base class for atomic operations
- SkillContext for port access during execution
- SkillRegistry for discovery and execution

Part of SIP-0.8.8.
"""
from squadops.agents.skills.base import Skill
from squadops.agents.skills.context import SkillContext
from squadops.agents.skills.registry import SkillRegistry

__all__ = [
    "Skill",
    "SkillContext",
    "SkillRegistry",
]
