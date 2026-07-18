"""DevelopmentDevelopHandler — build code generation (SIP-0068/0086).
Split from cycle_tasks.py (#152).
"""

from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING, Any

from squadops.capabilities.dev_capabilities import get_capability
from squadops.capabilities.handlers.base import (
    HandlerEvidence,
    HandlerResult,
)
from squadops.capabilities.handlers.prompt_guard import _guard_prompt_size
from squadops.llm.exceptions import LLMError
from squadops.llm.models import ChatMessage

if TYPE_CHECKING:
    from squadops.capabilities.handlers.context import ExecutionContext

from squadops.capabilities.handlers.cycle.base import _CycleTaskHandler
from squadops.capabilities.handlers.cycle.validation import (
    ValidationResult,
    _classify_file,
    _detect_expected_layers,
    _detect_stubs,
    _estimate_min_artifacts,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Build handlers (SIP-Enhanced-Agent-Build-Capabilities)
# ---------------------------------------------------------------------------


class DevelopmentDevelopHandler(_CycleTaskHandler):
    """Build handler: generates source code from implementation plan (D1, D8).

    Reads the implementation plan and strategy analysis from
    ``inputs["artifact_contents"]`` (pre-resolved by executor, D3)
    and instructs the LLM to produce runnable source files using
    tagged fenced code blocks.
    """

    _handler_name = "development_develop_handler"
    _capability_id = "development.develop"
    _role = "dev"
    _artifact_name = "build_output"  # overridden by multi-file output

    def validate_inputs(self, inputs: dict[str, Any], contract=None) -> list[str]:
        errors = super().validate_inputs(inputs, contract)
        # Build handlers require artifact_contents or artifact_vault for plan data
        if "artifact_contents" not in inputs and "artifact_vault" not in inputs:
            errors.append("'artifact_contents' or 'artifact_vault' is required for build tasks")
        return errors

    async def _validate_output(
        self,
        inputs: dict[str, Any],
        artifacts: list[dict],
        *,
        typed_error_counts: dict[str, int] | None = None,
    ) -> ValidationResult:
        """Validate dev handler output (SIP-0086 §6.3, SIP-0092 M1.3).

        Two modes: focused (manifest-driven) and legacy (monolithic).
        See SIP §6.3.1 and §6.3.2 for the distinction. Focused mode now
        evaluates typed acceptance criteria (M1.3) — see ``_validate_focused``.
        """
        if inputs.get("subtask_focus") is not None:
            return await self._validate_focused(
                inputs, artifacts, typed_error_counts=typed_error_counts
            )
        return self._validate_monolithic(inputs, artifacts)

    async def _validate_focused(
        self,
        inputs: dict[str, Any],
        artifacts: list[dict],
        *,
        typed_error_counts: dict[str, int] | None = None,
    ) -> ValidationResult:
        """Focused-task validation: strict, artifact-specific (SIP §6.3.1).

        FC1 (expected artifacts) and FC2 (non-stub) are unchanged. FC3 was
        previously informational ("included_in_evidence"); SIP-0092 M1.3
        replaces it with typed-check evaluation per RC-9 — severity AND
        status are independent dimensions, only ``severity=error`` AND
        ``status ∈ {failed, error}`` blocks validation.
        """
        if typed_error_counts is None:
            typed_error_counts = {}

        checks: list[dict] = []
        missing: list[str] = []
        artifact_names = [a.get("name", "") for a in artifacts]

        # FC1: Expected artifacts present (required gate)
        expected = inputs.get("expected_artifacts", [])
        missing_files = [f for f in expected if f not in artifact_names]
        checks.append(
            {
                "check": "expected_artifacts",
                "expected": expected,
                "present": [f for f in expected if f in artifact_names],
                "missing": missing_files,
                "passed": len(missing_files) == 0,
            }
        )
        if missing_files:
            missing.extend(f"file:{f}" for f in missing_files)

        # FC2: Non-stub files (required gate)
        stubs = _detect_stubs(artifacts)
        checks.append(
            {
                "check": "non_stub_files",
                "stubs_found": stubs,
                "passed": len(stubs) == 0,
            }
        )

        # FC3 (SIP-0092 M1.3): Typed acceptance criteria evaluation.
        await self._evaluate_typed_acceptance(
            inputs, artifacts, checks, missing, typed_error_counts
        )

        passed = all(c.get("passed", True) for c in checks) and not missing
        passed_count = sum(1 for c in checks if c.get("passed", True))
        coverage = passed_count / len(checks) if checks else 1.0

        summary_parts = []
        if missing_files:
            summary_parts.append(f"Missing files: {', '.join(missing_files)}")
        if stubs:
            summary_parts.append(f"Stub files: {', '.join(stubs)}")
        typed_failed = [
            c
            for c in checks
            if c.get("check", "").startswith("acceptance:")
            and c.get("status") in {"failed", "error"}
        ]
        if typed_failed:
            summary_parts.append(
                f"Typed checks failed: {len(typed_failed)} of {sum(1 for c in checks if c.get('check', '').startswith('acceptance:'))}"
            )

        # Issue #83: emit a single summary line per focused validation so
        # operators can see at-a-glance whether M1.3 ran and what it found.
        acceptance_checks = [c for c in checks if c.get("check", "").startswith("acceptance:")]
        if acceptance_checks:
            ac_passed = sum(1 for c in acceptance_checks if c.get("passed", False))
            logger.info(
                "typed_acceptance_summary subtask=%s evaluated=%d passed=%d blocking_failures=%d "
                "overall_passed=%s",
                inputs.get("subtask_index"),
                len(acceptance_checks),
                ac_passed,
                len(typed_failed),
                passed,
            )

        return ValidationResult(
            passed=passed,
            checks=checks,
            missing_components=missing,
            coverage_ratio=coverage,
            summary="; ".join(summary_parts) or "All checks passed",
        )

    # SIP-0092 M1.3 typed-acceptance evaluation is inherited from
    # _CycleTaskHandler (#419/#420) — one seam for every cycle handler
    # whose plan task carries typed acceptance criteria.

    def _validate_monolithic(
        self,
        inputs: dict[str, Any],
        artifacts: list[dict],
    ) -> ValidationResult:
        """Legacy monolithic validation: coarse heuristic (SIP §6.3.2).

        Designed to catch obvious incompleteness, not certify completeness.
        """
        prd = inputs.get("prd", "")
        if not prd:
            return ValidationResult(passed=True, summary="No PRD, skipping validation")

        checks: list[dict] = []
        missing: list[str] = []
        artifact_names = [a.get("name", "") for a in artifacts]

        # C1: Stack coverage heuristic
        expected_layers = _detect_expected_layers(prd)
        present_layers: set[str] = set()
        for name in artifact_names:
            for layer, exts in expected_layers.items():
                if any(name.endswith(ext) for ext in exts):
                    present_layers.add(layer)
        missing_layers = set(expected_layers.keys()) - present_layers
        if missing_layers:
            missing.extend(f"stack_layer:{layer}" for layer in missing_layers)
        checks.append(
            {
                "check": "stack_coverage_heuristic",
                "expected": list(expected_layers.keys()),
                "present": list(present_layers),
                "missing": list(missing_layers),
                "passed": len(missing_layers) == 0,
            }
        )

        # C2: Artifact count heuristic
        min_artifacts = _estimate_min_artifacts(prd)
        checks.append(
            {
                "check": "artifact_count_heuristic",
                "expected_min": min_artifacts,
                "actual": len(artifacts),
                "passed": len(artifacts) >= min_artifacts,
            }
        )

        # C3: Non-stub files
        stubs = _detect_stubs(artifacts)
        checks.append(
            {
                "check": "non_stub_files",
                "stubs_found": stubs,
                "passed": len(stubs) == 0,
            }
        )

        passed = all(c["passed"] for c in checks)
        passed_count = sum(1 for c in checks if c["passed"])
        coverage = passed_count / len(checks) if checks else 1.0

        summary_parts = []
        if missing_layers:
            summary_parts.append(f"Missing stack layers: {', '.join(missing_layers)}")
        if len(artifacts) < min_artifacts:
            summary_parts.append(f"Only {len(artifacts)} artifacts, expected >= {min_artifacts}")
        if stubs:
            summary_parts.append(f"Stub files: {', '.join(stubs)}")

        return ValidationResult(
            passed=passed,
            checks=checks,
            missing_components=missing,
            coverage_ratio=coverage,
            summary="; ".join(summary_parts) or "All checks passed",
        )

    def _build_user_prompt(
        self,
        prd: str,
        prior_outputs: dict[str, Any] | None,
        impl_plan: str | None = None,
        strategy: str | None = None,
    ) -> str:
        """Build prompt with PRD + plan artifacts for code generation."""
        capability = get_capability(self._resolved_config.get("dev_capability", "python_cli"))

        parts = [f"## Product Requirements Document\n\n{prd}"]

        if impl_plan:
            parts.append(f"\n\n## Implementation Plan\n\n{impl_plan}")

        if strategy:
            parts.append(f"\n\n## Strategy Analysis\n\n{strategy}")

        parts.append(capability.file_structure_guidance)
        parts.append(f"\n\nTarget file structure:\n{capability.example_structure}")

        # Prior analysis last — prompt guard truncates from this heading onward
        if prior_outputs:
            parts.append("\n\n## Prior Analysis from Upstream Roles\n")
            for role, summary in prior_outputs.items():
                parts.append(f"### {role}\n{summary}\n")

        return "\n".join(parts)

    def _build_focused_prompt(self, inputs: dict[str, Any]) -> str:
        """Build a focused prompt for manifest-driven subtasks (SIP-0086 §6.1.5).

        RC-6: When subtask_focus is present, this path is used exclusively.
        The legacy monolithic prompt path is NOT used.
        """
        prd = inputs.get("prd", "")
        focus = inputs["subtask_focus"]
        description = inputs.get("subtask_description", "")
        expected_files = inputs.get("expected_artifacts", [])
        acceptance_criteria = inputs.get("acceptance_criteria", [])
        artifact_contents = inputs.get("artifact_contents", {})

        parts = [f"## Build Task: {focus}\n\n{description}\n"]

        parts.append("### Expected Output Files\n")
        parts.extend(f"- `{f}`\n" for f in expected_files)

        if acceptance_criteria:
            parts.append("\n### Acceptance Criteria\n")
            parts.extend(f"- {c}\n" for c in acceptance_criteria)

        parts.append(f"\n### Context\nPRD:\n{prd}\n")

        if artifact_contents:
            parts.append("\n### Prior Artifacts (already built — do not reproduce)\n")
            for name, content in artifact_contents.items():
                parts.append(f"**{name}:**\n```\n{content}\n```\n")

        parts.append(
            "\nProduce ONLY the files listed in Expected Output Files. "
            "Use fenced code blocks with ```language:path/to/file``` format. "
            "Do not reproduce files from prior artifacts."
        )
        return "".join(parts)

    async def handle(
        self,
        context: ExecutionContext,
        inputs: dict[str, Any],
    ) -> HandlerResult:
        from squadops.capabilities.handlers.fenced_parser import extract_fenced_files

        start_time = time.perf_counter()

        # D11: store resolved_config for use by _build_user_prompt()
        self._resolved_config = inputs.get("resolved_config", {})

        prd = inputs.get("prd", "")
        prior_outputs = inputs.get("prior_outputs")

        # SIP-0086 RC-6: focused prompt path for manifest-driven subtasks
        if inputs.get("subtask_focus") is not None:
            user_prompt = self._build_focused_prompt(inputs)
            rendered = None
            try:
                capability = get_capability(
                    self._resolved_config.get("dev_capability", "python_cli")
                )
            except ValueError as exc:
                return self._fail_result(start_time, inputs, str(exc))
        else:
            # Legacy monolithic prompt path (unchanged)

            # Resolve capability (fail fast on unknown dev_capability)
            try:
                capability = get_capability(
                    self._resolved_config.get("dev_capability", "python_cli")
                )
            except ValueError as exc:
                return self._fail_result(start_time, inputs, str(exc))

            # Resolve plan artifacts with vault fallback (D3)
            impl_plan = await self._resolve_with_vault_fallback(
                inputs,
                "implementation_plan",
            )
            strategy = await self._resolve_with_vault_fallback(inputs, "strategy_analysis")

            # Check required artifacts (fail only when vault was available but empty)
            if impl_plan is None and inputs.get("artifact_vault") is not None:
                return self._fail_result(
                    start_time, inputs, "Required plan artifacts not available"
                )

            rendered, user_prompt = await self._build_dev_prompt(
                context,
                prd,
                prior_outputs,
                capability,
                impl_plan,
                strategy,
            )

        assembled = context.ports.prompt_service.get_system_prompt(self._role)
        system_prompt = assembled.content + "\n\n" + capability.system_prompt_supplement

        # Resolve model, token budget, and prompt guard
        model_name, max_tokens, context_window = self._resolve_model_budget(
            inputs, capability.max_completion_tokens, context.ports.llm.default_model
        )
        agent_overrides = inputs.get("agent_config_overrides", {})
        agent_model = inputs.get("agent_model") or None

        # SIP-0073: guard prompt size against context window
        try:
            user_prompt = _guard_prompt_size(
                system_prompt,
                user_prompt,
                max_tokens,
                context_window,
            )
        except ValueError as exc:
            return self._fail_result(start_time, inputs, str(exc))

        # SIP-0073: resolve effective timeout (D6)
        generation_timeout = self._resolved_config.get("generation_timeout", 300)

        # SIP-0075 §3.3: build chat kwargs from overrides
        chat_kwargs: dict[str, Any] = {
            "max_tokens": max_tokens,
            "timeout_seconds": generation_timeout,
        }
        if agent_model:
            chat_kwargs["model"] = agent_model
        if "temperature" in agent_overrides:
            chat_kwargs["temperature"] = agent_overrides["temperature"]

        messages = [
            ChatMessage(role="system", content=system_prompt),
            ChatMessage(role="user", content=user_prompt),
        ]

        try:
            response = await context.ports.llm.chat_stream_with_usage(messages, **chat_kwargs)
        except LLMError as exc:
            logger.warning("LLM call failed for %s: %s", self._handler_name, exc)
            return self._fail_result(start_time, inputs, str(exc))

        content = response.content
        llm_duration_ms = (time.perf_counter() - start_time) * 1000

        # Record LLM generation for LangFuse tracing
        self._record_generation(
            context,
            user_prompt,
            content,
            llm_duration_ms,
            model_name,
            rendered=rendered,
            chat_response=response,
        )

        # Parse fenced code blocks
        extracted = extract_fenced_files(content)

        if not extracted:
            self._log_no_fenced_blocks(content)
            return self._fail_result(
                start_time,
                inputs,
                "No valid fenced code blocks found",
                outputs={
                    "artifacts": [
                        {
                            "name": "build_warnings.md",
                            "content": content,
                            "media_type": "text/markdown",
                            "type": "document",
                        },
                    ],
                },
            )

        # Build artifact list from extracted files
        artifacts = []
        for file_rec in extracted:
            artifact_type, media_type = _classify_file(file_rec["filename"])
            artifacts.append(
                {
                    "name": file_rec["filename"],
                    "content": file_rec["content"],
                    "media_type": media_type,
                    "type": artifact_type,
                }
            )

        # SIP-0086: Output validation + self-evaluation + outcome classification
        resolved_config = inputs.get("resolved_config", {})
        evidence_extra: dict[str, Any] = {}

        if resolved_config.get("output_validation", False):
            # SIP-0092 M1.3 / RC-9b: per-criterion error counts persist across
            # self-eval passes within this handle() invocation, then are dropped.
            typed_error_counts: dict[str, int] = {}
            validation = await self._validate_output(
                inputs, artifacts, typed_error_counts=typed_error_counts
            )

            # Self-evaluation loop (Phase 7)
            if not validation.passed:
                max_self_eval = resolved_config.get("max_self_eval_passes", 1)
                self_eval_count = 0

                while not validation.passed and self_eval_count < max_self_eval:
                    self_eval_count += 1
                    followup_prompt = self._build_self_eval_prompt(validation, artifacts)

                    try:
                        followup_response = await context.ports.llm.chat_stream_with_usage(
                            [
                                ChatMessage(role="system", content=system_prompt),
                                ChatMessage(role="user", content=user_prompt),
                                ChatMessage(role="assistant", content=content),
                                ChatMessage(role="user", content=followup_prompt),
                            ],
                            **chat_kwargs,
                        )
                    except LLMError as exc:
                        logger.warning(
                            "Self-eval LLM call failed for %s: %s",
                            self._handler_name,
                            exc,
                        )
                        break

                    new_extracted = extract_fenced_files(followup_response.content)
                    new_artifacts = [
                        {
                            "name": f["filename"],
                            "content": f["content"],
                            "media_type": _classify_file(f["filename"])[1],
                            "type": _classify_file(f["filename"])[0],
                        }
                        for f in new_extracted
                    ]
                    artifacts = self._merge_artifacts(artifacts, new_artifacts, evidence_extra)

                    # RC-7: validate merged artifact set
                    validation = await self._validate_output(
                        inputs, artifacts, typed_error_counts=typed_error_counts
                    )

                evidence_extra["self_eval_passes"] = self_eval_count

            evidence_extra["validation_result"] = {
                "passed": validation.passed,
                "checks": validation.checks,
                "missing_components": validation.missing_components,
                "coverage_ratio": validation.coverage_ratio,
                "summary": validation.summary,
            }

            # Issue #114: emit per-task typed-check evaluation artifact when
            # any typed checks ran, so the SIP-0092 gate evaluator can
            # measure C1 (evaluator-error rate) and C2 (typed-check trips).
            tce_artifact = self._build_typed_check_evaluation_artifact(
                validation.checks,
                inputs.get("subtask_index"),
                self._capability_id,
            )
            if tce_artifact is not None:
                artifacts.append(tce_artifact)
        else:
            validation = ValidationResult(passed=True, summary="Validation disabled")

        # SIP-0084 §10: build prompt provenance for artifact traceability
        provenance: dict[str, Any] = {
            "system_prompt_bundle_hash": assembled.assembly_hash,
        }
        if rendered is not None:
            provenance["request_template_id"] = rendered.template_id
            provenance["request_template_version"] = rendered.template_version
            provenance["request_render_hash"] = rendered.render_hash
            provenance["prompt_environment"] = "production"

        outputs: dict[str, Any] = {
            "summary": f"[dev] Generated {len(artifacts)} source file(s)",
            "role": self._role,
            "artifacts": artifacts,
            "prompt_provenance": provenance,
        }

        # Phase 6: Outcome classification
        if validation.passed:
            from squadops.cycles.task_outcome import TaskOutcome

            outputs["outcome_class"] = TaskOutcome.SUCCESS
        else:
            from squadops.cycles.task_outcome import (
                FailureClassification,
                TaskOutcome,
            )

            outputs["outcome_class"] = TaskOutcome.SEMANTIC_FAILURE
            outputs["failure_classification"] = FailureClassification.WORK_PRODUCT
            outputs["validation_result"] = evidence_extra.get("validation_result", {})

        duration_ms = (time.perf_counter() - start_time) * 1000
        evidence = HandlerEvidence.create(
            handler_name=self._handler_name,
            capability_id=self._capability_id,
            duration_ms=duration_ms,
            inputs_hash=self._hash_dict(inputs),
            outputs_hash=self._hash_dict(outputs),
            metadata=evidence_extra if evidence_extra else None,
        )

        return HandlerResult(
            success=validation.passed,
            outputs=outputs,
            _evidence=evidence,
            error=validation.summary if not validation.passed else None,
        )

    async def _build_dev_prompt(
        self,
        context: ExecutionContext,
        prd: str,
        prior_outputs: dict | None,
        capability: Any,
        impl_plan: str | None,
        strategy: str | None,
    ) -> tuple[Any, str]:
        """Build the dev prompt via renderer or fallback. Returns (rendered, user_prompt)."""
        rendered = None
        renderer = getattr(context.ports, "request_renderer", None)
        if renderer is not None:
            variables: dict[str, str] = {
                "prd": prd,
                "file_structure_guidance": capability.file_structure_guidance,
                "example_structure": capability.example_structure,
            }
            if impl_plan:
                variables["impl_plan"] = f"\n\n## Implementation Plan\n\n{impl_plan}"
            if strategy:
                variables["strategy"] = f"\n\n## Strategy Analysis\n\n{strategy}"
            variables["prior_outputs"] = self._format_prior_outputs(prior_outputs)
            # SIP-0099 99.3 (part 2): on a scaffoldable stack a walking skeleton was
            # seeded into the workspace (part 1), so instruct the dev to FILL the fixed
            # slots rather than rewire. Data-driven — "" for a non-scaffolded cycle.
            fill_only = await self._fill_only_section(renderer)
            if fill_only:
                variables["fill_only_section"] = fill_only
            rendered = await renderer.render(
                "request.development_develop.code_generate",
                variables,
            )
            return rendered, rendered.content

        user_prompt = self._build_user_prompt(
            prd,
            prior_outputs,
            impl_plan=impl_plan,
            strategy=strategy,
        )
        return None, user_prompt

    async def _fill_only_section(self, renderer: Any) -> str:
        """The fill-only instruction, or "" (SIP-0099 99.3 part 2).

        Non-empty only on a scaffoldable stack — a walking skeleton has been seeded into
        the workspace (part 1), so the dev fills fixed slots instead of rewiring. The
        instruction lives in a managed prompt asset, not an inline literal (CLAUDE.md
        #448). Frozen-surface *enforcement* is SIP-0098's `frozen:` contract, not here.
        """
        from squadops.capabilities.scaffold import is_scaffoldable_stack

        stack = str(self._resolved_config.get("build_profile") or "")
        if not is_scaffoldable_stack(stack):
            return ""
        rendered = await renderer.render(
            "request.development_develop_fill_only_appendix", {"stack": stack}
        )
        return rendered.content
