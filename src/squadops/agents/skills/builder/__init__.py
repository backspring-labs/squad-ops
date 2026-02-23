"""Builder agent skills.

Skills for artifact production from approved plans.
Part of SIP-0071 Phase 3.
"""
from squadops.agents.skills.builder.artifact_generation import ArtifactGenerationSkill

# Skills exported for auto-discovery
SKILLS = [
    ArtifactGenerationSkill,
]

__all__ = [
    "ArtifactGenerationSkill",
    "SKILLS",
]
