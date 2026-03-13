"""Planning task handlers — LLM-powered handlers for planning workload pipeline.

5 planning handlers and 2 refinement handlers whose capability_ids match
the pinned task_type values from PLANNING_TASK_STEPS and REFINEMENT_TASK_STEPS
(SIP-0078 §5.3, §5.10).

All planning/refinement handlers extend ``_PlanningTaskHandler``, which
overrides the system prompt assembly to activate the ``task_type`` prompt
layer via ``context.ports.prompt_service.assemble(role, hook, task_type=...)``.
This is the key difference from standard ``_CycleTaskHandler`` which calls
``get_system_prompt(role)`` (no task_type layer).

Part of SIP-0078.
"""

from __future__ import annotations

import logging
import re
import time
from typing import TYPE_CHECKING, Any

import yaml

from squadops.capabilities.handlers.base import (
    HandlerEvidence,
    HandlerResult,
)
from squadops.capabilities.handlers.cycle_tasks import _CycleTaskHandler
from squadops.llm.exceptions import LLMError
from squadops.llm.models import ChatMessage

if TYPE_CHECKING:
    from squadops.capabilities.handlers.context import ExecutionContext

logger = logging.getLogger(__name__)

_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)
_VALID_READINESS = {"go", "revise", "no-go"}


# ---------------------------------------------------------------------------
# Time budget awareness helpers (SIP-0082)
# ---------------------------------------------------------------------------


def _format_time_budget(seconds: int) -> str:
    """Format seconds as coarse human-readable duration for planning guidance.

    Uses hours/minutes granularity; sub-minute remainders are dropped.
    """
    if seconds < 60:
        return f"{seconds} second{'s' if seconds != 1 else ''}"
    hours, remainder = divmod(seconds, 3600)
    minutes = remainder // 60
    parts: list[str] = []
    if hours:
        parts.append(f"{hours} hour{'s' if hours != 1 else ''}")
    if minutes:
        parts.append(f"{minutes} minute{'s' if minutes != 1 else ''}")
    return " ".join(parts)


def _build_time_budget_section(time_budget_seconds: int | None) -> str:
    """Build time budget prompt section for initial planning handlers."""
    if not time_budget_seconds or time_budget_seconds <= 0:
        return ""
    formatted = _format_time_budget(time_budget_seconds)
    return (
        f"\n\n## Time Budget\n\n"
        f"This cycle has a **{formatted}** time budget ({time_budget_seconds}s). "
        f"Scope only what can reasonably be planned and executed within this window. "
        f"Prefer a smaller executable plan over a broader incomplete plan. "
        f"Explicitly defer out-of-budget work."
    )


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


