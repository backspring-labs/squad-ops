"""_CycleTaskHandler — shared base for cycle task handlers (SIP-0066).
Split from cycle_tasks.py (#152).
"""

from __future__ import annotations

import logging
import tempfile
import time
from pathlib import Path
from typing import TYPE_CHECKING, Any

from squadops.capabilities.handlers.base import (
    CapabilityHandler,
    HandlerEvidence,
    HandlerResult,
)
from squadops.capabilities.reasoning_policy import resolve_reasoning_level
from squadops.cycles.acceptance_check_spec import (
    CHECK_SPECS,
    CONFIG_OFF_SKIP_REASONS,
    is_check_applicable,
)
from squadops.cycles.acceptance_checks import CheckOutcome
from squadops.cycles.acceptance_evaluation import (
    evaluate_criterion,
    resolve_check_stack,
    split_acceptance_criteria,
)
from squadops.cycles.emission_integrity import emission_stats
from squadops.cycles.implementation_plan import TypedCheck
from squadops.cycles.patch_verification import materialize_artifacts
from squadops.cycles.verification_integrity import ResultStatus
from squadops.llm.exceptions import LLMError
from squadops.llm.model_registry import get_model_spec
from squadops.llm.models import ChatMessage

if TYPE_CHECKING:
    from squadops.capabilities.handlers.context import ExecutionContext

from squadops.capabilities.handlers.cycle.validation import (
    ValidationResult,
    _build_typed_check_evaluation_artifact,
)
from squadops.capabilities.handlers.emission_log import log_emission_shape

logger = logging.getLogger(__name__)


#: Checks the framework injects here, derived from the registry rather than
#: listed beside it (#1082 added the second one, and a hand-kept list is how the
#: menu and the injector would drift). The filter is exactly what this seam can
#: satisfy: a framework-injected check whose only parameter is the file the task
#: emitted. Checks needing more (``fill_slot_signature``'s routes,
#: ``contract_assertions_match``'s endpoints) are injected where that context
#: lives, and are excluded here by construction rather than by memory.
_FILE_SCOPED_FRAMEWORK_CHECKS: tuple[str, ...] = tuple(
    sorted(
        name
        for name, spec in CHECK_SPECS.items()
        if spec.framework_injected and spec.required_params == frozenset({"file"})
    )
)


def _framework_injected_criteria(
    artifacts: list[dict], authored: tuple[TypedCheck, ...]
) -> list[TypedCheck]:
    """Checks the framework applies to this emission regardless of what was authored (#689).

    Today that is ``undefined_names`` on every ``.py`` file emitted by a handler that
    routes through this seam: dev, builder, and — since #670 (ruled fork 1, landed
    v1.5) — ``qa.test``, whose override now calls the seam like the others, so
    authored checks and framework injections alike reach qa emissions. Injection —
    rather than adding the check to the contract's per-slot criteria — is what makes
    it reach a BIND-mode cycle at all: bind mode loads the pinned contract from
    ``contract_ref`` instead of regenerating it, so a criterion added to the expander
    would not appear until a re-seed, and the check would ship unverified.

    Scoped to the producer's own emitted artifacts, so it can never indict a file this
    task did not write. An authored row for the same check and file wins — the author
    may have set a different severity, and two rows for one file would double-count in
    the evidence.
    """
    already = {(c.check, str(c.params.get("file", ""))) for c in authored}
    injected: list[TypedCheck] = []
    for check_name in _FILE_SCOPED_FRAMEWORK_CHECKS:
        spec = CHECK_SPECS[check_name]
        seen: set[str] = set()
        for art in artifacts:
            name = art.get("name") if art.get("name") is not None else art.get("path")
            if not isinstance(name, str) or not is_check_applicable(check_name, name):
                continue
            if name in seen or (check_name, name) in already:
                continue
            seen.add(name)
            injected.append(
                TypedCheck(
                    check=check_name,
                    params={"file": name},
                    severity=spec.blocking_default,
                )
            )
    return injected


