"""Planning/refinement task handlers package — split from planning_tasks.py (#331).

One module per plan-authoring stage (SIP-0093's own vocabulary: framing tail →
brief → propose → merge → review, plus the refinement pair) with the shared
``_PlanningTaskHandler`` base beside them. The legacy import path
``squadops.capabilities.handlers.planning_tasks`` re-exports this package's
names and remains the compatibility surface for existing importers; new code
should import from this package directly.
"""

from squadops.capabilities.handlers.planning.base import (
    _build_time_budget_section,
    _content_summary,
    _format_time_budget,
    _PlanningTaskHandler,
)
from squadops.capabilities.handlers.planning.brief import (
    GovernancePreparePlanAuthoringBriefHandler,
)
from squadops.capabilities.handlers.planning.framing import (
    DataResearchContextHandler,
    DevelopmentDesignPlanHandler,
    QADefineTestStrategyHandler,
    StrategyFrameObjectiveHandler,
)
from squadops.capabilities.handlers.planning.merge import GovernanceMergePlanHandler
from squadops.capabilities.handlers.planning.propose import (
    DevelopmentProposePlanTasksHandler,
    QaProposePlanTasksHandler,
    StrategyProposePlanGuidanceHandler,
    _ProposeBaseHandler,
)
from squadops.capabilities.handlers.planning.refinement import (
    GovernanceIncorporateFeedbackHandler,
    QAValidateRefinementHandler,
    _build_refinement_time_budget_section,
)
from squadops.capabilities.handlers.planning.review import GovernanceReviewPlanHandler

__all__ = [
    "DataResearchContextHandler",
    "DevelopmentDesignPlanHandler",
    "DevelopmentProposePlanTasksHandler",
    "GovernanceIncorporateFeedbackHandler",
    "GovernanceMergePlanHandler",
    "GovernancePreparePlanAuthoringBriefHandler",
    "GovernanceReviewPlanHandler",
    "QADefineTestStrategyHandler",
    "QAValidateRefinementHandler",
    "QaProposePlanTasksHandler",
    "StrategyFrameObjectiveHandler",
    "StrategyProposePlanGuidanceHandler",
    "_PlanningTaskHandler",
    "_ProposeBaseHandler",
    "_build_refinement_time_budget_section",
    "_build_time_budget_section",
    "_content_summary",
    "_format_time_budget",
]
