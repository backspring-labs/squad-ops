"""Wrap-up task handlers — LLM-powered handlers for wrap-up workload pipeline.

5 handlers whose capability_ids match the pinned task_type values from
WRAPUP_TASK_STEPS (SIP-0080 §7.1). All extend ``_PlanningTaskHandler``
to activate the task_type prompt layer for role-specific wrap-up behavior.

DataGatherEvidenceHandler has a validate_inputs() override (requires impl_run_id).
GovernanceCloseoutDecisionHandler and GovernancePublishHandoffHandler have
handle() overrides with structural YAML frontmatter validation.
DataClassifyUnresolvedHandler has lightweight suggested_owner validation (warn, not fail).

Part of SIP-0080.
"""

from __future__ import annotations

import logging
import re
from typing import TYPE_CHECKING, Any

import yaml

from squadops.capabilities.handlers.base import HandlerResult
from squadops.capabilities.handlers.planning_tasks import _PlanningTaskHandler
from squadops.cycles.wrapup_models import (
    ALLOWED_SUGGESTED_OWNERS,
    CloseoutRecommendation,
    ConfidenceClassification,
    NextCycleRecommendation,
)

if TYPE_CHECKING:
    from squadops.capabilities.handlers.context import ExecutionContext

logger = logging.getLogger(__name__)

_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)

_VALID_CONFIDENCE = {
    ConfidenceClassification.VERIFIED_COMPLETE,
    ConfidenceClassification.COMPLETE_WITH_CAVEATS,
    ConfidenceClassification.PARTIAL_COMPLETION,
    ConfidenceClassification.NOT_SUFFICIENTLY_VERIFIED,
    ConfidenceClassification.INCONCLUSIVE,
    ConfidenceClassification.FAILED,
}

_VALID_RECOMMENDATION = {
    CloseoutRecommendation.PROCEED,
    CloseoutRecommendation.HARDEN,
    CloseoutRecommendation.REPLAN,
    CloseoutRecommendation.HALT,
}

_VALID_NEXT_CYCLE = {
    NextCycleRecommendation.PLANNING,
    NextCycleRecommendation.IMPLEMENTATION,
    NextCycleRecommendation.HARDENING,
    NextCycleRecommendation.RESEARCH,
    NextCycleRecommendation.NONE,
}

# Pattern to find suggested_owner values in markdown tables or YAML-like content
_SUGGESTED_OWNER_RE = re.compile(r"suggested_owner\s*[:=|]\s*(\w+)", re.IGNORECASE)


class DataGatherEvidenceHandler(_PlanningTaskHandler):
    """Compile evidence inventory from implementation run artifacts.

    Requires ``impl_run_id`` in ``execution_overrides`` (via ``resolved_config``).
    Missing ``artifact_contents`` is degraded mode — not a hard error (D5).
    """

    _handler_name = "data_gather_evidence_handler"
    _capability_id = "data.gather_evidence"
    _role = "data"
    _artifact_name = "evidence_inventory.md"

    def validate_inputs(self, inputs: dict[str, Any], contract=None) -> list[str]:
        errors = super().validate_inputs(inputs, contract)
        resolved_config = inputs.get("resolved_config", {})
        if not resolved_config.get("impl_run_id"):
            errors.append("'impl_run_id' is required in execution_overrides for wrap-up runs")
        return errors


class QAAssessOutcomesHandler(_PlanningTaskHandler):
    """Planned-vs-actual comparison, acceptance criteria evaluation."""

    _handler_name = "qa_assess_outcomes_handler"
    _capability_id = "qa.assess_outcomes"
    _role = "qa"
    _artifact_name = "outcome_assessment.md"


class DataClassifyUnresolvedHandler(_PlanningTaskHandler):
    """Categorize unresolved items by type and severity.

    Post-generation: scans for suggested_owner values and logs warnings
    for any not in ALLOWED_SUGGESTED_OWNERS. Warn, not fail (V1).
    """

    _handler_name = "data_classify_unresolved_handler"
    _capability_id = "data.classify_unresolved"
    _role = "data"
    _artifact_name = "unresolved_items.md"

    async def handle(
        self,
        context: ExecutionContext,
        inputs: dict[str, Any],
    ) -> HandlerResult:
        result = await super().handle(context, inputs)
        if not result.success:
            return result

        content = result.outputs["artifacts"][0]["content"]
        owners = _SUGGESTED_OWNER_RE.findall(content)
        for owner in owners:
            if owner.lower() not in ALLOWED_SUGGESTED_OWNERS:
                logger.warning(
                    "Unrecognized suggested_owner '%s' in unresolved items (allowed: %s)",
                    owner,
                    ", ".join(sorted(ALLOWED_SUGGESTED_OWNERS)),
                )

        return result


