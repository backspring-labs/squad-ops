"""Strategy agent skills.

Skills for strategic planning and analysis.
Part of SIP-0.8.8 Phase 4.
"""

from squadops.agents.skills.strat.strategy_analysis import StrategyAnalysisSkill

# Skills exported for auto-discovery
SKILLS = [
    StrategyAnalysisSkill,
]

__all__ = [
    "StrategyAnalysisSkill",
    "SKILLS",
]
