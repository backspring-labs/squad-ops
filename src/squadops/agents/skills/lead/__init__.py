"""Lead agent skills.

Skills for task orchestration and delegation.
Part of SIP-0.8.8 Phase 4.
"""

from squadops.agents.skills.lead.task_analysis import TaskAnalysisSkill
from squadops.agents.skills.lead.task_delegation import TaskDelegationSkill

# Skills exported for auto-discovery
SKILLS = [
    TaskAnalysisSkill,
    TaskDelegationSkill,
]

__all__ = [
    "TaskAnalysisSkill",
    "TaskDelegationSkill",
    "SKILLS",
]
