"""Refinement handlers (#331 split from planning_tasks.py).

``governance.incorporate_feedback`` + ``qa.validate_refinement``
(SIP-0078 §5.10) and the refinement-specific time-budget section — its
only consumers are here.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from squadops.capabilities.handlers.base import (
    HandlerEvidence,
    HandlerResult,
)

if TYPE_CHECKING:
    from squadops.capabilities.handlers.context import ExecutionContext
from squadops.capabilities.handlers.planning.base import _format_time_budget, _PlanningTaskHandler


def _build_refinement_time_budget_section(time_budget_seconds: int | None) -> str:
    """Build time budget prompt section for refinement handlers."""
    if not time_budget_seconds or time_budget_seconds <= 0:
        return ""
    formatted = _format_time_budget(time_budget_seconds)
    return (
        f"\n\n## Time Budget\n\n"
        f"This cycle has a **{formatted}** time budget ({time_budget_seconds}s). "
        f"Preserve budget realism while incorporating feedback. "
        f"Do not expand scope beyond what can execute within this cycle budget."
    )


# ---------------------------------------------------------------------------
# 2 Refinement handlers (SIP-0078 §5.10)
# ---------------------------------------------------------------------------


class GovernanceIncorporateFeedbackHandler(_PlanningTaskHandler):
    """Refinement handler: incorporate feedback into planning artifact.

    Requires ``plan_artifact_refs`` in ``resolved_config`` (D17 fail-fast).
    Produces two artifacts:
    - ``planning_artifact_revised.md`` — the updated canonical planning artifact
    - ``plan_refinement.md`` — companion artifact documenting what changed
    """

    _handler_name = "governance_incorporate_feedback_handler"
    _capability_id = "governance.incorporate_feedback"
    _role = "lead"
    _artifact_name = "planning_artifact_revised.md"
    _request_template_id = "request.governance_incorporate_feedback"

    def _build_render_variables(
        self,
        prd: str,
        prior_outputs: dict[str, Any] | None,
        inputs: dict[str, Any],
    ) -> dict[str, str]:
        """Build template variables with artifact contents and refinement instructions."""
        raw_budget = inputs.get("resolved_config", {}).get("time_budget_seconds")
        time_budget_seconds = int(raw_budget) if raw_budget is not None else None
        budget_section = _build_refinement_time_budget_section(time_budget_seconds)

        variables: dict[str, str] = {"prd": prd, "role": self._role}
        if budget_section:
            variables["time_budget_section"] = budget_section

        # Include original planning artifact content if pre-resolved
        if prior_outputs and "artifact_contents" in prior_outputs:
            parts = []
            for name, content in prior_outputs["artifact_contents"].items():
                parts.append(f"\n\n## Original Planning Artifact: {name}\n\n{content}")
            variables["artifact_contents"] = "\n".join(parts)

        # Include refinement instructions
        if prior_outputs and "refinement_instructions" in prior_outputs:
            variables["refinement_instructions"] = (
                f"\n\n## Refinement Instructions\n\n{prior_outputs['refinement_instructions']}"
            )

        # Upstream outputs (excluding special keys)
        if prior_outputs:
            upstream = {
                k: v
                for k, v in prior_outputs.items()
                if k not in ("artifact_contents", "refinement_instructions")
            }
            variables["prior_outputs"] = self._format_prior_outputs(upstream or None)
        else:
            variables["prior_outputs"] = ""

        return variables

    def validate_inputs(
        self,
        inputs: dict[str, Any],
        contract=None,
    ) -> list[str]:
        errors = super().validate_inputs(inputs, contract)
        resolved_config = inputs.get("resolved_config", {})
        plan_refs = resolved_config.get("plan_artifact_refs")
        if not plan_refs:
            errors.append(
                "'plan_artifact_refs' is required in execution_overrides for refinement runs"
            )
        elif not isinstance(plan_refs, list) or len(plan_refs) != 1:
            errors.append("'plan_artifact_refs' must contain exactly one artifact reference")
        return errors

    def _build_user_prompt(
        self,
        prd: str,
        prior_outputs: dict[str, Any] | None,
        time_budget_seconds: int | None = None,
    ) -> str:
        """Build prompt with PRD, original planning artifact, and refinement instructions."""
        parts = [f"## Product Requirements Document\n\n{prd}"]
        budget_section = _build_refinement_time_budget_section(time_budget_seconds)
        if budget_section:
            parts.append(budget_section)

        # Include original planning artifact content if pre-resolved
        if prior_outputs and "artifact_contents" in prior_outputs:
            for name, content in prior_outputs["artifact_contents"].items():
                parts.append(f"\n\n## Original Planning Artifact: {name}\n\n{content}")

        # Include refinement instructions
        if prior_outputs and "refinement_instructions" in prior_outputs:
            parts.append(
                f"\n\n## Refinement Instructions\n\n{prior_outputs['refinement_instructions']}"
            )

        # Include upstream outputs
        if prior_outputs:
            upstream = {
                k: v
                for k, v in prior_outputs.items()
                if k not in ("artifact_contents", "refinement_instructions")
            }
            if upstream:
                parts.append("\n\n## Prior Analysis from Upstream Roles\n")
                for role, summary in upstream.items():
                    parts.append(f"### {role}\n{summary}\n")

        parts.append(f"\nPlease provide your {self._role} analysis and deliverables.")
        return "\n".join(parts)

    async def handle(
        self,
        context: ExecutionContext,
        inputs: dict[str, Any],
    ) -> HandlerResult:
        """Override to enforce D17 and produce differentiated companion artifact."""
        # D17 conditions 2/3: fail-fast if artifact content is empty/missing
        prior_outputs = inputs.get("prior_outputs") or {}
        artifact_contents = prior_outputs.get("artifact_contents", {})
        if not artifact_contents or all(not str(v).strip() for v in artifact_contents.values()):
            duration_ms = 0.0
            evidence = HandlerEvidence.create(
                handler_name=self._handler_name,
                capability_id=self._capability_id,
                duration_ms=duration_ms,
                inputs_hash=self._hash_dict(inputs),
            )
            return HandlerResult(
                success=False,
                outputs={},
                _evidence=evidence,
                error=(
                    "D17 fail-fast: planning artifact content is empty or unreadable. "
                    "Cannot incorporate feedback without the original planning artifact."
                ),
            )

        result = await super().handle(context, inputs)
        if not result.success:
            return result

        # Build differentiated companion artifact (SIP §5.9)
        resolved_config = inputs.get("resolved_config", {})
        plan_refs = resolved_config.get("plan_artifact_refs", [])
        ref_name = plan_refs[0] if plan_refs else "unknown"
        refinement_instructions = prior_outputs.get("refinement_instructions", "")

        companion_lines = [
            "---",
            f'original_plan_ref: "{ref_name}"',
            "refinement_source: execution_overrides",
            "---",
            "",
            "## Refinement Log",
            "",
            f"**Original artifact:** `{ref_name}`",
            "",
            "### Refinement Instructions",
            "",
            refinement_instructions if refinement_instructions else "(none provided)",
            "",
            "### Incorporation Summary",
            "",
            "The revised planning artifact (`planning_artifact_revised.md`) incorporates",
            "the refinement instructions above. See the revised artifact for the complete",
            "updated plan with all changes applied.",
        ]

        result.outputs["artifacts"].append(
            {
                "name": "plan_refinement.md",
                "content": "\n".join(companion_lines),
                "media_type": "text/markdown",
                "type": "document",
            },
        )
        return result


class QAValidateRefinementHandler(_PlanningTaskHandler):
    """Refinement handler: verify acceptance criteria still hold after refinement."""

    _handler_name = "qa_validate_refinement_handler"
    _capability_id = "qa.validate_refinement"
    _role = "qa"
    _artifact_name = "refinement_validation.md"
