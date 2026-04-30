"""Framing task handlers — LLM-powered handlers for the framing workload pipeline.

5 framing handlers and 2 refinement handlers whose capability_ids match
the pinned task_type values from FRAMING_TASK_STEPS and REFINEMENT_TASK_STEPS
(SIP-0078 §5.3, §5.10). The module filename remains ``planning_tasks.py`` as
a legacy identifier; imports across the codebase pin to that name.

All framing/refinement handlers extend ``_PlanningTaskHandler``, which
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
        rendered = None
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
            response = await context.ports.llm.chat_stream_with_usage(messages, **chat_kwargs)
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
                prompt_name=rendered.template_id if rendered else None,
                prompt_version=(
                    int(rendered.template_version)
                    if rendered and rendered.template_version
                    else None
                ),
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

        # SIP-0084 §10: build prompt provenance for artifact traceability
        provenance: dict[str, Any] = {
            "system_prompt_bundle_hash": assembled.assembly_hash,
        }
        if renderer is not None and rendered is not None:
            provenance["request_template_id"] = rendered.template_id
            provenance["request_template_version"] = rendered.template_version
            provenance["request_render_hash"] = rendered.render_hash
            provenance["prompt_environment"] = "production"

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
            "prompt_provenance": provenance,
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

    _DEFAULT_FRONTMATTER = (
        "---\nreadiness: revise\nsufficiency_score: 3\nblocker_unknowns: 0\n---\n\n"
    )

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

        # SIP-0086 / SIP-0092: Produce implementation plan when enabled.
        # The plan decomposes the upcoming build into focused subtasks.
        resolved_config = inputs.get("resolved_config", {})
        if resolved_config.get("implementation_plan", False):
            manifest_artifact = await self._produce_manifest(
                context, inputs, content, resolved_config
            )
            if manifest_artifact is not None:
                result.outputs["artifacts"].append(manifest_artifact)

        return result

    async def _produce_manifest(
        self,
        context: ExecutionContext,
        inputs: dict[str, Any],
        planning_content: str,
        resolved_config: dict[str, Any],
    ) -> dict[str, Any] | None:
        """Generate build task manifest via a dedicated LLM call.

        Separate from the planning artifact generation to keep prompts focused.
        Returns manifest artifact dict or None on graceful fallback (RC-4).
        """

        from squadops.capabilities.handlers.fenced_parser import extract_fenced_files
        from squadops.llm.models import ChatMessage

        prd = inputs.get("prd", "")

        # Constrain role choices to what the active squad profile actually has.
        # Without this, small models invent plausible-sounding roles like
        # 'backend_dev' that fail profile validation at impl-time.
        profile_roles = inputs.get("profile_roles") or []
        roles_section = (
            f"Available roles (use ONLY these; do NOT invent new ones): "
            f"{', '.join(profile_roles)}\n\n"
            if profile_roles
            else ""
        )

        # Constrain task_type to the known build task_types. Without this,
        # models invent task_types like 'quality_assurance.validate' instead
        # of the canonical 'qa.test'.
        from squadops.cycles.implementation_plan import _KNOWN_BUILD_TASK_TYPES

        allowed_task_types = sorted(_KNOWN_BUILD_TASK_TYPES)
        task_types_section = (
            f"Available task_types (use ONLY these; do NOT invent new ones): "
            f"{', '.join(allowed_task_types)}\n\n"
        )

        # SIP-0086 + SIP-0071: when the squad includes a dedicated builder,
        # route assembly/packaging work to `builder.assemble` tasks so the
        # builder role is actually exercised by the convergence loop.
        has_builder = "builder" in profile_roles
        if has_builder:
            builder_guideline = (
                "- Route packaging, entrypoints, requirements.txt/package.json, "
                "Dockerfile/startup scripts, and qa_handoff.md to `builder.assemble` "
                "tasks (role: builder). Place AFTER all `development.develop` tasks "
                "and BEFORE any `qa.test` tasks.\n"
            )
            qa_handoff_guideline = ""
            builder_example = (
                "  - task_index: 1\n"
                "    task_type: builder.assemble\n"
                "    role: builder\n"
                '    focus: "Package build output and produce qa_handoff.md"\n'
                "    description: |\n"
                "      Assemble packaging (entrypoints, requirements/manifest, "
                "Dockerfile if applicable) and write qa_handoff.md summarizing "
                "how to run and test the build.\n"
                "    expected_artifacts:\n"
                '      - "qa_handoff.md"\n'
                "    acceptance_criteria:\n"
                '      - "..."\n'
                "    depends_on: [0]\n"
            )
            summary_builder_line = "  total_builder_tasks: P\n"
            total_tasks_expr = "N+M+P"
        else:
            builder_guideline = ""
            qa_handoff_guideline = "- Put QA handoff last\n"
            builder_example = ""
            summary_builder_line = ""
            total_tasks_expr = "N+M"

        manifest_prompt = (
            "Based on the following PRD and planning artifact, produce a build task "
            "manifest that decomposes the upcoming build into focused subtasks.\n\n"
            f"{roles_section}"
            f"{task_types_section}"
            f"## PRD\n{prd}\n\n"
            f"## Planning Artifact\n{planning_content}\n\n"
            "Each subtask should:\n"
            "1. Have a clear, narrow focus (e.g., 'Backend data models' not 'Build the app')\n"
            "2. List the specific files it should produce\n"
            "3. Declare dependencies on prior subtasks by task_index\n"
            "4. Define acceptance criteria\n"
            "5. Be completable in a single focused LLM generation (~2-10 minutes)\n\n"
            "Decomposition guidelines:\n"
            "- Separate backend and frontend into distinct tasks\n"
            "- Separate models/data from API endpoints/routes\n"
            "- Separate UI shell/routing from individual view components\n"
            "- Put integration config (CORS, proxy, requirements) in its own task\n"
            "- Put tests after the code they test\n"
            f"{builder_guideline}"
            f"{qa_handoff_guideline}"
            "\n"
            "Output ONLY the manifest as a YAML code block with filename tag:\n"
            "```yaml:implementation_plan.yaml\n"
            "version: 1\n"
            "project_id: <project_id>\n"
            "cycle_id: <cycle_id>\n"
            "prd_hash: <hash>\n"
            "tasks:\n"
            "  - task_index: 0\n"
            "    task_type: development.develop\n"
            "    role: dev\n"
            '    focus: "..."\n'
            "    description: |\n"
            "      ...\n"
            "    expected_artifacts:\n"
            '      - "path/to/file"\n'
            "    acceptance_criteria:\n"
            '      - "..."\n'
            "    depends_on: []\n"
            f"{builder_example}"
            "summary:\n"
            "  total_dev_tasks: N\n"
            "  total_qa_tasks: M\n"
            f"{summary_builder_line}"
            f"  total_tasks: {total_tasks_expr}\n"
            "  estimated_layers: [backend, frontend, test, config]\n"
            "```\n"
        )

        assembled = context.ports.prompt_service.get_system_prompt(self._role)
        chat_kwargs = self._build_chat_kwargs(inputs)
        min_subtasks = resolved_config.get("min_build_subtasks", 3)
        max_subtasks = resolved_config.get("max_build_subtasks", 15)

        # Retry loop: small models occasionally produce malformed YAML or
        # off-bounds manifests. Re-prompt with the specific error so the
        # model can correct itself before falling back to static steps.
        max_attempts = int(resolved_config.get("manifest_max_attempts", 2))
        messages = [
            ChatMessage(role="system", content=assembled.content),
            ChatMessage(role="user", content=manifest_prompt),
        ]

        for attempt in range(1, max_attempts + 1):
            try:
                response = await context.ports.llm.chat_stream_with_usage(messages, **chat_kwargs)
            except Exception as exc:
                logger.warning(
                    "assess_readiness: manifest LLM call failed on attempt %d/%d (%s)",
                    attempt,
                    max_attempts,
                    exc,
                )
                if attempt >= max_attempts:
                    return None
                messages = messages[:2]  # reset and try once more from scratch
                continue

            # Extract manifest YAML — prefer filename-tagged fence
            extracted = extract_fenced_files(response.content)
            manifest_files = [f for f in extracted if f["filename"] == "implementation_plan.yaml"]
            if manifest_files:
                yaml_content = manifest_files[0]["content"]
            else:
                yaml_content = self._find_manifest_yaml(response.content)

            manifest, error_msg = self._validate_manifest_candidate(
                yaml_content, min_subtasks, max_subtasks, profile_roles
            )

            if error_msg is None and manifest is not None:
                logger.info(
                    "assess_readiness: produced build task manifest with %d subtasks on attempt %d",
                    len(manifest.tasks),
                    attempt,
                )
                return {
                    "name": "implementation_plan.yaml",
                    "content": yaml_content,
                    "media_type": "text/yaml",
                    "type": "control_implementation_plan",
                }

            logger.warning(
                "assess_readiness: manifest attempt %d/%d failed (%s)",
                attempt,
                max_attempts,
                error_msg,
            )
            if attempt >= max_attempts:
                logger.warning(
                    "assess_readiness: exhausted %d manifest attempts, "
                    "falling back to static task steps",
                    max_attempts,
                )
                return None

            # Append corrective feedback for the next attempt.
            messages = [
                *messages,
                ChatMessage(role="assistant", content=response.content),
                ChatMessage(role="user", content=error_msg),
            ]

        return None

    @staticmethod
    def _validate_manifest_candidate(
        yaml_content: str | None,
        min_subtasks: int,
        max_subtasks: int,
        profile_roles: list[str],
    ) -> tuple[Any | None, str | None]:
        """Validate a candidate plan YAML. Returns (plan, error_msg).

        error_msg is None iff the plan is valid; in that case the first return
        is the parsed ImplementationPlan. The error_msg is the corrective
        feedback appended to the next LLM attempt.
        """
        from squadops.cycles.implementation_plan import ImplementationPlan

        if yaml_content is None:
            return None, (
                "Your response did not contain a fenced YAML block tagged "
                "implementation_plan.yaml. Reply with ONLY the fenced block."
            )

        try:
            manifest = ImplementationPlan.from_yaml(yaml_content)
        except ValueError as exc:
            return None, (
                f"The previous plan YAML failed validation: {exc}. "
                "Produce a corrected implementation_plan.yaml. "
                "Quote every file path; do not put parenthetical comments "
                "after quoted strings on list items."
            )

        n = len(manifest.tasks)
        if n < min_subtasks or n > max_subtasks:
            return None, (
                f"The previous manifest had {n} subtasks; bounds are "
                f"{min_subtasks}-{max_subtasks}. Produce a corrected "
                "implementation_plan.yaml within bounds."
            )

        if profile_roles:
            allowed = set(profile_roles)
            bad = sorted({t.role for t in manifest.tasks if t.role not in allowed})
            if bad:
                return None, (
                    f"The previous manifest used role(s) not in the "
                    f"squad profile: {', '.join(bad)}. "
                    f"Use ONLY these roles: {', '.join(profile_roles)}. "
                    "Produce a corrected implementation_plan.yaml."
                )

        return manifest, None

    @staticmethod
    def _find_manifest_yaml(content: str) -> str | None:
        """Search for untagged ```yaml block with manifest content."""
        import re

        for match in re.finditer(r"```yaml\s*\n(.*?)```", content, re.DOTALL):
            block = match.group(1).strip()
            if "task_index" in block and "task_type" in block and "focus" in block:
                return block
        return None


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
