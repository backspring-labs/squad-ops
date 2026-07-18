"""Framing task handlers — LLM-powered handlers for the framing workload pipeline.

5 framing handlers and 2 refinement handlers whose capability_ids match
the pinned task_type values from PLANNING_TASK_STEPS and REFINEMENT_TASK_STEPS
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
from dataclasses import replace
from typing import TYPE_CHECKING, Any

import yaml

from squadops.capabilities.handlers.base import (
    HandlerEvidence,
    HandlerResult,
)
from squadops.capabilities.handlers.cycle_tasks import (
    _CycleTaskHandler,
)
from squadops.cycles.acceptance_check_spec import render_typed_acceptance_vocabulary
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


class GovernanceReviewPlanHandler(_PlanningTaskHandler):
    """Planning sign-off (SIP-0093 PR 93.3 cutover).

    Produces ``planning_artifact.md`` — a reconstituted narrative synthesizing
    all upstream planning outputs with YAML frontmatter carrying the
    readiness recommendation and sufficiency score. After SIP-0093 PR 93.3,
    this handler is **sign-off only**: it does NOT author
    ``implementation_plan.yaml``. The merger (``governance.merge_plan``)
    runs upstream and emits the canonical plan plus ``merge_decisions.yaml``
    via the same handler chain regardless of authoring mode (multi-role or
    sole-author).

    Performs lightweight post-generation validation on the artifact content:
    - YAML frontmatter exists (``---`` delimiters)
    - ``readiness`` field is one of ``go``, ``revise``, ``no-go``
    - ``sufficiency_score`` is an integer 0–5
    """

    _handler_name = "governance_assess_readiness_handler"
    _capability_id = "governance.review_plan"
    _role = "lead"
    _artifact_name = "planning_artifact.md"

    async def _retry_without_frontmatter(
        self,
        context: ExecutionContext,
        inputs: dict[str, Any],
        prior_content: str,
    ) -> str | None:
        """Re-prompt Max once with a corrective instruction.

        Returns the new artifact content if the retry produced any
        response, else ``None`` so the caller can fail the task. The
        caller still validates frontmatter on the result, so a retry
        that comes back empty or still missing frontmatter terminates
        the task.
        """
        prd = inputs.get("prd", "")
        prior_outputs = inputs.get("prior_outputs")
        raw_budget = inputs.get("resolved_config", {}).get("time_budget_seconds")
        time_budget_seconds = int(raw_budget) if raw_budget is not None else None

        renderer = getattr(context.ports, "request_renderer", None)
        if renderer is not None:
            variables = self._build_render_variables(prd, prior_outputs, inputs)
            rendered = await renderer.render(self._request_template_id, variables)
            user_prompt = rendered.content
        else:
            user_prompt = self._build_user_prompt(prd, prior_outputs, time_budget_seconds)

        assembled = context.ports.prompt_service.assemble(
            role=self._role,
            hook="agent_start",
            task_type=self._capability_id,
        )

        messages = [
            ChatMessage(role="system", content=assembled.content),
            ChatMessage(role="user", content=user_prompt),
            ChatMessage(role="assistant", content=prior_content),
            ChatMessage(role="user", content=self._FRONTMATTER_RETRY_INSTRUCTION),
        ]
        chat_kwargs = self._build_chat_kwargs(inputs)

        try:
            response = await context.ports.llm.chat_stream_with_usage(messages, **chat_kwargs)
        except LLMError as exc:
            logger.warning("assess_readiness: frontmatter-retry LLM call failed: %s", exc)
            return None

        return response.content if response and response.content else None

    _FRONTMATTER_RETRY_INSTRUCTION = (
        "Your previous response did not include the required YAML frontmatter. "
        "The planning artifact MUST start with a `---` delimited block "
        "containing `readiness` (one of `go`, `revise`, `no-go`) and "
        "`sufficiency_score` (integer 0–5), followed by `---` and the body. "
        "Re-emit the full planning artifact, starting with the frontmatter."
    )

    async def handle(
        self,
        context: ExecutionContext,
        inputs: dict[str, Any],
    ) -> HandlerResult:
        result = await super().handle(context, inputs)
        if not result.success:
            return result

        content = result.outputs["artifacts"][0]["content"]

        # Structural validation: YAML frontmatter must be authored by the
        # LLM. Issue #109: we used to silently synthesize a default
        # `readiness=revise / sufficiency_score=3` block when frontmatter
        # was missing, which made it look like Max had reviewed the plan
        # when in fact every downstream consumer was reading defaults.
        # Now: retry once with a corrective prompt; if the retry still
        # omits frontmatter, fail the task so the cycle's correction
        # loop can fire instead of papering over it.
        m = _FRONTMATTER_RE.match(content)
        if not m:
            retry_content = await self._retry_without_frontmatter(context, inputs, content)
            if retry_content is not None:
                content = retry_content
                # #155: `result` is a frozen HandlerResult. Rebuild it with the
                # retry content instead of mutating its nested `outputs` dict in
                # place — `frozen=True` does not freeze nested containers, and the
                # original result may be shared/cached/retried elsewhere.
                artifacts = result.outputs["artifacts"]
                new_artifacts = [{**artifacts[0], "content": content}, *artifacts[1:]]
                new_outputs = {**result.outputs, "artifacts": new_artifacts}
                result = replace(result, outputs=new_outputs)
                m = _FRONTMATTER_RE.match(content)

            if not m:
                logger.warning(
                    "assess_readiness: LLM omitted YAML frontmatter on initial "
                    "response and retry; failing task to surface the gap"
                )
                return HandlerResult(
                    success=False,
                    outputs={},
                    _evidence=result._evidence,
                    error=(
                        "Planning artifact missing required YAML frontmatter "
                        "(readiness, sufficiency_score) after one corrective retry"
                    ),
                )

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

        # SIP-0093 PR 93.3 cutover: implementation_plan.yaml is no longer
        # produced here. The merger (governance.merge_plan) runs upstream
        # and emits the canonical plan + merge_decisions.yaml. This handler
        # is sign-off only — it consumes the consolidated planning artifact
        # and adds the readiness recommendation.
        #
        # The merger's artifacts already live in the cycle's artifact
        # stream; PR 93.4 surfaces them in the gate package primary view.
        return result


_BRIEF_MAX_ATTEMPTS_DEFAULT = 2


class GovernancePreparePlanAuthoringBriefHandler(_PlanningTaskHandler):
    """SIP-0093 PR 93.0: produce ``plan_authoring_brief.yaml``.

    The brief pins stack, scope, requirements, scope cuts, and risk areas
    before plan-authoring fan-out so role proposers operate from one shared
    frame. The merger consumes it (RC-22 immutability) regardless of whether
    proposers ran or sole-author mode kicks in.

    Runs an LLM call with up to ``brief_max_attempts`` retries; each attempt's
    raw response is fence-stripped via ``retry_yaml_call`` before
    ``PlanAuthoringBrief.from_yaml`` validates it. Mirrors the proposer
    handlers in this module.
    """

    _handler_name = "governance_prepare_plan_authoring_brief_handler"
    _capability_id = "governance.prepare_plan_authoring_brief"
    _role = "lead"
    _artifact_name = "plan_authoring_brief.yaml"

    async def handle(
        self,
        context: ExecutionContext,
        inputs: dict[str, Any],
    ) -> HandlerResult:
        from squadops.capabilities.handlers._plan_authoring import retry_yaml_call
        from squadops.cycles.plan_authoring_brief import PlanAuthoringBrief

        start_time = time.perf_counter()

        prd = inputs.get("prd", "")
        prior_outputs = inputs.get("prior_outputs")
        resolved_config = inputs.get("resolved_config", {})
        raw_budget = resolved_config.get("time_budget_seconds")
        time_budget_seconds = int(raw_budget) if raw_budget is not None else None

        renderer = getattr(context.ports, "request_renderer", None)
        if renderer is not None:
            variables = self._build_render_variables(prd, prior_outputs, inputs)
            rendered = await renderer.render(self._request_template_id, variables)
            user_prompt = rendered.content
        else:
            user_prompt = self._build_user_prompt(prd, prior_outputs, time_budget_seconds)

        assembled = context.ports.prompt_service.assemble(
            role=self._role,
            hook="agent_start",
            task_type=self._capability_id,
        )
        system_prompt = assembled.content

        max_attempts = int(resolved_config.get("brief_max_attempts", _BRIEF_MAX_ATTEMPTS_DEFAULT))
        chat_kwargs = self._build_chat_kwargs(inputs)

        def parse_and_validate(
            yaml_or_none: str | None,
        ) -> tuple[Any | None, str | None]:
            if yaml_or_none is None:
                return None, (
                    "No YAML brief found. Emit your output as a fenced block: "
                    "```yaml:plan_authoring_brief.yaml ... ``` (or ```yaml ... ```)."
                )
            try:
                brief = PlanAuthoringBrief.from_yaml(yaml_or_none)
            except ValueError as exc:
                return None, f"plan_authoring_brief.yaml failed to parse: {exc}"
            return brief, None

        parsed, last_yaml, last_error = await retry_yaml_call(
            llm=context.ports.llm,
            chat_kwargs=chat_kwargs,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            parse_and_validate=parse_and_validate,
            max_attempts=max_attempts,
            handler_name=self._handler_name,
        )

        duration_ms = (time.perf_counter() - start_time) * 1000

        if parsed is None:
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
                    f"plan_authoring_brief.yaml failed to parse: "
                    f"{last_error or 'exhausted retry budget without parseable output'}"
                ),
            )

        # ``last_yaml`` is the fence-extracted body; persist that as the
        # artifact content so downstream callers (merger, gate package) get
        # raw YAML without code-fence wrappers.
        assert last_yaml is not None  # invariant: parsed is not None → yaml was extracted
        outputs = {
            "summary": f"[{self._role}] plan_authoring_brief produced",
            "role": self._role,
            "artifacts": [
                {
                    "name": self._artifact_name,
                    "content": last_yaml,
                    "media_type": "text/yaml",
                    "type": "plan_authoring_brief",
                },
            ],
            # PR 93.3 wire: surface the brief YAML in a non-artifacts key so
            # the merger can consume it from prior_outputs["lead"]["brief_outcome"].
            # The executor's prior_outputs builder strips "artifacts" by design.
            "brief_outcome": {
                "status": "success",
                "yaml_content": last_yaml,
                "artifact_name": self._artifact_name,
            },
        }
        evidence = HandlerEvidence.create(
            handler_name=self._handler_name,
            capability_id=self._capability_id,
            duration_ms=duration_ms,
            inputs_hash=self._hash_dict(inputs),
            outputs_hash=self._hash_dict(outputs),
        )
        return HandlerResult(success=True, outputs=outputs, _evidence=evidence)


# ---------------------------------------------------------------------------
# 3 Proposer handlers (SIP-0093 PR 93.2)
#
# Three handlers that contribute domain-scoped plan-authoring artifacts:
# development.propose_plan_tasks, qa.propose_plan_tasks, and
# strategy.propose_plan_guidance. Registered but NOT wired into
# PLANNING_TASK_STEPS — cutover happens in PR 93.3. The handlers are
# reachable via direct dispatch and in tests until then.
#
# Each handler:
#   1. Reads plan_authoring_brief.yaml from prior_outputs["artifact_contents"]
#      (RC-22: brief is immutable upstream context).
#   2. Renders its user prompt from a registered template that surfaces the
#      brief content, planning_content, proposal_id, source_brief_id.
#   3. Assembles its system prompt via prompt_service.assemble(..., task_type=
#      self._capability_id) — task-type fragments live in
#      src/squadops/prompts/fragments/shared/task_type/.
#   4. Runs retry_yaml_call (SIP-0093 _plan_authoring helper) for up to
#      manifest_max_attempts attempts with corrective feedback on each
#      parse failure.
#   5. Enforces source_brief_id matching the upstream brief's brief_id.
#   6. On success: emits the parseable artifact (proposed_plan_tasks.yaml or
#      plan_guidance.yaml).
#   7. On exhausted failure: emits a ProposalFailure artifact (RC-23) rather
#      than an exception that kills the cycle. The merger (PR 93.3) reads
#      these as "this role's proposal is missing."
# ---------------------------------------------------------------------------


_PROPOSAL_MAX_ATTEMPTS_DEFAULT = 2


def _extract_brief_id_from_prior_outputs(prior_outputs: dict[str, Any] | None) -> str | None:
    """Pull the upstream brief_id out of a pre-resolved artifact-contents map.

    The pipeline pre-resolver (wired by PR 93.3 cutover) puts the brief's
    YAML content into ``prior_outputs["artifact_contents"]["plan_authoring_brief.yaml"]``.
    Returns ``None`` if the brief isn't in prior_outputs (caller decides
    whether that's a hard failure or an empty-context proposer call).
    """
    if not prior_outputs:
        return None
    contents = prior_outputs.get("artifact_contents")
    if not isinstance(contents, dict):
        return None
    brief_yaml = contents.get("plan_authoring_brief.yaml")
    if not brief_yaml:
        return None
    try:
        from squadops.cycles.plan_authoring_brief import PlanAuthoringBrief

        return PlanAuthoringBrief.from_yaml(brief_yaml).brief_id
    except ValueError:
        return None


def _format_planning_content(prior_outputs: dict[str, Any] | None) -> str:
    """Concatenate non-brief planning artifacts for the user-prompt context.

    Filters out the brief itself (surfaced separately as ``brief_content``)
    and the artifact_contents key. Renders remaining role outputs as
    Markdown sections so the proposer sees the framing artifacts as a
    single narrative.
    """
    if not prior_outputs:
        return "(no upstream framing artifacts)"
    parts: list[str] = []

    contents = prior_outputs.get("artifact_contents")
    if isinstance(contents, dict):
        for name, content in contents.items():
            if name == "plan_authoring_brief.yaml":
                continue
            parts.append(f"### {name}\n{content}")

    for key, value in prior_outputs.items():
        if key in ("artifact_contents",):
            continue
        if isinstance(value, dict) and "summary" in value:
            parts.append(f"### {key}\n{value['summary']}")

    return "\n\n".join(parts) if parts else "(no upstream framing artifacts)"


class _ProposeBaseHandler(_PlanningTaskHandler):
    """Shared shape for the three SIP-0093 proposer handlers.

    Subclasses pin ``_capability_id``, ``_role``, ``_request_template_id``,
    ``_proposer_role`` (the value that appears in ``proposing_role`` of the
    parsed artifact), and implement ``_parse_and_validate``. The base
    drives the retry loop, surfaces the parsed artifact on success, and
    emits a ``ProposalFailure`` artifact on exhaustion (RC-23).
    """

    _success_artifact_name: str = ""  # subclasses override
    _success_artifact_type: str = ""  # subclasses override
    _proposer_role: str = ""  # subclasses override — appears as proposing_role in YAML

    def _failure_artifact_name(self) -> str:
        # capability_id with dots → underscores, plus _failure.yaml — a
        # filename the merger can pattern-match without parsing.
        return self._capability_id.replace(".", "_") + "_failure.yaml"

    def _parse_and_validate(
        self,
        yaml_content: str | None,
        expected_brief_id: str | None,
    ) -> tuple[Any | None, str | None]:
        """Subclass-specific parse + validate.

        Returns ``(parsed_obj, error_msg)``. ``error_msg is None`` means
        accept; otherwise the message becomes corrective feedback for the
        next retry attempt.
        """
        raise NotImplementedError

    def _build_render_variables(
        self,
        prd: str,
        prior_outputs: dict[str, Any] | None,
        inputs: dict[str, Any],
    ) -> dict[str, str]:
        import uuid

        brief_content = "(brief not yet provided — direct-invocation context)"
        if prior_outputs:
            contents = prior_outputs.get("artifact_contents")
            if isinstance(contents, dict):
                brief_content = contents.get("plan_authoring_brief.yaml", brief_content)

        brief_id = _extract_brief_id_from_prior_outputs(prior_outputs) or "(unknown)"
        proposal_id = inputs.get("proposal_id") or f"prop-{uuid.uuid4().hex[:8]}"

        profile_roles = inputs.get("profile_roles") or []
        roles_section = ""
        if profile_roles:
            roles_section = f"## Available roles in this squad\n\n{', '.join(profile_roles)}\n\n"

        builder_section = ""
        if "builder" in profile_roles and self._role != "builder":
            builder_section = (
                "## Builder role present\n\n"
                "This squad includes a dedicated builder role. Do NOT propose "
                "packaging, requirements files, Dockerfile, startup scripts, "
                "or qa_handoff.md tasks — those are the builder's domain. "
                "Reference builder tasks via ``depends_on_focus`` if your "
                "tasks need their outputs.\n\n"
            )

        return {
            "brief_content": brief_content,
            "planning_content": _format_planning_content(prior_outputs),
            "proposal_id": proposal_id,
            "source_brief_id": brief_id,
            "prd": prd,
            "roles_section": roles_section,
            "builder_section": builder_section,
            # Generated from CHECK_SPECS so the proposer sees exact param names
            # + a parser-valid example per check (issue #182 — was "", which let
            # models guess param names and fail count_at_least validation).
            "typed_acceptance_vocabulary": render_typed_acceptance_vocabulary(),
        }

    async def _scaffold_section(self, renderer: Any, inputs: dict[str, Any]) -> str:
        """The interface-manifest instruction, or "" (SIP-0099 99.2 Slice B).

        Non-empty ONLY for the dev proposer on a scaffoldable stack — dev owns the
        interface section, and a non-scaffoldable cycle must not be asked to emit a
        manifest that plan validation would reject. The instruction text lives in a
        managed prompt asset (``request.development_interface_manifest_appendix``), not
        inline here (CLAUDE.md #448)."""
        from squadops.capabilities.scaffold import is_scaffoldable_stack

        if self._proposer_role != "development":
            return ""
        resolved_config = inputs.get("resolved_config") or {}
        stack = str(resolved_config.get("build_profile") or "")
        if not is_scaffoldable_stack(stack):
            return ""
        rendered = await renderer.render(
            "request.development_interface_manifest_appendix", {"stack": stack}
        )
        return rendered.content

    async def _bind_criteria_section(self, renderer: Any, inputs: dict[str, Any]) -> str:
        """The *bind, don't author* instruction + contract criteria index, or ""
        (SIP-0098 98.3).

        Non-empty ONLY in bind mode — a contract is seeded, so the executor injected
        ``contract_criteria_index`` into this proposer's inputs — and only for the dev/qa
        proposers that author build tasks (strategy proposes guidance, not tasks). The
        instruction prose lives in a managed asset (``request.plan_bind_criteria_appendix``);
        only the index *data* is a variable (CLAUDE.md #448). Absent contract → "" →
        today's author-mode proposer prompt exactly."""
        if self._proposer_role not in ("development", "qa"):
            return ""
        index = inputs.get("contract_criteria_index")
        if not index:
            return ""
        rendered = await renderer.render(
            "request.plan_bind_criteria_appendix", {"criteria_index": index}
        )
        return rendered.content

    async def handle(
        self,
        context: ExecutionContext,
        inputs: dict[str, Any],
    ) -> HandlerResult:
        from squadops.capabilities.handlers._plan_authoring import (
            extract_interface_manifest_yaml,
            retry_yaml_call,
        )

        start_time = time.perf_counter()

        prd = inputs.get("prd", "")
        prior_outputs = inputs.get("prior_outputs")
        resolved_config = inputs.get("resolved_config", {})
        expected_brief_id = _extract_brief_id_from_prior_outputs(prior_outputs)

        # Render user prompt via the registered template (SIP-0084).
        renderer = getattr(context.ports, "request_renderer", None)
        if renderer is None:
            # No renderer in test contexts: emit a structured failure rather
            # than constructing an inline duplicate. This handler family is
            # new (PR 93.2) — tests inject a renderer mock, no migration
            # baggage to accommodate.
            return self._build_failure_result(
                start_time,
                inputs,
                "llm_error",
                f"{self._handler_name} requires request_renderer port",
            )

        variables = self._build_render_variables(prd, prior_outputs, inputs)
        # SIP-0099 99.2 (Slice B): on a scaffoldable stack, the dev proposer is asked to
        # ALSO author an interface manifest. Data-driven — a non-scaffoldable cycle gets
        # "" and stays on today's path — and the instruction lives in a managed prompt
        # asset, not an inline literal (CLAUDE.md #448). Only set when non-empty so qa/
        # strategy renders don't log an unknown-variable warning.
        scaffold_section = await self._scaffold_section(renderer, inputs)
        if scaffold_section:
            variables["scaffold_section"] = scaffold_section
        # SIP-0098 98.3: in bind mode the dev/qa proposer is told to bind the contract's
        # covered-file criteria by id (not author them). Data-driven — only set when the
        # executor injected the criteria index (contract seeded) — and the instruction is
        # a managed asset, not an inline literal (#448). Only set when non-empty so a
        # non-bind render doesn't warn on an unknown variable.
        bind_criteria_section = await self._bind_criteria_section(renderer, inputs)
        if bind_criteria_section:
            variables["bind_criteria_section"] = bind_criteria_section
        rendered = await renderer.render(self._request_template_id, variables)
        user_prompt = rendered.content

        assembled = context.ports.prompt_service.assemble(
            role=self._role,
            hook="agent_start",
            task_type=self._capability_id,
        )
        system_prompt = assembled.content

        max_attempts = int(
            resolved_config.get("proposal_max_attempts", _PROPOSAL_MAX_ATTEMPTS_DEFAULT)
        )
        chat_kwargs = self._build_chat_kwargs(inputs)

        def parse_and_validate(yaml_or_none: str | None) -> tuple[Any | None, str | None]:
            return self._parse_and_validate(yaml_or_none, expected_brief_id)

        captured: dict[str, str] = {}

        def _capture_content(content: str) -> None:
            captured["content"] = content

        parsed, last_yaml, last_error = await retry_yaml_call(
            llm=context.ports.llm,
            chat_kwargs=chat_kwargs,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            parse_and_validate=parse_and_validate,
            max_attempts=max_attempts,
            handler_name=self._handler_name,
            on_success_content=_capture_content,
        )

        if parsed is None:
            failure_reason = self._classify_failure(last_error, last_yaml)
            return self._build_failure_result(
                start_time,
                inputs,
                failure_reason,
                last_error or "exhausted retry budget without parseable output",
            )

        # SIP-0099 99.2: a framing proposer may emit interface_manifest.yaml alongside
        # its proposed_plan_tasks.yaml; carry the raw block for the merger (data-driven —
        # absent = today's behavior).
        interface_manifest_yaml = extract_interface_manifest_yaml(captured.get("content", ""))
        return self._build_success_result(
            start_time, inputs, last_yaml or "", interface_manifest_yaml
        )

    def _classify_failure(self, last_error: str | None, last_yaml: str | None) -> str:
        """Map the retry loop's last error to a ProposalFailure failure_reason."""
        if not last_error:
            return "malformed_yaml" if not last_yaml else "schema_validation_error"
        lowered = last_error.lower()
        if "brief" in lowered and "mismatch" in lowered:
            return "mismatched_brief_id"
        if "malformed" in lowered or "yaml" in lowered:
            return "malformed_yaml"
        if last_yaml is None:
            return "malformed_yaml"
        return "schema_validation_error"

    def _build_success_result(
        self,
        start_time: float,
        inputs: dict[str, Any],
        yaml_content: str,
        interface_manifest_yaml: str | None = None,
    ) -> HandlerResult:
        # The merger consumes this via prior_outputs (PR 93.3). The cycle
        # executor strips "artifacts" from prior_outputs by design, so we
        # surface the YAML content under a non-artifacts key the merger
        # reads by role.
        proposal_outcome: dict[str, Any] = {
            "status": "success",
            "proposing_role": self._proposer_role,
            "yaml_content": yaml_content,
            "artifact_name": self._success_artifact_name,
        }
        # SIP-0099 99.2: carry the raw interface manifest for the merger, only when the
        # proposer emitted one (no key = no interface manifest = today's behavior).
        if interface_manifest_yaml:
            proposal_outcome["interface_manifest_yaml"] = interface_manifest_yaml
        outputs = {
            "summary": f"[{self._role}] proposal produced for {self._capability_id}",
            "role": self._role,
            "artifacts": [
                {
                    "name": self._success_artifact_name,
                    "content": yaml_content,
                    "media_type": "text/yaml",
                    "type": self._success_artifact_type,
                },
            ],
            "proposal_outcome": proposal_outcome,
        }
        duration_ms = (time.perf_counter() - start_time) * 1000
        evidence = HandlerEvidence.create(
            handler_name=self._handler_name,
            capability_id=self._capability_id,
            duration_ms=duration_ms,
            inputs_hash=self._hash_dict(inputs),
            outputs_hash=self._hash_dict(outputs),
        )
        return HandlerResult(success=True, outputs=outputs, _evidence=evidence)

    def _build_failure_result(
        self,
        start_time: float,
        inputs: dict[str, Any],
        failure_reason: str,
        details: str,
    ) -> HandlerResult:
        """Emit a ProposalFailure artifact (RC-23) — the cycle continues.

        Returns ``HandlerResult(success=True, ...)`` so the cycle pipeline
        keeps moving and the merger gets a chance to read this artifact.
        The "failure" is captured inside the artifact, not at the
        HandlerResult layer.
        """
        from squadops.cycles.proposal_failure import ProposalFailure

        failure = ProposalFailure(
            proposer_role=self._proposer_role,
            failure_reason=failure_reason,
            details=details,
        )
        failure_yaml = failure.to_yaml()
        outputs = {
            "summary": (
                f"[{self._role}] proposal failed ({failure_reason}) — "
                f"failure record emitted for merger"
            ),
            "role": self._role,
            "artifacts": [
                {
                    "name": self._failure_artifact_name(),
                    "content": failure_yaml,
                    "media_type": "text/yaml",
                    "type": "proposal_failure",
                },
            ],
            # PR 93.3 wire: the merger reads this from prior_outputs by role.
            "proposal_outcome": {
                "status": "failure",
                "proposing_role": self._proposer_role,
                "yaml_content": failure_yaml,
                "artifact_name": self._failure_artifact_name(),
                "failure_reason": failure_reason,
            },
        }
        duration_ms = (time.perf_counter() - start_time) * 1000
        evidence = HandlerEvidence.create(
            handler_name=self._handler_name,
            capability_id=self._capability_id,
            duration_ms=duration_ms,
            inputs_hash=self._hash_dict(inputs),
            outputs_hash=self._hash_dict(outputs),
        )
        return HandlerResult(success=True, outputs=outputs, _evidence=evidence)


class DevelopmentProposePlanTasksHandler(_ProposeBaseHandler):
    """SIP-0093 PR 93.2: development-domain plan-task proposer."""

    _handler_name = "development_propose_plan_tasks_handler"
    _capability_id = "development.propose_plan_tasks"
    _role = "dev"
    _request_template_id = "request.development_propose_plan_tasks"
    _success_artifact_name = "proposed_plan_tasks.yaml"
    _success_artifact_type = "proposed_plan_tasks"
    _proposer_role = "development"

    def _parse_and_validate(
        self,
        yaml_content: str | None,
        expected_brief_id: str | None,
    ) -> tuple[Any | None, str | None]:
        from squadops.cycles.proposed_role_tasks import ProposedRoleTasks

        if yaml_content is None:
            return (
                None,
                "No fenced YAML block found. Emit your proposal in a ```yaml:proposed_plan_tasks.yaml``` block.",
            )
        try:
            proposal = ProposedRoleTasks.from_yaml(yaml_content)
        except ValueError as exc:
            return None, f"proposed_plan_tasks.yaml failed to parse: {exc}"
        if expected_brief_id and proposal.source_brief_id != expected_brief_id:
            return None, (
                f"brief_id mismatch: proposal cites {proposal.source_brief_id!r}, "
                f"upstream brief is {expected_brief_id!r}. Use the upstream brief_id verbatim."
            )
        if proposal.proposing_role not in ("development", "dev"):
            return None, (
                f"proposing_role must be 'development' for this handler, "
                f"got {proposal.proposing_role!r}"
            )
        return proposal, None


class QaProposePlanTasksHandler(_ProposeBaseHandler):
    """SIP-0093 PR 93.2: qa-domain plan-task proposer."""

    _handler_name = "qa_propose_plan_tasks_handler"
    _capability_id = "qa.propose_plan_tasks"
    _role = "qa"
    _request_template_id = "request.qa_propose_plan_tasks"
    _success_artifact_name = "proposed_plan_tasks.yaml"
    _success_artifact_type = "proposed_plan_tasks"
    _proposer_role = "qa"

    def _parse_and_validate(
        self,
        yaml_content: str | None,
        expected_brief_id: str | None,
    ) -> tuple[Any | None, str | None]:
        from squadops.cycles.proposed_role_tasks import ProposedRoleTasks

        if yaml_content is None:
            return (
                None,
                "No fenced YAML block found. Emit your proposal in a ```yaml:proposed_plan_tasks.yaml``` block.",
            )
        try:
            proposal = ProposedRoleTasks.from_yaml(yaml_content)
        except ValueError as exc:
            return None, f"proposed_plan_tasks.yaml failed to parse: {exc}"
        if expected_brief_id and proposal.source_brief_id != expected_brief_id:
            return None, (
                f"brief_id mismatch: proposal cites {proposal.source_brief_id!r}, "
                f"upstream brief is {expected_brief_id!r}. Use the upstream brief_id verbatim."
            )
        if proposal.proposing_role != "qa":
            return None, (
                f"proposing_role must be 'qa' for this handler, got {proposal.proposing_role!r}"
            )
        return proposal, None


class StrategyProposePlanGuidanceHandler(_ProposeBaseHandler):
    """SIP-0093 PR 93.2: strategy plan-authoring guidance proposer."""

    _handler_name = "strategy_propose_plan_guidance_handler"
    _capability_id = "strategy.propose_plan_guidance"
    _role = "strat"
    _request_template_id = "request.strategy_propose_plan_guidance"
    _success_artifact_name = "plan_guidance.yaml"
    _success_artifact_type = "plan_guidance"
    _proposer_role = "strategy"

    def _build_render_variables(
        self,
        prd: str,
        prior_outputs: dict[str, Any] | None,
        inputs: dict[str, Any],
    ) -> dict[str, str]:
        # #484: strategy emits PlanGuidance (guidance_id), not a ProposedRoleTasks
        # (proposal_id), so its request template requires a `guidance_id` the shared
        # proposer base never provides — the strategy proposer crashed with
        # TemplateMissingVariableError on every multi-role cycle. Supply one, mirroring
        # the base's proposal_id generation.
        import uuid

        variables = super()._build_render_variables(prd, prior_outputs, inputs)
        variables["guidance_id"] = str(inputs.get("guidance_id") or f"guid-{uuid.uuid4().hex[:8]}")
        return variables

    def _parse_and_validate(
        self,
        yaml_content: str | None,
        expected_brief_id: str | None,
    ) -> tuple[Any | None, str | None]:
        from squadops.cycles.plan_guidance import PlanGuidance

        if yaml_content is None:
            return (
                None,
                "No fenced YAML block found. Emit your guidance in a ```yaml:plan_guidance.yaml``` block.",
            )
        try:
            guidance = PlanGuidance.from_yaml(yaml_content)
        except ValueError as exc:
            return None, f"plan_guidance.yaml failed to parse: {exc}"
        if expected_brief_id and guidance.source_brief_id != expected_brief_id:
            return None, (
                f"brief_id mismatch: guidance cites {guidance.source_brief_id!r}, "
                f"upstream brief is {expected_brief_id!r}. Use the upstream brief_id verbatim."
            )
        return guidance, None


# ---------------------------------------------------------------------------
# Merger handler (SIP-0093 PR 93.3) — the cutover. Runtime route changes here:
# governance.review_plan no longer authors implementation_plan.yaml; the
# merger does, consuming proposer artifacts via prior_outputs[role][...].
#
# Pure-deterministic per §5.8 (no LLM call). Falls back to
# PlanAuthoringService.produce_plan(...) when no proposals are available
# (configured or degraded sole-author).
# ---------------------------------------------------------------------------


class GovernanceMergePlanHandler(_CycleTaskHandler):
    """SIP-0093 PR 93.3: deterministic merger of role proposals.

    Consumes:
      - ``plan_authoring_brief.yaml`` (read-only — RC-22). Surfaced via
        ``prior_outputs["lead"]["brief_outcome"]["yaml_content"]``.
      - Proposer outcomes via ``prior_outputs[role]["proposal_outcome"]``
        for each contributor role (dev, qa, strat). Outcomes carry
        ``status: success | failure`` and the YAML content; the merger
        parses success records into ``ProposedRoleTasks`` /
        ``PlanGuidance`` and translates failures into ``MissingProposal``
        entries for ``merge_decisions.yaml``.
      - The configured contributors list via
        ``inputs["resolved_config"]["plan_authoring_contributors"]``.
        Drives the §5.9 missing-role operator warnings and the
        configured-vs-degraded distinction in sole-author mode.

    Produces (always two artifacts):
      - ``implementation_plan.yaml`` — canonical SIP-0092 M1 plan.
      - ``merge_decisions.yaml`` — auditable record with
        ``authoring_mode`` / ``sole_author_reason`` / ``proposal_completeness``
        per RC-26.

    Sole-author fallback: when no proposals are available (empty
    contributors list, or all configured proposals failed), the merger
    calls ``PlanAuthoringService.produce_plan(...)`` directly with the
    brief and the framing-tail planning_content concatenated. The same
    handler chain runs regardless of authoring mode — only the content
    inside ``merge_decisions.yaml`` differs.
    """

    _handler_name = "governance_merge_plan_handler"
    _capability_id = "governance.merge_plan"
    _role = "lead"

    async def handle(
        self,
        context: ExecutionContext,
        inputs: dict[str, Any],
    ) -> HandlerResult:
        start_time = time.perf_counter()

        from squadops.capabilities.handlers._plan_merger import (
            build_sole_author_decisions,
            emit_merge_decisions_yaml,
            emit_plan_yaml,
            merge_proposals,
        )
        from squadops.cycles.merge_decisions import MissingProposal
        from squadops.cycles.plan_authoring_brief import PlanAuthoringBrief
        from squadops.cycles.plan_guidance import PlanGuidance
        from squadops.cycles.proposed_role_tasks import ProposedRoleTasks

        prior_outputs = inputs.get("prior_outputs") or {}
        resolved_config = inputs.get("resolved_config") or {}
        configured_contributors = list(resolved_config.get("plan_authoring_contributors") or [])

        # Brief is mandatory upstream — without it the merger has no
        # contract to anchor proposals against. Fail loudly if absent
        # (this is a wiring bug, not a recoverable runtime condition).
        brief_outcome = prior_outputs.get("lead", {}).get("brief_outcome")
        if not brief_outcome or not brief_outcome.get("yaml_content"):
            return self._failure_result(
                start_time,
                inputs,
                "governance.merge_plan requires plan_authoring_brief.yaml in "
                "prior_outputs['lead']['brief_outcome']",
            )
        try:
            brief = PlanAuthoringBrief.from_yaml(brief_outcome["yaml_content"])
        except ValueError as exc:
            return self._failure_result(
                start_time,
                inputs,
                f"plan_authoring_brief.yaml failed to parse at merger: {exc}",
            )

        # Read each role's proposal outcome. Absent role-key (e.g. dev
        # not in contributors) is distinct from present-but-failed
        # (degraded mode tracking). Both yield a None proposal but only
        # the latter contributes to missing_proposals.
        dev_outcome = prior_outputs.get("dev", {}).get("proposal_outcome")
        qa_outcome = prior_outputs.get("qa", {}).get("proposal_outcome")
        strat_outcome = prior_outputs.get("strat", {}).get("proposal_outcome")

        dev_proposal, dev_missing = self._parse_proposal_outcome(
            dev_outcome, "development", ProposedRoleTasks
        )
        qa_proposal, qa_missing = self._parse_proposal_outcome(qa_outcome, "qa", ProposedRoleTasks)
        strategy_guidance, strat_missing = self._parse_proposal_outcome(
            strat_outcome, "strategy", PlanGuidance
        )

        missing_proposals: list[MissingProposal] = []
        for entry in (dev_missing, qa_missing, strat_missing):
            if entry is not None:
                missing_proposals.append(entry)

        successful_count = sum(
            1 for p in (dev_proposal, qa_proposal, strategy_guidance) if p is not None
        )

        prd = inputs.get("prd", "")
        prd_hash = inputs.get("config_hash") or ""
        project_id = getattr(context, "project_id", None) or "(unknown)"
        cycle_id = getattr(context, "cycle_id", None) or "(unknown)"

        if successful_count == 0:
            return await self._handle_sole_author(
                start_time=start_time,
                inputs=inputs,
                context=context,
                brief=brief,
                missing_proposals=missing_proposals,
                configured_contributors=configured_contributors,
                project_id=project_id,
                cycle_id=cycle_id,
                prd=prd,
                prd_hash=prd_hash,
                prior_outputs=prior_outputs,
                build_sole_author_decisions=build_sole_author_decisions,
                emit_plan_yaml=emit_plan_yaml,
                emit_merge_decisions_yaml=emit_merge_decisions_yaml,
            )

        plan, decisions = merge_proposals(
            brief=brief,
            dev_proposal=dev_proposal,
            qa_proposal=qa_proposal,
            strategy_guidance=strategy_guidance,
            project_id=project_id,
            cycle_id=cycle_id,
            prd_hash=prd_hash,
            configured_contributors=configured_contributors,
            missing_proposals=missing_proposals,
        )

        return self._success_result(
            start_time,
            inputs,
            plan_yaml=emit_plan_yaml(plan),
            decisions_yaml=emit_merge_decisions_yaml(decisions),
            authoring_mode=decisions.authoring_mode,
            interface_manifest_yaml=self._read_interface_manifest(prior_outputs),
        )

    @staticmethod
    def _read_interface_manifest(prior_outputs: dict[str, Any]) -> str | None:
        """Raw ``interface_manifest.yaml`` a framing proposer emitted (dev preferred, qa
        fallback), or ``None`` (SIP-0099 99.2). Data-driven: absence = today's behavior,
        no flag."""
        for role_key in ("dev", "qa"):
            outcome = (prior_outputs.get(role_key) or {}).get("proposal_outcome") or {}
            raw = outcome.get("interface_manifest_yaml")
            if raw:
                return raw
        return None

    def _parse_proposal_outcome(
        self,
        outcome: dict[str, Any] | None,
        proposer_role: str,
        schema_cls: Any,
    ) -> tuple[Any | None, Any]:
        """Parse a proposer outcome into (parsed_object, MissingProposal | None).

        Returns the parsed proposal/guidance on success (no MissingProposal
        entry). On failure outcome OR malformed outcome: returns (None,
        MissingProposal) so the merger can record the gap. Absent outcome
        (proposer not in pipeline) returns (None, None) — neither parsed
        content nor a missing-role entry.
        """
        from squadops.cycles.merge_decisions import MissingProposal
        from squadops.cycles.proposal_failure import ProposalFailure

        if not outcome:
            return None, None

        status = outcome.get("status")
        if status == "failure":
            reason = outcome.get("failure_reason") or "unknown"
            details = ""
            yaml_content = outcome.get("yaml_content")
            if yaml_content:
                try:
                    parsed_failure = ProposalFailure.from_yaml(yaml_content)
                    reason = parsed_failure.failure_reason
                    details = parsed_failure.details
                except ValueError:
                    details = "proposal_failure artifact malformed"
            return None, MissingProposal(
                role=proposer_role,
                failure_reason=f"{reason}{(': ' + details) if details else ''}"[:256],
            )

        yaml_content = outcome.get("yaml_content")
        if not yaml_content:
            return None, MissingProposal(
                role=proposer_role,
                failure_reason="malformed_yaml: outcome carried no yaml_content",
            )

        try:
            parsed = schema_cls.from_yaml(yaml_content)
        except ValueError as exc:
            return None, MissingProposal(
                role=proposer_role,
                failure_reason=f"schema_validation_error: {exc}"[:256],
            )

        return parsed, None

    async def _handle_sole_author(
        self,
        *,
        start_time: float,
        inputs: dict[str, Any],
        context: ExecutionContext,
        brief: Any,
        missing_proposals: list[Any],
        configured_contributors: list[str],
        project_id: str,
        cycle_id: str,
        prd: str,
        prd_hash: str,
        prior_outputs: dict[str, Any],
        build_sole_author_decisions: Any,
        emit_plan_yaml: Any,
        emit_merge_decisions_yaml: Any,
    ) -> HandlerResult:
        """Sole-author fallback: delegate to PlanAuthoringService.

        Two sub-cases per §5.10:
          - ``no_contributors_configured`` — empty contributors list.
          - ``all_proposals_failed`` — non-empty contributors, all failed.
        The split is determined by whether missing_proposals is empty (no
        failures were recorded) or populated (every configured role
        failed).
        """
        from squadops.capabilities.handlers._plan_authoring_service import (
            produce_plan,
        )
        from squadops.cycles.implementation_plan import ImplementationPlan

        sole_author_reason = (
            "no_contributors_configured" if not configured_contributors else "all_proposals_failed"
        )

        planning_content = self._build_planning_content_from_framing(prior_outputs)

        manifest = await produce_plan(
            context,
            inputs,
            planning_content=planning_content,
            resolved_config=inputs.get("resolved_config", {}),
            role=self._role,
            handler_name=self._handler_name,
            chat_kwargs=self._build_chat_kwargs(inputs),
        )

        if manifest is None:
            return self._failure_result(
                start_time,
                inputs,
                "sole-author fallback exhausted PlanAuthoringService retry budget",
            )

        plan = ImplementationPlan.from_yaml(manifest["content"])
        decisions = build_sole_author_decisions(
            brief=brief,
            cycle_id=cycle_id,
            sole_author_reason=sole_author_reason,
            canonical_tasks=list(plan.tasks),
            missing_proposals=missing_proposals,
        )
        return self._success_result(
            start_time,
            inputs,
            plan_yaml=emit_plan_yaml(plan),
            decisions_yaml=emit_merge_decisions_yaml(decisions),
            authoring_mode="sole_author",
            # sole-author path: the interface manifest, if any, rides produce_plan's
            # return (SIP-0099 99.2).
            interface_manifest_yaml=manifest.get("interface_manifest_yaml"),
        )

    def _build_planning_content_from_framing(
        self,
        prior_outputs: dict[str, Any],
    ) -> str:
        """Concatenate the four framing-tail role outputs for sole-author fallback.

        ``PlanAuthoringService.produce_plan`` expects a ``planning_content``
        string that historically came from ``governance.review_plan``'s
        consolidated planning artifact. Post-cutover, the planning artifact
        is produced AFTER the merger (in review_plan's sign-off step), so
        the merger has to assemble its own context from the framing tail.
        """
        parts: list[str] = []
        for role_key in ("data", "strat", "dev", "qa"):
            slot = prior_outputs.get(role_key) or {}
            summary = slot.get("summary")
            if summary:
                parts.append(f"## {role_key} output\n\n{summary}")
        return "\n\n".join(parts) if parts else "(no framing context available)"

    def _success_result(
        self,
        start_time: float,
        inputs: dict[str, Any],
        *,
        plan_yaml: str,
        decisions_yaml: str,
        authoring_mode: str,
        interface_manifest_yaml: str | None = None,
    ) -> HandlerResult:
        artifacts: list[dict[str, Any]] = [
            {
                "name": "implementation_plan.yaml",
                "content": plan_yaml,
                "media_type": "text/yaml",
                "type": "control_implementation_plan",
            },
            {
                "name": "merge_decisions.yaml",
                "content": decisions_yaml,
                "media_type": "text/yaml",
                "type": "merge_decisions",
            },
        ]
        # SIP-0099 99.2: the framing-authored interface manifest rides alongside the plan
        # as a sibling artifact — surfaced in the gate package for operator review and
        # loaded by the executor (99.3). Emitted only when a proposer/sole-author authored
        # one; absent → the artifact set is byte-identical to today. The merger does NOT
        # validate it — that is net-b's job (dispatched_flow_executor), keeping emission
        # and validation cleanly separated.
        if interface_manifest_yaml:
            artifacts.append(
                {
                    "name": "interface_manifest.yaml",
                    "content": interface_manifest_yaml,
                    "media_type": "text/yaml",
                    "type": "interface_manifest",
                }
            )
        outputs = {
            "summary": f"[{self._role}] merged plan produced ({authoring_mode})",
            "role": self._role,
            "artifacts": artifacts,
            # Surfaced for review_plan's sign-off and the gate package.
            "merge_outcome": {
                "authoring_mode": authoring_mode,
                "plan_yaml": plan_yaml,
                "decisions_yaml": decisions_yaml,
            },
        }
        duration_ms = (time.perf_counter() - start_time) * 1000
        evidence = HandlerEvidence.create(
            handler_name=self._handler_name,
            capability_id=self._capability_id,
            duration_ms=duration_ms,
            inputs_hash=self._hash_dict(inputs),
            outputs_hash=self._hash_dict(outputs),
        )
        return HandlerResult(success=True, outputs=outputs, _evidence=evidence)

    def _failure_result(
        self,
        start_time: float,
        inputs: dict[str, Any],
        error: str,
    ) -> HandlerResult:
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
            error=error,
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
