"""QA agent skills.

Skills for testing and validation.
Part of SIP-0.8.8 Phase 4.
"""

from squadops.agents.skills.qa.test_execution import TestExecutionSkill
from squadops.agents.skills.qa.validation import ValidationSkill

# Skills exported for auto-discovery
SKILLS = [
    TestExecutionSkill,
    ValidationSkill,
]

__all__ = [
    "TestExecutionSkill",
    "ValidationSkill",
    "SKILLS",
]
