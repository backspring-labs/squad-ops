"""Compatibility shim — planning task handlers moved to the ``planning`` package (#331).

The 1,887-line module was split into ``squadops.capabilities.handlers.planning``
(one module per plan-authoring stage + shared ``base``). This path re-exports
the same names so existing importers and tests work unchanged. New code should
import from ``squadops.capabilities.handlers.planning`` directly.
"""

from squadops.capabilities.handlers.planning import (
    DataResearchContextHandler,
    DevelopmentDesignPlanHandler,
    DevelopmentProposePlanTasksHandler,
    GovernanceIncorporateFeedbackHandler,
    GovernanceMergePlanHandler,
    GovernancePreparePlanAuthoringBriefHandler,
    GovernanceReviewPlanHandler,
    QADefineTestStrategyHandler,
    QaProposePlanTasksHandler,
    QAValidateRefinementHandler,
    StrategyFrameObjectiveHandler,
    StrategyProposePlanGuidanceHandler,
    _build_refinement_time_budget_section,
    _build_time_budget_section,
    _content_summary,
    _format_time_budget,
    _PlanningTaskHandler,
    _ProposeBaseHandler,
)

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