class _CycleTaskHandler(CapabilityHandler):
    """Base class for cycle task handlers.

    Provides shared validate_inputs (requires 'prd') and a template
    handle() that calls ``context.ports.llm.chat()`` with system prompts
    assembled via ``context.ports.prompt_service`` (SIP-0057).
    Subclasses set ``_role`` and ``_artifact_name``.
    """

    _handler_name: str = ""
    _capability_id: str = ""
    _role: str = ""
    _artifact_name: str = ""
    _request_template_id: str = "request.cycle_task_base"

    @property
    def name(self) -> str:
        return self._handler_name

    @property
    def capability_id(self) -> str:
        return self._capability_id

    @property
    def description(self) -> str:
        return f"Cycle task handler for {self._role} role ({self._capability_id})"

    # Issue #114: thin instance binding so subclass handlers can call
    # `self._build_typed_check_evaluation_artifact(...)` without importing
    # the module-level function. Real implementation is module-scoped so
    # handlers that don't extend this base (or future module-level
    # callers) can use it directly.
    @staticmethod
    def _build_typed_check_evaluation_artifact(
        validation_checks: list[dict],
        task_index: Any,
        task_type: str,
        workspace_revision_id: str | None = None,
    ) -> dict | None:
        return _build_typed_check_evaluation_artifact(
            validation_checks, task_index, task_type, workspace_revision_id
        )

    def validate_inputs(
        self,
        inputs: dict[str, Any],
        contract=None,
    ) -> list[str]:
        errors = super().validate_inputs(inputs, contract)
        if "prd" not in inputs:
            errors.append("'prd' is required")
        return errors

    def _build_user_prompt(
        self,
        prd: str,
        prior_outputs: dict[str, Any] | None,
        inputs: dict[str, Any] | None = None,
    ) -> str:
        """Assemble user prompt from PRD and upstream handler outputs.

        ``inputs`` is the full task inputs dict; the default implementation
        ignores it but subclasses (notably the correction-loop repair
        handlers) consume it to surface failure context, expected
        artifacts, and acceptance criteria that aren't reachable from
        ``prd`` or ``prior_outputs`` alone.
        """
        parts = [f"## Product Requirements Document\n\n{prd}"]
        if prior_outputs:
            parts.append("\n\n## Prior Analysis from Upstream Roles\n")
            for role, summary in prior_outputs.items():
                parts.append(f"### {role}\n{summary}\n")
        parts.append(f"\nPlease provide your {self._role} analysis and deliverables.")
        return "\n".join(parts)

    @staticmethod
    def _format_prior_outputs(prior_outputs: dict[str, Any] | None) -> str:
        """Format prior outputs dict as a prompt section string for template injection.

        #657: ``artifact_contents`` (executor-threaded upstream documents, RC-22)
        renders as full named sections; role entries render their ``summary``
        field — the raw outputs dict carries provenance hashes and wire keys
        that are noise as prompt context.
        """
        if not prior_outputs:
            return ""
        parts = ["\n\n## Prior Analysis from Upstream Roles\n"]
        contents = prior_outputs.get("artifact_contents")
        if isinstance(contents, dict):
            for name, content in contents.items():
                parts.append(f"### {name}\n{content}\n")
        for role, value in prior_outputs.items():
            if role == "artifact_contents":
                continue
            summary = value.get("summary", "") if isinstance(value, dict) else value
            parts.append(f"### {role}\n{summary}\n")
        return "\n".join(parts)

    def _build_render_variables(
        self,
        prd: str,
        prior_outputs: dict[str, Any] | None,
        inputs: dict[str, Any],
    ) -> dict[str, str]:
        """Build template variables for request rendering. Override for custom variables."""
        return {
            "prd": prd,
            "role": self._role,
            "prior_outputs": self._format_prior_outputs(prior_outputs),
        }

    def _build_artifacts_from_content(self, content: str) -> list[dict[str, Any]]:
        """Build artifact list from LLM response content.

        Default wraps the full response as a single markdown document under
        ``self._artifact_name``. Handlers whose LLM emits multi-file source
        output (fenced code blocks, e.g. development.develop and
        development.correction_repair) override this to extract per-file
        artifacts via ``extract_fenced_files``. The default exists so the
        majority of handlers (that produce narrative deliverables) keep
        working without each one re-implementing the wrap.
        """
        return [
            {
                "name": self._artifact_name,
                "content": content,
                "media_type": "text/markdown",
                "type": "document",
            },
        ]

    def _fail_result(
        self,
        start_time: float,
        inputs: dict[str, Any],
        error: str,
        outputs: dict[str, Any] | None = None,
        outcome_class: str | None = None,
        failure_classification: str | None = None,
    ) -> HandlerResult:
        """Build a failure HandlerResult with evidence.

        When ``outcome_class`` is provided (SIP-0086 Stage B), it is written
        to ``outputs["outcome_class"]`` so the executor's correction-routing
        path in ``_handle_task_outcome`` uses the semantic classification
        instead of falling through to the D5 retry-then-SEMANTIC_FAILURE
        fallback. Handlers with structural validation (e.g., missing
        required artifacts) should emit ``TaskOutcome.SEMANTIC_FAILURE``
        with ``FailureClassification.WORK_PRODUCT`` so analysis runs
        against a known classification rather than "unknown".
        """
        duration_ms = (time.perf_counter() - start_time) * 1000
        evidence = HandlerEvidence.create(
            handler_name=self._handler_name,
            capability_id=self._capability_id,
            duration_ms=duration_ms,
            inputs_hash=self._hash_dict(inputs),
        )
        merged_outputs = dict(outputs or {})
        if outcome_class is not None:
            merged_outputs["outcome_class"] = outcome_class
        if failure_classification is not None:
            merged_outputs["failure_classification"] = failure_classification
        return HandlerResult(
            success=False,
            outputs=merged_outputs,
            _evidence=evidence,
            error=error,
        )

    def _log_no_fenced_blocks(self, content: str, *, excerpt: int = 1000) -> None:
        """Log the truncated raw LLM response when fenced extraction found
        nothing (#130).

        The build/QA handlers otherwise only persist the raw into a
        ``build_warnings.md`` artifact, so a zero-extraction failure leaves no
        signal in the agent logs. The raw is the only way to distinguish a
        thinking-mode token blowout from a prompt/scope formatting failure.
        """
        logger.warning(
            "%s: no fenced code blocks extracted from a %d-char response; raw[:%d]=%r",
            self._handler_name,
            len(content),
            excerpt,
            content[:excerpt],
        )

    async def _apply_emission_retry_feedback(
        self,
        context: ExecutionContext,
        inputs: dict[str, Any],
        user_prompt: str,
    ) -> str:
        """#566: append the parse-failure feedback appendix to a retry prompt.

        The executor sets ``inputs["emission_retry_feedback"]`` (the prior
        attempt's ``emission_failure`` marker) when re-dispatching after a
        zero-extraction failure — without it the retry re-rolls blind on the
        same prior. All instruction prose renders from the managed template
        asset; this method only supplies the data lines. No renderer or no
        marker → prompt unchanged.
        """
        marker = inputs.get("emission_retry_feedback")
        if not isinstance(marker, dict):
            return user_prompt
        renderer = getattr(context.ports, "request_renderer", None)
        if renderer is None:
            return user_prompt
        from squadops.cycles.emission_integrity import emission_retry_reason_line

        expected = [
            str(e)
            for e in (marker.get("expected_artifacts") or inputs.get("expected_artifacts") or [])
            if e
        ]
        expected_files = "\n".join(f"  - `{e}`" for e in expected) or "  - (as named in the task)"
        rendered = await renderer.render(
            "request.cycle_emission_retry_feedback",
            {
                "reason_line": emission_retry_reason_line(marker),
                "expected_files": expected_files,
            },
        )
        return f"{user_prompt}\n\n{rendered.content}"

    def _resolve_model_budget(
        self,
        inputs: dict[str, Any],
        capability_max_tokens: int,
        default_model: str,
    ) -> tuple[str, int, int | None]:
        """Resolve model name, token budget, and context window from inputs.

        Returns (model_name, max_tokens, context_window).
        """
        agent_overrides = inputs.get("agent_config_overrides", {})
        agent_model = inputs.get("agent_model") or None
        model_name = agent_model or default_model
        model_spec = get_model_spec(model_name)

        max_tokens = capability_max_tokens
        context_window = None
        if model_spec is not None:
            max_tokens = min(max_tokens, model_spec.default_max_completion)
            context_window = model_spec.context_window
        if "max_completion_tokens" in agent_overrides:
            max_tokens = agent_overrides["max_completion_tokens"]

        return model_name, max_tokens, context_window

    def _build_chat_kwargs(self, inputs: dict[str, Any]) -> dict[str, Any]:
        """Build chat() kwargs from agent config overrides (SIP-0075 §3.2).

        #1011: without an explicit ``max_completion_tokens`` override, the
        registry's per-model completion clamp applies — previously ``max_tokens``
        was simply omitted here, so every handler riding the base path
        (correction repairs foremost) ran at capability ceilings the clamped
        develop/qa handlers never see (a dev repair emitted 12,314 tokens under
        an 8,192-clamped model, V38 shakedown #2). An explicit override still
        wins, and a model without a registry entry keeps the old behavior —
        the clamp cannot invent a budget for a model it does not know.
        """
        overrides = inputs.get("agent_config_overrides", {})
        agent_model = inputs.get("agent_model") or None
        kwargs: dict[str, Any] = {}
        if agent_model:
            kwargs["model"] = agent_model
        if "temperature" in overrides:
            kwargs["temperature"] = overrides["temperature"]
        if "max_completion_tokens" in overrides:
            kwargs["max_tokens"] = overrides["max_completion_tokens"]
        elif agent_model and (spec := get_model_spec(agent_model)) is not None:
            kwargs["max_tokens"] = spec.default_max_completion
        if "timeout_seconds" in overrides:
            kwargs["timeout_seconds"] = overrides["timeout_seconds"]
        # #927: keyed on the agent's model exactly as the completion clamp is — a
        # task dispatched without one sends no level, as it gets no clamp.
        reasoning = resolve_reasoning_level(
            self._capability_id, agent_overrides=overrides, model_name=agent_model
        )
        if reasoning is not None:
            kwargs["reasoning"] = reasoning
        return kwargs

    # SIP-0086: Output validation and self-evaluation (Stage B)

    async def _validate_output(
        self,
        inputs: dict[str, Any],
        artifacts: list[dict],
        *,
        typed_error_counts: dict[str, int] | None = None,
    ) -> ValidationResult:
        """Validate handler output. Override in build handler subclasses.

        SIP-0092 M1.3: typed-acceptance evaluation may run async work
        (subprocess execution for command_exit_zero); the base method is
        async so subclasses can await without restructuring.
        """
        return ValidationResult(passed=True, summary="No validation configured")

    # ---- SIP-0092 M1.3 typed acceptance (shared seam, #419/#420) ----------
    #
    # Hoisted from DevelopmentDevelopHandler so every cycle handler whose
    # plan task carries typed acceptance criteria enforces them identically
    # (#419: the builder seam silently ignored its contract). Criteria arrive
    # as wire-shape dicts after distributed dispatch; coercion happens in
    # split_acceptance_criteria (#420), never via isinstance filtering here.

    async def _evaluate_typed_acceptance(
        self,
        inputs: dict[str, Any],
        artifacts: list[dict],
        checks: list[dict],
        missing: list[str],
        typed_error_counts: dict[str, int],
    ) -> None:
        """Evaluate typed acceptance criteria, mutating ``checks`` and ``missing`` in place.

        Implements RC-9 (severity × status blocking matrix), RC-9a (error-vs-
        failed wording distinction), RC-9b (per-criterion error count with
        2-strikes escalation), RC-12a (skipped-not-error for unset stack).
        """
        split = split_acceptance_criteria(inputs.get("acceptance_criteria", []))

        # Prose strings stay informational, evidence-only — same as Rev 1's
        # included_in_evidence behavior. They never block.
        if split.prose:
            checks.append(
                {
                    "check": "acceptance_criteria_prose",
                    "criteria": list(split.prose),
                    "evaluation": "included_in_evidence",
                    "passed": True,
                }
            )

        # #420: disclosed, non-blocking. The parser enforces vocabulary at
        # plan-authoring time, so a row landing here is a transport-shape
        # bug — surface it in evidence rather than misfiling it as prose.
        if split.unparseable:
            checks.append(
                {
                    "check": "acceptance_criteria_unparseable",
                    "criteria": [repr(c) for c in split.unparseable],
                    "evaluation": "unparseable_not_evaluated",
                    "passed": True,
                }
            )

        authored_criteria = list(split.typed)
        typed_criteria = authored_criteria + _framework_injected_criteria(artifacts, split.typed)
        if not typed_criteria:
            return

        resolved_config = inputs.get("resolved_config", {})
        typed_acceptance_enabled = resolved_config.get("typed_acceptance", True)
        command_acceptance_enabled = resolved_config.get("command_acceptance_checks", True)
        stack = resolve_check_stack(resolved_config)

        with tempfile.TemporaryDirectory(prefix="squadops-typed-acc-") as tmpdir_str:
            workspace_root = Path(tmpdir_str)
            # #643: materialize the accepted workspace tree first (executor
            # threads it — scaffold siblings included), then this task's own
            # artifacts on top so the candidate supersedes its own slots.
            # Runtime-level checks (module_imports) false-fail contract-
            # mandated sibling imports in a task-artifacts-only workspace.
            workspace_files = inputs.get("acceptance_workspace_files") or {}
            if workspace_files:
                self._materialize_artifacts(
                    [
                        {"name": name, "content": content}
                        for name, content in workspace_files.items()
                    ],
                    workspace_root,
                )
            self._materialize_artifacts(artifacts, workspace_root)

            for check_index, criterion in enumerate(typed_criteria):
                outcome = await evaluate_criterion(
                    criterion,
                    workspace_root,
                    stack=stack,
                    typed_acceptance_enabled=typed_acceptance_enabled,
                    command_acceptance_enabled=command_acceptance_enabled,
                )
                # #423: an *authored* error-severity check that the evaluator
                # skipped for any reason other than deliberate config-off is an
                # evidence gap — the author asked for enforcement on a concrete
                # target and the evaluator declared it cannot deliver
                # (unsupported extension/stack, missing tooling). Distinct from
                # the benign classes: config-off skips, and framework-injected
                # checks (which target only files in their own family, #605).
                # A gap must never read `passed: true` — that is the false
                # green #423 measured (7 of 14 evaluations skipped-yet-passed,
                # the whole frontend contract surface unenforced) — but it also
                # must not mission a correction: no code repair can close an
                # evaluator limitation. It surfaces as unverified at the
                # SIP-0096 roll-up instead (see verification_normalize /
                # aggregate_verification).
                evidence_gap = (
                    outcome.status == ResultStatus.SKIPPED
                    and check_index < len(authored_criteria)
                    and criterion.severity == "error"
                    and outcome.reason not in CONFIG_OFF_SKIP_REASONS
                )
                check_record = {
                    "check": f"acceptance:{criterion.check}",
                    "severity": criterion.severity,
                    "params": criterion.params,
                    "description": criterion.description,
                    "status": outcome.status,
                    "actual": outcome.actual,
                    "reason": outcome.reason,
                    # `passed` flag for compatibility with the legacy
                    # all-checks-pass aggregator: severity=error AND blocking
                    # status, or an evidence-gap skip (#423), counts as
                    # not-passed.
                    "passed": not (
                        criterion.severity == "error" and outcome.status in {"failed", "error"}
                    )
                    and not evidence_gap,
                    "evidence_gap": evidence_gap,
                    # Issue #114: identity fields for downstream trigger
                    # composition and per-cycle evaluation persistence.
                    # task_index is None for tasks not driven by an
                    # implementation_plan (legacy monolithic flow).
                    "task_index": inputs.get("subtask_index"),
                    "check_index": check_index,
                    # SIP-0098 98.3: the contract criterion id when this check was
                    # resolved from a bind-mode criteria_ref; None for authored checks.
                    "criterion_id": criterion.id or None,
                }
                checks.append(check_record)

                # Issue #83: per-check observability. Without these the M1.3
                # path is invisible to operators — see issue body for context.
                blocking = criterion.severity == "error" and outcome.status in {"failed", "error"}
                log_fn = logger.info if blocking else logger.debug
                log_fn(
                    "typed_acceptance_check subtask=%s check=%s severity=%s status=%s blocking=%s reason=%s",
                    inputs.get("subtask_index"),
                    criterion.check,
                    criterion.severity,
                    outcome.status,
                    blocking,
                    outcome.reason or "",
                )

                # RC-9: severity AND status are independent. Only error+blocking missions.
                if criterion.severity != "error":
                    continue
                if outcome.status == "failed":
                    # RC-9a: app-incompleteness wording.
                    label = criterion.description or criterion.check
                    missing.append(f"acceptance:{label}")
                elif outcome.status == "error":
                    fp = criterion.fingerprint()
                    prior = typed_error_counts.get(fp, 0)
                    if prior < 2:
                        # RC-9a: evaluator-error wording, distinct from app-incomplete.
                        missing.append(f"evaluator-error:{criterion.check}: {outcome.reason}")
                    else:
                        self._escalate_persistent_evaluator_error(criterion, outcome)
                    typed_error_counts[fp] = prior + 1
                # status in {passed, skipped} never blocks.

    # Shared with the executor-side patch verification (#389) — one
    # materializer, one safety policy.
    _materialize_artifacts = staticmethod(materialize_artifacts)

    @staticmethod
    def _escalate_persistent_evaluator_error(criterion: TypedCheck, outcome: CheckOutcome) -> None:
        """RC-9b: surface a persistent evaluator error outside the self-eval feedback loop.

        Logged at WARNING with structured fields; the correction protocol
        and operator-facing surfaces consume the log. A first-class
        escalation channel is a follow-up if/when the prompt-feedback
        suppression proves insufficient.
        """
        logger.warning(
            "typed_check_evaluator_error_escalated",
            extra={
                "check": criterion.check,
                "severity": criterion.severity,
                "fingerprint": criterion.fingerprint(),
                "reason": outcome.reason,
                "actual": outcome.actual,
            },
        )

    @staticmethod
    def _build_self_eval_prompt(
        validation: ValidationResult,
        artifacts: list[dict],
    ) -> str:
        """Build follow-up prompt for self-evaluation after validation failure."""
        artifact_names = [a.get("name", "") for a in artifacts]
        parts = [
            "Your previous response was incomplete. Here is what's missing:\n\n",
            f"**Validation Summary:** {validation.summary}\n\n",
        ]
        if validation.missing_components:
            parts.append(f"**Missing Components:** {', '.join(validation.missing_components)}\n\n")
        parts.append(f"**Files You Already Produced:** {', '.join(artifact_names)}\n\n")
        parts.append(
            "Please produce ONLY the missing files. Use the same fenced code block format "
            "(```language:path/to/file```). Do not reproduce files you already generated."
        )
        return "".join(parts)

    @staticmethod
    def _merge_artifacts(
        existing: list[dict],
        new: list[dict],
        evidence: dict,
    ) -> list[dict]:
        """Merge new artifacts into existing, replacing files with same name.

        RC-7: The merged set is the authoritative candidate for revalidation.
        All additions and replacements are recorded in evidence.
        """
        by_name = {a["name"]: a for a in existing}
        merge_log: list[dict] = []

        for art in new:
            name = art["name"]
            if name in by_name:
                merge_log.append(
                    {
                        "action": "replaced",
                        "name": name,
                        "old_size": len(by_name[name].get("content", "")),
                        "new_size": len(art.get("content", "")),
                    }
                )
            else:
                merge_log.append(
                    {
                        "action": "added",
                        "name": name,
                        "size": len(art.get("content", "")),
                    }
                )
            by_name[name] = art

        evidence.setdefault("self_eval_merge_log", []).extend(merge_log)
        return list(by_name.values())

    async def handle(
        self,
        context: ExecutionContext,
        inputs: dict[str, Any],
    ) -> HandlerResult:
        start_time = time.perf_counter()

        prd = inputs.get("prd", "")
        prior_outputs = inputs.get("prior_outputs")

        # SIP-0084: dual-path — use request renderer when available
        rendered = None
        renderer = getattr(context.ports, "request_renderer", None)
        if renderer is not None:
            variables = self._build_render_variables(prd, prior_outputs, inputs)
            rendered = await renderer.render(self._request_template_id, variables)
            user_prompt = rendered.content
        else:
            user_prompt = self._build_user_prompt(prd, prior_outputs, inputs)

        assembled = context.ports.prompt_service.get_system_prompt(self._role)
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

        # #924: unconditional, and deliberately NOT inside the observability block below —
        # that block is gated on `llm_obs and correlation_context`, so a capture placed
        # there would go missing in exactly the setups where the emission is unexplained.
        log_emission_shape(self._handler_name, content, response.completion_tokens)

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
            if response.tokens_per_second:
                logger.info(
                    "%s LLM throughput: %.1f t/s (%s tokens)",
                    self._handler_name,
                    response.tokens_per_second,
                    response.completion_tokens,
                )
            layers = PromptLayerMetadata(
                prompt_layer_set_id=f"{self._role}-cycle",
                layers=(
                    PromptLayer(layer_type="system", layer_id=f"{self._role}-system"),
                    PromptLayer(layer_type="user", layer_id=f"cycle-{self._capability_id}"),
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

        artifacts = self._build_artifacts_from_content(content)
        outputs = {
            "summary": f"[{self._role}] {prd_summary}",
            "role": self._role,
            "artifacts": artifacts,
            # #431: generated-vs-stored accounting — repair emissions route
            # through this base handle, and the repair path is where the
            # production exhibit burned its budget regenerating into a loss
            "emission_stats": emission_stats(len(content), artifacts),
            "prompt_provenance": provenance,
        }
        if not content.strip():
            # #998: an EMPTY emission on the generic path — which every repair handler
            # rides — carried no marker at all, so the correction loop could refund the
            # round (#1053) but never say what kind of nothing it was. Three of the
            # eleven repair rounds in the 1.6.3 set's reds were exactly this. Only
            # emptiness is flagged here: a document-producing handler legitimately
            # emits no fences, and that is not a failure of anything.
            from squadops.cycles.emission_integrity import no_fenced_blocks_failure

            outputs["emission_failure"] = no_fenced_blocks_failure(
                len(content),
                inputs.get("expected_artifacts"),
                completion_tokens=response.completion_tokens,
                completion_cap=chat_kwargs.get("max_tokens"),
            )

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

    def _resolve_artifact_content(
        self,
        inputs: dict[str, Any],
        filename_substring: str,
    ) -> str | None:
        """Resolve artifact content by filename substring from inputs."""
        contents = inputs.get("artifact_contents", {})
        for key, value in contents.items():
            if filename_substring in key:
                return value
        return None

    async def _resolve_with_vault_fallback(
        self,
        inputs: dict[str, Any],
        filename_substring: str,
    ) -> str | None:
        """Resolve artifact content with vault fallback (D3).

        Tries ``artifact_contents`` first, falls back to
        ``artifact_vault.retrieve()`` using ``artifact_refs`` when
        the content was not pre-resolved (e.g., 512KB limit exceeded).
        """
        result = self._resolve_artifact_content(inputs, filename_substring)
        if result is not None:
            return result

        vault = inputs.get("artifact_vault")
        refs = inputs.get("artifact_refs", [])
        if not vault or not refs:
            return None

        for ref_id in refs:
            try:
                ref, content_bytes = await vault.retrieve(ref_id)
                if filename_substring in ref.filename:
                    return content_bytes.decode(errors="replace")
            except Exception:
                logger.debug(
                    "Vault fallback: failed to retrieve %s",
                    ref_id,
                    exc_info=True,
                )
        return None

    # Prompt-layer naming for _record_generation; BuilderAssembleHandler
    # overrides with "assemble" (its layer set is {role}-assemble).
    _prompt_layer_kind = "build"

    def _record_generation(
        self,
        context: ExecutionContext,
        prompt: str,
        response: str,
        duration_ms: float,
        resolved_model: str | None = None,
        rendered: object | None = None,
        chat_response: ChatMessage | None = None,
        reasoning: str | None = None,
    ) -> None:
        """Record LLM generation for LangFuse tracing (SIP-0061).

        Every cycle handler routes here. GovernanceReviewHandler kept a private copy
        until 2026-08-16, justified by a call shape it no longer had — the note said it
        "has no ChatMessage", but its call site has held the response object since the
        streaming seam landed. The copy cost it token accounting, prompt-version
        linkage and the configurable layer kind, silently, on every governance
        generation. Add a keyword argument here rather than a second implementation.
        """
        if chat_response and chat_response.tokens_per_second:
            logger.info(
                "%s LLM throughput: %.1f t/s (%s tokens)",
                self._handler_name,
                chat_response.tokens_per_second,
                chat_response.completion_tokens,
            )
        llm_obs = getattr(context.ports, "llm_observability", None)
        if llm_obs and context.correlation_context:
            from squadops.telemetry.models import (
                PromptLayer,
                PromptLayerMetadata,
                build_generation_record,
            )

            gen_record = build_generation_record(
                model=resolved_model or context.ports.llm.default_model,
                prompt_text=prompt,
                response_text=response,
                latency_ms=duration_ms,
                usage=chat_response,
                prompt_name=getattr(rendered, "template_id", None),
                prompt_version=(
                    int(rendered.template_version)
                    if rendered and getattr(rendered, "template_version", None)
                    else None
                ),
                reasoning=reasoning,
            )
            layers = PromptLayerMetadata(
                prompt_layer_set_id=f"{self._role}-{self._prompt_layer_kind}",
                layers=(
                    PromptLayer(
                        layer_type="system",
                        layer_id=f"{self._role}-{self._prompt_layer_kind}-system",
                    ),
                    PromptLayer(
                        layer_type="user",
                        layer_id=f"{self._prompt_layer_kind}-{self._capability_id}",
                    ),
                ),
            )
            llm_obs.record_generation(context.correlation_context, gen_record, layers)
