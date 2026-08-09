"""Framing-tail handlers (#331 split from planning_tasks.py).

The four thin per-role framing stages (SIP-0078 §5.3) — class-attribute
specializations of the shared base; all behavior lives there.
"""

from __future__ import annotations

from typing import Any

from squadops.capabilities.handlers.planning.base import _PlanningTaskHandler

# ---------------------------------------------------------------------------
# 5 Planning handlers (SIP-0078 §5.3)
# ---------------------------------------------------------------------------


class DataResearchContextHandler(_PlanningTaskHandler):
    """Planning handler: gather constraints, prior patterns, risk areas."""

    _handler_name = "data_research_context_handler"
    _capability_id = "data.research_context"
    _role = "data"
    _artifact_name = "context_research.md"


class StrategyFrameObjectiveHandler(_PlanningTaskHandler):
    """Planning handler: frame objective, scope, non-goals, acceptance criteria."""

    _handler_name = "strategy_frame_objective_handler"
    _capability_id = "strategy.frame_objective"
    _role = "strat"
    _artifact_name = "objective_frame.md"


class DevelopmentDesignPlanHandler(_PlanningTaskHandler):
    """Planning handler: technical design, interfaces, sequencing, proto validation."""

    _handler_name = "development_design_plan_handler"
    _capability_id = "development.design_plan"
    _role = "dev"
    _artifact_name = "technical_design.md"

    async def _rejection_context_section(self, renderer: Any, inputs: dict[str, Any]) -> str:
        """The revision request, or "" (#811).

        Overrides the planning base, which renders the *plan* re-roll appendix — a rejected
        `implementation_plan.yaml` this stage did not write, under rules about task shape that
        say nothing about a technical design. Same #669 rail, a document-appropriate asset.
        """
        reasons = [
            str(r).strip() for r in (inputs.get("rejection_reasons") or []) if str(r).strip()
        ]
        if not reasons:
            return ""
        rendered = await renderer.render(
            "request.design_revision_request_appendix",
            {"reviewer_notes": "\n".join(f"- {r}" for r in reasons)},
        )
        return rendered.content


class QADefineTestStrategyHandler(_PlanningTaskHandler):
    """Planning handler: acceptance checklist, test strategy, defect severity rubric."""

    _handler_name = "qa_define_test_strategy_handler"
    _capability_id = "qa.define_test_strategy"
    _role = "qa"
    _artifact_name = "test_strategy.md"
