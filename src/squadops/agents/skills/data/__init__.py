"""Skills for the data role.

Skills for analytics and data processing.
Part of SIP-0.8.8 Phase 4.
"""
from squadops.agents.skills.data.metrics_collection import MetricsCollectionSkill

# Skills exported for auto-discovery
SKILLS = [
    MetricsCollectionSkill,
]

__all__ = [
    "MetricsCollectionSkill",
    "SKILLS",
]