class _PlanningTaskHandler(_CycleTaskHandler):
    """Base class for planning and refinement task handlers.

    Overrides ``handle()`` to use ``prompt_service.assemble()`` with
    ``task_type=self._capability_id``, activating the task_type prompt
    fragment layer (SIP-0057). Standard ``_CycleTaskHandler`` calls
    ``get_system_prompt(role)`` which omits the task_type layer.

    Subclasses set ``_handler_name``, ``_capability_id``, ``_role``,
    and ``_artifact_name``.
    """

    _request_template_id = "request.planning_task_base"

    def _build_render_variables(
        self,
        prd: str,
        prior_outputs: dict[str, Any] | None,
        inputs: dict[str, Any],
    ) -> dict[str, str]:
        """Build template variables with optional time budget section."""
        raw_budget = inputs.get("resolved_config", {}).get("time_budget_seconds")
        time_budget_seconds = int(raw_budget) if raw_budget is not None else None
        budget_section = _build_time_budget_section(time_budget_seconds)

        variables: dict[str, str] = {
            "prd": prd,
            "role": self._role,
            "prior_outputs": self._format_prior_outputs(prior_outputs),
        }
        if budget_section:
            variables["time_budget_section"] = budget_section
        return variables

    def _build_user_prompt(
        self,
        prd: str,
        prior_outputs: dict[str, Any] | None,
        time_budget_seconds: int | None = None,
    ) -> str:
        """Assemble user prompt with optional time budget awareness (SIP-0082)."""
        parts = [f"## Product Requirements Document\n\n{prd}"]
        budget_section = _build_time_budget_section(time_budget_seconds)
        if budget_section:
            parts.append(budget_section)
        if prior_outputs:
            parts.append("\n\n## Prior Analysis from Upstream Roles\n")
            for role, summary in prior_outputs.items():
                parts.append(f"### {role}\n{summary}\n")
        parts.append(f"\nPlease provide your {self._role} analysis and deliverables.")
        return "\n".join(parts)

    async def handle(
        self,
        context: ExecutionContext,
        inputs: dict[str, Any],
    ) -> HandlerResult:
        start_time = time.perf_counter()

        prd = inputs.get("prd", "")
        prior_outputs = inputs.get("prior_outputs")
        raw_budget = inputs.get("resolved_config", {}).get("time_budget_seconds")
        time_budget_seconds = int(raw_budget) if raw_budget is not None else None

        # SIP-0084: dual-path — use request renderer when available
        renderer = getattr(context.ports, "request_renderer", None)
        if renderer is not None:
            variables = self._build_render_variables(prd, prior_outputs, inputs)
            rendered = await renderer.render(self._request_template_id, variables)
            user_prompt = rendered.content
        else:
            user_prompt = self._build_user_prompt(prd, prior_outputs, time_budget_seconds)

        # Key difference: assemble with task_type to activate task_type layer
        assembled = context.ports.prompt_service.assemble(
            role=self._role,
            hook="agent_start",
            task_type=self._capability_id,
        )
        system_prompt = assembled.content

        messages = [
            ChatMessage(role="system", content=system_prompt),
            ChatMessage(role="user", content=user_prompt),
        ]

        chat_kwargs = self._build_chat_kwargs(inputs)

        try:
            response = await context.ports.llm.chat(messages, **chat_kwargs)
        except LLMError as exc:
            logger.warning(
                "LLM call failed for %s: %s",
                self._handler_name,
                exc,
            )
            duration_ms = (time.perf_counter() - start_time) * 1000
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
                error=str(exc),
            )

        content = response.content
        llm_duration_ms = (time.perf_counter() - start_time) * 1000

        # Record LLM generation for LangFuse tracing (SIP-0061 Option B)
        llm_obs = getattr(context.ports, "llm_observability", None)
        if llm_obs and context.correlation_context:
            import uuid

            from squadops.telemetry.models import (
                MAX_OBSERVABILITY_TEXT_LENGTH,
                GenerationRecord,
                PromptLayer,
                PromptLayerMetadata,
            )

            resolved_model = chat_kwargs.get("model", context.ports.llm.default_model)
            gen_record = GenerationRecord(
                generation_id=str(uuid.uuid4()),
                model=resolved_model,
                prompt_text=user_prompt[:MAX_OBSERVABILITY_TEXT_LENGTH],
                response_text=content[:MAX_OBSERVABILITY_TEXT_LENGTH],
                latency_ms=llm_duration_ms,
            )
            layers = PromptLayerMetadata(
                prompt_layer_set_id=f"{self._role}-planning",
                layers=(
                    PromptLayer(
                        layer_type="system",
                        layer_id=f"{self._role}-planning-system",
                    ),
                    PromptLayer(
                        layer_type="user",
                        layer_id=f"planning-{self._capability_id}",
                    ),
                ),
            )
            llm_obs.record_generation(context.correlation_context, gen_record, layers)

        prd_summary = str(prd)[:80] if prd else "(no PRD)"

        outputs = {
            "summary": f"[{self._role}] {prd_summary}",
            "role": self._role,
            "artifacts": [
                {
                    "name": self._artifact_name,
                    "content": content,
                    "media_type": "text/markdown",
                    "type": "document",
                },
            ],
        }

        duration_ms = (time.perf_counter() - start_time) * 1000

        evidence = HandlerEvidence.create(
            handler_name=self._handler_name,
            capability_id=self._capability_id,
            duration_ms=duration_ms,
            inputs_hash=self._hash_dict(inputs),
            outputs_hash=self._hash_dict(outputs),
        )

        return HandlerResult(
            success=True,
            outputs=outputs,
            _evidence=evidence,
        )


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


