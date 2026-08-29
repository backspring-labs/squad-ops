"""Shared planning-handler base (#331 split from planning_tasks.py).

``_PlanningTaskHandler`` overrides system-prompt assembly to activate the
``task_type`` prompt layer via ``prompt_service.assemble(role, hook,
task_type=...)`` — the key difference from ``_CycleTaskHandler``, which
calls ``get_system_prompt(role)`` (no task_type layer). Plus the shared
time-budget/summary prompt helpers.
"""

from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING, Any

from squadops.capabilities.handlers.base import (
    HandlerEvidence,
    HandlerResult,
)
from squadops.capabilities.handlers.cycle import _CycleTaskHandler
from squadops.llm.exceptions import LLMError
from squadops.llm.models import ChatMessage

if TYPE_CHECKING:
    from squadops.capabilities.handlers.context import ExecutionContext

from squadops.capabilities.handlers.emission_log import log_emission_shape

logger = logging.getLogger(__name__)


def _content_summary(content: str, limit: int = 240) -> str:
    """First ``limit`` chars of the produced document, whitespace-collapsed.

    #657: the chained ``summary`` is the only cross-task context the executor
    keeps once artifacts are stripped — a PRD-prefix summary said nothing
    about the document this task actually produced.
    """
    collapsed = " ".join(content.split())
    return collapsed[:limit]


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

    async def _target_stack_section(self, renderer: Any, inputs: dict[str, Any]) -> str:
        """The stack this cycle builds, stated as a decision (#838).

        VS (`cyc_afa934886acd`) framed for 75 minutes and designed the wrong application.
        Nothing had misbehaved: the group_run PRD names its stack in prose — *"a coherent,
        runnable full-stack vertical slice (FastAPI + React)"* — the research stage summarised
        it, the design stage designed it, and the manifest author inherited it. **Every stage
        was obediently following the requirements**, which disagreed with the cycle's
        configuration and won because they were the louder input.

        So this is not "tell the design stage the stack"; it is *"the stack the cycle
        configures outranks anything the PRD says about architecture"* — a precedence rule,
        stated once, on the shared base so every framing stage inherits it rather than the
        design stage alone. Research frames the design stage's inputs, and objective framing
        frames both.

        Empty for a cycle with no scaffoldable ``build_profile``: a free-form generation cycle
        has no stack to be decided for it, and asserting one would be a fiction.
        """
        from squadops.capabilities.scaffold import scaffold_stack_for
        from squadops.capabilities.stack_narratives import stack_narrative

        stack = scaffold_stack_for(inputs.get("resolved_config"))
        if not stack:
            return ""
        narrative = stack_narrative(stack)
        if not narrative:
            # A registered stack with no narrative would render a bare heading and teach
            # nothing. Silence beats an authoritative-looking empty section.
            return ""
        rendered = await renderer.render(
            "request.target_stack_section", {"stack": stack, "stack_narrative": narrative}
        )
        return rendered.content

    async def _authoring_rules_section(self, renderer: Any) -> str:
        """The plan-shape rules every deterministic validator enforces (#686).

        Unconditional — unlike the sections around it there is no input to key on,
        because these rules hold for every plan on every roll. shk-1's first framing
        authored the #673 dual-claim shape with the contract, the manifest and the
        typed-acceptance vocabulary all present, because the rules themselves appeared
        in no prompt: the validator knew, the author never did (#629's pattern). Prose
        is the managed asset; which validators are author-facing is the data table in
        ``squadops.cycles.plan_authoring_rules``, and a test binds the two (#448).
        """
        from squadops.capabilities.handlers._plan_authoring import authoring_rules_section

        return await authoring_rules_section(renderer)

    async def _rejection_context_section(self, renderer: Any, inputs: dict[str, Any]) -> str:
        """The prior-rejection appendix on a framing re-roll, or "" (#669).

        A #522 re-roll previously started with fresh dice and zero context —
        the validator's teaching message persisted in gate_decisions where no
        model ever read it, so the re-roll was free to re-emit the exact
        rejected shape (fay-10 tripped the same ownership class on all three
        framings; fay-15's #658 rejection named file, rule, and consequence to
        nobody). Data arrives as dispatch-injected inputs; all prose lives in
        the appendix assets (CLAUDE.md #448).
        """
        reasons = [
            str(r).strip() for r in (inputs.get("rejection_reasons") or []) if str(r).strip()
        ]
        if not reasons:
            return ""
        variables: dict[str, str] = {"rejection_reasons": "\n".join(f"- {r}" for r in reasons)}
        plan_yaml = str(inputs.get("rejected_plan_yaml") or "").strip()
        if plan_yaml:
            plan_rendered = await renderer.render(
                "request.plan_reroll_rejected_plan_appendix",
                {"rejected_plan_yaml": plan_yaml},
            )
            variables["rejected_plan_section"] = plan_rendered.content
        rendered = await renderer.render("request.plan_reroll_rejection_appendix", variables)
        return rendered.content

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
        formatted = self._format_prior_outputs(prior_outputs)
        if formatted:
            parts.append(formatted)
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
            # #838: attached here rather than in `_build_render_variables` because rendering
            # the section is itself async. Every framing stage inherits it — research frames
            # the design stage's inputs and objective framing frames both, so telling only
            # the design stage would leave the contamination path open one step upstream.
            stack_section = await self._target_stack_section(renderer, inputs)
            if stack_section:
                variables["target_stack_section"] = stack_section
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
        log_emission_shape(self._handler_name, content, response.completion_tokens)
        llm_duration_ms = (time.perf_counter() - start_time) * 1000

        # Record LLM generation for LangFuse tracing (SIP-0061 Option B)
        llm_obs = getattr(context.ports, "llm_observability", None)
        if llm_obs and context.correlation_context:
            from squadops.telemetry.models import (
                PromptLayer,
                PromptLayerMetadata,
                build_generation_record,
            )

            resolved_model = chat_kwargs.get("model", context.ports.llm.default_model)
            gen_record = build_generation_record(
                model=resolved_model,
                prompt_text=user_prompt,
                response_text=content,
                latency_ms=llm_duration_ms,
                usage=response,
                prompt_name=rendered.template_id if rendered else None,
                prompt_version=(
                    int(rendered.template_version)
                    if rendered and rendered.template_version
                    else None
                ),
                reasoning=chat_kwargs.get("reasoning"),
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

        doc_summary = _content_summary(content) or "(empty document)"

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
            "summary": f"[{self._role}] {doc_summary}",
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
