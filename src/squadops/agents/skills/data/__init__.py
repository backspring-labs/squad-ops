"""Data agent skills.

Skills for analytics and data processing.
Part of SIP-0.8.8 Phase 4.
"""
from squadops.agents.skills.data.data_analysis import DataAnalysisSkill
from squadops.agents.skills.data.metrics_collection import MetricsCollectionSkill

# Skills exported for auto-discovery
SKILLS = [
    DataAnalysisSkill,
    MetricsCollectionSkill,
]

__all__ = [
    "DataAnalysisSkill",
    "MetricsCollectionSkill",
    "SKILLS",
]