class QADefineTestStrategyHandler(_PlanningTaskHandler):
    """Planning handler: acceptance checklist, test strategy, defect severity rubric."""

    _handler_name = "qa_define_test_strategy_handler"
    _capability_id = "qa.define_test_strategy"
    _role = "qa"
    _artifact_name = "test_strategy.md"


class GovernanceAssessReadinessHandler(_PlanningTaskHandler):
    """Planning handler: consolidate outputs, design sufficiency check, readiness.

    Produces the canonical ``planning_artifact.md`` — a reconstituted document
    that synthesizes all upstream planning outputs into a coherent plan with
    YAML frontmatter containing readiness recommendation and sufficiency score.

    Performs lightweight post-generation validation on the artifact content:
    - YAML frontmatter exists (``---`` delimiters)
    - ``readiness`` field is one of ``go``, ``revise``, ``no-go``
    - ``sufficiency_score`` is an integer 0–5
    """

    _handler_name = "governance_assess_readiness_handler"
    _capability_id = "governance.assess_readiness"
    _role = "lead"
    _artifact_name = "planning_artifact.md"

    _DEFAULT_FRONTMATTER = "---\nreadiness: revise\nsufficiency_score: 3\nblocker_unknowns: 0\n---\n\n"

    def _synthesize_frontmatter(self, content: str) -> str:
        """Prepend default frontmatter when LLM omits it."""
        logger.warning(
            "assess_readiness: LLM omitted YAML frontmatter — "
            "synthesizing default (readiness=revise, score=3)"
        )
        return self._DEFAULT_FRONTMATTER + content

    async def handle(
        self,
        context: ExecutionContext,
        inputs: dict[str, Any],
    ) -> HandlerResult:
        result = await super().handle(context, inputs)
        if not result.success:
            return result

        content = result.outputs["artifacts"][0]["content"]

        # Structural validation: YAML frontmatter
        m = _FRONTMATTER_RE.match(content)
        if not m:
            # Graceful degradation: synthesize default frontmatter so the
            # cycle can proceed.  The default readiness=revise ensures the
            # plan is flagged for review rather than silently accepted.
            content = self._synthesize_frontmatter(content)
            result.outputs["artifacts"][0]["content"] = content
            m = _FRONTMATTER_RE.match(content)

        try:
            fm = yaml.safe_load(m.group(1))
        except yaml.YAMLError as exc:
            return HandlerResult(
                success=False,
                outputs={},
                _evidence=result._evidence,
                error=f"Planning artifact has invalid YAML frontmatter: {exc}",
            )

        if not isinstance(fm, dict):
            return HandlerResult(
                success=False,
                outputs={},
                _evidence=result._evidence,
                error="Planning artifact YAML frontmatter is not a mapping",
            )

        # Validate readiness field — default to "revise" if missing/invalid
        readiness = fm.get("readiness")
        if readiness not in _VALID_READINESS:
            logger.warning(
                "assess_readiness: frontmatter readiness=%r invalid, defaulting to 'revise'",
                readiness,
            )
            fm["readiness"] = "revise"

        # Validate sufficiency_score — default to 3 if missing/invalid
        try:
            score = int(fm.get("sufficiency_score", 3))
            if not (0 <= score <= 5):
                raise ValueError
        except (TypeError, ValueError):
            logger.warning(
                "assess_readiness: frontmatter sufficiency_score=%r invalid, defaulting to 3",
                fm.get("sufficiency_score"),
            )
            score = 3

        return result


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
