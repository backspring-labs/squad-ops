"""Developer agent skills.

Skills for code generation and implementation.
Part of SIP-0.8.8 Phase 4.
"""

from squadops.agents.skills.dev.code_generation import CodeGenerationSkill

# Skills exported for auto-discovery
SKILLS = [
    CodeGenerationSkill,
]

__all__ = [
    "CodeGenerationSkill",
    "SKILLS",
]