def _parse_frontmatter(content: str) -> tuple[dict | None, str | None]:
    """Parse YAML frontmatter from markdown content.

    Returns:
        (parsed_dict, error_message) — one of the two is None.
    """
    m = _FRONTMATTER_RE.match(content)
    if not m:
        return None, "missing YAML frontmatter (expected --- delimiters)"

    try:
        fm = yaml.safe_load(m.group(1))
    except yaml.YAMLError as exc:
        return None, f"invalid YAML frontmatter: {exc}"

    if not isinstance(fm, dict):
        return None, "YAML frontmatter is not a mapping"

    return fm, None


class GovernanceCloseoutDecisionHandler(_PlanningTaskHandler):
    """Produce closeout artifact with structural frontmatter validation.

    After LLM generation, validates that YAML frontmatter contains:
    - ``confidence``: one of 6 ConfidenceClassification values
    - ``readiness_recommendation``: one of 4 CloseoutRecommendation values

    Invalid frontmatter → HandlerResult(success=False).
    """

    _handler_name = "governance_closeout_decision_handler"
    _capability_id = "governance.closeout_decision"
    _role = "lead"
    _artifact_name = "closeout_artifact.md"

    async def handle(
        self,
        context: ExecutionContext,
        inputs: dict[str, Any],
    ) -> HandlerResult:
        result = await super().handle(context, inputs)
        if not result.success:
            return result

        content = result.outputs["artifacts"][0]["content"]
        fm, error = _parse_frontmatter(content)
        if error:
            return HandlerResult(
                success=False,
                outputs={},
                _evidence=result._evidence,
                error=f"Closeout artifact {error}",
            )

        if "confidence" not in fm:
            return HandlerResult(
                success=False,
                outputs={},
                _evidence=result._evidence,
                error="Closeout artifact frontmatter missing 'confidence' field",
            )

        if fm["confidence"] not in _VALID_CONFIDENCE:
            return HandlerResult(
                success=False,
                outputs={},
                _evidence=result._evidence,
                error=(
                    f"Closeout artifact 'confidence' must be one of "
                    f"{sorted(_VALID_CONFIDENCE)}, got: {fm['confidence']!r}"
                ),
            )

        if "readiness_recommendation" not in fm:
            return HandlerResult(
                success=False,
                outputs={},
                _evidence=result._evidence,
                error=("Closeout artifact frontmatter missing 'readiness_recommendation' field"),
            )

        if fm["readiness_recommendation"] not in _VALID_RECOMMENDATION:
            return HandlerResult(
                success=False,
                outputs={},
                _evidence=result._evidence,
                error=(
                    f"Closeout artifact 'readiness_recommendation' must be one of "
                    f"{sorted(_VALID_RECOMMENDATION)}, "
                    f"got: {fm['readiness_recommendation']!r}"
                ),
            )

        return result


class GovernancePublishHandoffHandler(_PlanningTaskHandler):
    """Produce handoff artifact with structural frontmatter validation.

    After LLM generation, validates that YAML frontmatter contains:
    - ``next_cycle_type``: one of 5 NextCycleRecommendation values

    Invalid frontmatter → HandlerResult(success=False).
    """

    _handler_name = "governance_publish_handoff_handler"
    _capability_id = "governance.publish_handoff"
    _role = "lead"
    _artifact_name = "handoff_artifact.md"

    async def handle(
        self,
        context: ExecutionContext,
        inputs: dict[str, Any],
    ) -> HandlerResult:
        result = await super().handle(context, inputs)
        if not result.success:
            return result

        content = result.outputs["artifacts"][0]["content"]
        fm, error = _parse_frontmatter(content)
        if error:
            return HandlerResult(
                success=False,
                outputs={},
                _evidence=result._evidence,
                error=f"Handoff artifact {error}",
            )

        if "next_cycle_type" not in fm:
            return HandlerResult(
                success=False,
                outputs={},
                _evidence=result._evidence,
                error="Handoff artifact frontmatter missing 'next_cycle_type' field",
            )

        if fm["next_cycle_type"] not in _VALID_NEXT_CYCLE:
            return HandlerResult(
                success=False,
                outputs={},
                _evidence=result._evidence,
                error=(
                    f"Handoff artifact 'next_cycle_type' must be one of "
                    f"{sorted(_VALID_NEXT_CYCLE)}, "
                    f"got: {fm['next_cycle_type']!r}"
                ),
            )

        return result
