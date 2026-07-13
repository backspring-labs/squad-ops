"""QATestHandler — test generation + execution against build artifacts (D1).
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
from squadops.cycles.check_registry import CHECK_FRONTEND_BUILD
from squadops.cycles.verification_integrity import NotExecutedReason
from squadops.llm.exceptions import LLMError
from squadops.llm.models import ChatMessage

if TYPE_CHECKING:
    from squadops.capabilities.handlers.context import ExecutionContext

from squadops.capabilities.handlers.cycle.base import _CycleTaskHandler
from squadops.capabilities.handlers.cycle.validation import (
    _STUB_THRESHOLD_BYTES,
    ValidationResult,
    _classify_file,
    _detect_stubs,
    _is_test_file,
)

logger = logging.getLogger(__name__)


def _frontend_skip_reason(error: str) -> str:
    """Map a frontend-build skip error to a §7 not-executed reason (#407).

    ``run_frontend_build`` skips (``ran=False``) with the cause in ``error``: an
    absent Node toolchain (``npm/npx not found``) is ``missing_tooling`` — the
    #306 case a required frontend_build must block on; anything else (no frontend
    source) is ``subject_missing``.
    """
    e = (error or "").lower()
    if "not found" in e or "not installed" in e:
        return NotExecutedReason.MISSING_TOOLING
    return NotExecutedReason.SUBJECT_MISSING


class QATestHandler(_CycleTaskHandler):
    """Build handler: generates test files from validation plan + source (D1).

    Reads the validation plan and source artifacts from
    ``inputs["artifact_contents"]`` and instructs the LLM to produce
    pytest test files.
    """

    _handler_name = "qa_test_handler"
    _capability_id = "qa.test"
    _role = "qa"
    _artifact_name = "test_output"  # overridden by multi-file output

    def validate_inputs(self, inputs: dict[str, Any], contract=None) -> list[str]:
        errors = super().validate_inputs(inputs, contract)
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
        """Validate QA handler output (SIP-0086 §6.4).

        SIP-0092 M1.3: signature is async to match the base class. Typed
        acceptance evaluation in the QA path is out of scope for M1.3 —
        the SIP focuses on the dev FC3 site. The ``typed_error_counts``
        kwarg is accepted for caller compatibility but unused here.
        """
        del typed_error_counts  # accepted for caller compat; not used in QA
        checks: list[dict] = []
        missing: list[str] = []

        if inputs.get("subtask_focus") is not None:
            # Focused mode: check expected artifacts
            expected = inputs.get("expected_artifacts", [])
            artifact_names = [a.get("name", "") for a in artifacts]
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
        else:
            # Legacy mode: at least one test file with content
            test_files = [
                a
                for a in artifacts
                if "test" in a.get("name", "").lower()
                and len(a.get("content", "")) > _STUB_THRESHOLD_BYTES
            ]
            checks.append(
                {
                    "check": "test_file_presence",
                    "test_files_found": len(test_files),
                    "passed": len(test_files) > 0,
                }
            )
            if not test_files:
                missing.append("test_files")

        # Non-stub check (both modes)
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
        if missing:
            summary_parts.append(f"Missing: {', '.join(missing)}")
        if stubs:
            summary_parts.append(f"Stub files: {', '.join(stubs)}")

        return ValidationResult(
            passed=passed,
            checks=checks,
            missing_components=missing,
            coverage_ratio=coverage,
            summary="; ".join(summary_parts) or "All checks passed",
        )

    def _get_source_artifacts(self, inputs: dict[str, Any]) -> dict[str, str]:
        """Get source artifacts filtered by capability (D4, D9).

        Includes source files (by ``source_filter`` extension, non-test) AND the
        capability's ``build_support_files`` (config/entry files matched by
        basename — package.json, vite.config.js, index.html, …). Without the
        support files the QA build/test workspace can't build the deliverable and
        the frontend build check (#290) + vitest skip on "no package.json" (#296).
        """
        capability = get_capability(
            inputs.get("resolved_config", {}).get("dev_capability", "python_cli")
        )
        contents = inputs.get("artifact_contents", {})
        support = set(getattr(capability, "build_support_files", ()))
        sources = {}
        for key, value in contents.items():
            basename = key.replace("\\", "/").rsplit("/", 1)[-1]
            is_source = any(
                key.endswith(ext) for ext in capability.source_filter
            ) and not _is_test_file(key, capability.test_file_patterns)
            if is_source or basename in support:
                sources[key] = value
        return sources

    @staticmethod
    def _fence_lang(path: str) -> str:
        """Return the appropriate code fence language for a file path."""
        if path.endswith((".js", ".jsx", ".mjs")):
            return "javascript"
        if path.endswith((".ts", ".tsx")):
            return "typescript"
        return "python"

    def _build_user_prompt(
        self,
        prd: str,
        prior_outputs: dict[str, Any] | None,
        val_plan: str | None = None,
        sources: dict[str, str] | None = None,
        capability_name: str = "python_cli",
    ) -> str:
        """Build prompt with validation plan + source code for test generation."""
        capability = get_capability(capability_name)
        parts = [f"## Product Requirements Document\n\n{prd}"]

        if val_plan:
            parts.append(f"\n\n## Validation Plan\n\n{val_plan}")

        if sources:
            parts.append("\n\n## Source Files to Test\n")
            for path, code in sources.items():
                lang = self._fence_lang(path)
                parts.append(f"\n### {path}\n```{lang}\n{code}\n```\n")

        parts.append(capability.test_prompt_supplement)

        # Prior analysis last — prompt guard truncates from this heading onward
        if prior_outputs:
            parts.append("\n\n## Prior Analysis from Upstream Roles\n")
            for role, summary in prior_outputs.items():
                parts.append(f"### {role}\n{summary}\n")

        return "\n".join(parts)

    @staticmethod
    async def _run_test_suite(
        capability: Any,
        sources: dict[str, str],
        extracted: list[dict],
    ) -> tuple[Any, dict]:
        """Run the build-validation suite and return (result, report_artifact).

        Framework dispatch (pytest/vitest/both) and the #276 frontend build check
        live in ``test_runner`` (which owns test-framework knowledge). This handler
        stays framework-agnostic — it passes ``capability.test_framework`` through
        and reads only the generic ``RunTestsResult``.
        """
        from squadops.capabilities.handlers.test_runner import run_build_validation

        source_file_records = [{"path": p, "content": c} for p, c in sources.items()]
        test_file_records = [
            {"path": rec["filename"], "content": rec["content"]} for rec in extracted
        ]

        test_result = await run_build_validation(
            capability.test_framework,
            source_file_records,
            test_file_records,
            timeout_seconds=capability.test_timeout_seconds,
        )

        report_lines = [
            "# Test Execution Report\n",
            f"**Result:** {test_result.summary}\n",
            f"**Exit code:** {test_result.exit_code}\n",
            f"**Test files:** {test_result.test_file_count}\n",
            f"**Source files:** {test_result.source_file_count}\n",
        ]
        if test_result.stdout:
            report_lines.append(f"\n## stdout\n\n```\n{test_result.stdout}\n```\n")
        if test_result.stderr:
            report_lines.append(f"\n## stderr\n\n```\n{test_result.stderr}\n```\n")
        if test_result.error:
            report_lines.append(f"\n## Error\n\n{test_result.error}\n")

        report_artifact = {
            "name": "test_report.md",
            "content": "\n".join(report_lines),
            "media_type": "text/markdown",
            "type": "test_report",
        }
        return test_result, report_artifact

    def _build_focused_prompt(self, inputs: dict[str, Any]) -> str:
        """Build a focused prompt for manifest-driven QA subtasks (SIP-0086).

        RC-6: When subtask_focus is present, this path is used exclusively.
        """
        prd = inputs.get("prd", "")
        focus = inputs["subtask_focus"]
        description = inputs.get("subtask_description", "")
        expected_files = inputs.get("expected_artifacts", [])
        acceptance_criteria = inputs.get("acceptance_criteria", [])
        artifact_contents = inputs.get("artifact_contents", {})

        parts = [f"## QA Task: {focus}\n\n{description}\n"]

        parts.append("### Expected Output Files\n")
        parts.extend(f"- `{f}`\n" for f in expected_files)

        if acceptance_criteria:
            parts.append("\n### Acceptance Criteria\n")
            parts.extend(f"- {c}\n" for c in acceptance_criteria)

        parts.append(f"\n### Context\nPRD:\n{prd}\n")

        if artifact_contents:
            parts.append("\n### Source Artifacts to Test\n")
            for name, content in artifact_contents.items():
                lang = self._fence_lang(name)
                parts.append(f"**{name}:**\n```{lang}\n{content}\n```\n")

        parts.append(
            "\nProduce ONLY the files listed in Expected Output Files. "
            "Use fenced code blocks with ```language:path/to/file``` format. "
            "Do not reproduce source artifacts."
        )
        return "".join(parts)

    async def handle(
        self,
        context: ExecutionContext,
        inputs: dict[str, Any],
    ) -> HandlerResult:
        from squadops.capabilities.handlers.fenced_parser import extract_fenced_files

        start_time = time.perf_counter()

        prd = inputs.get("prd", "")
        prior_outputs = inputs.get("prior_outputs")
        resolved_config = inputs.get("resolved_config", {})
        capability_name = resolved_config.get("dev_capability", "python_cli")

        # Resolve capability (fail fast on unknown dev_capability)
        try:
            capability = get_capability(capability_name)
        except ValueError as exc:
            return self._fail_result(start_time, inputs, str(exc))

        # SIP-0086 RC-6: focused prompt path for manifest-driven subtasks
        if inputs.get("subtask_focus") is not None:
            user_prompt = self._build_focused_prompt(inputs)
            rendered = None
            sources = self._get_source_artifacts(inputs)
        else:
            # Legacy monolithic prompt path (unchanged)

            # Resolve plan artifacts with vault fallback (D3)
            val_plan = await self._resolve_with_vault_fallback(inputs, "validation_plan")
            sources = self._get_source_artifacts(inputs)

            # Check required artifacts (fail only when vault was available but empty)
            if val_plan is None and inputs.get("artifact_vault") is not None:
                return self._fail_result(
                    start_time, inputs, "Required plan artifacts not available"
                )

            rendered, user_prompt = await self._build_qa_prompt(
                context,
                prd,
                prior_outputs,
                capability,
                val_plan,
                sources,
                capability_name,
            )

        assembled = context.ports.prompt_service.get_system_prompt(self._role)
        system_prompt = assembled.content

        # Resolve model, token budget, and prompt guard
        model_name, max_tokens, context_window = self._resolve_model_budget(
            inputs, capability.max_completion_tokens, context.ports.llm.default_model
        )

        try:
            user_prompt = _guard_prompt_size(
                system_prompt,
                user_prompt,
                max_tokens,
                context_window,
            )
        except ValueError as exc:
            return self._fail_result(start_time, inputs, str(exc))

        generation_timeout = resolved_config.get("generation_timeout", 300)
        agent_overrides = inputs.get("agent_config_overrides", {})
        agent_model = inputs.get("agent_model") or None

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
        self._record_generation(
            context,
            user_prompt,
            content,
            llm_duration_ms,
            model_name,
            rendered=rendered,
            chat_response=response,
        )

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
                        }
                    ]
                },
            )

        artifacts = [
            {
                "name": f["filename"],
                "content": f["content"],
                "media_type": _classify_file(f["filename"])[1],
                "type": "test",
            }
            for f in extracted
        ]

        # SIP-0086: Output validation + self-evaluation
        evidence_extra: dict[str, Any] = {}
        output_validation_enabled = resolved_config.get("output_validation", False)

        if output_validation_enabled:
            validation = await self._validate_output(inputs, artifacts)

            # Self-evaluation loop
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
                            "type": "test",
                        }
                        for f in new_extracted
                    ]
                    artifacts = self._merge_artifacts(artifacts, new_artifacts, evidence_extra)
                    validation = await self._validate_output(inputs, artifacts)

                evidence_extra["self_eval_passes"] = self_eval_count
        else:
            validation = ValidationResult(passed=True, summary="Validation disabled")

        # Run generated tests and build report
        test_result, test_report_artifact = await self._run_test_suite(
            capability, sources, extracted
        )
        artifacts.append(test_report_artifact)

        # Fold test-execution outcome into validation. The qa.test handler's
        # objective is "produce tests that pass against the dev artifacts";
        # artifacts-present-and-non-stub is necessary but not sufficient. A
        # passing test file count with exit_code != 0 (e.g., import errors
        # causing pytest to collect 0 tests) must surface as SEMANTIC_FAILURE
        # so the correction protocol activates.
        if output_validation_enabled and not (test_result.executed and test_result.tests_passed):
            if test_result.executed:
                detail = f"tests_failed:exit_{test_result.exit_code}"
                fail_note = f"Tests failed (exit {test_result.exit_code})"
            else:
                reason = test_result.error or "runner_error"
                detail = f"tests_not_executed:{reason}"
                fail_note = f"Tests not executed: {reason}"

            validation.checks.append(
                {
                    "check": "tests_pass",
                    "executed": test_result.executed,
                    "exit_code": test_result.exit_code,
                    "tests_passed": test_result.tests_passed,
                    "passed": False,
                }
            )
            validation.passed = False
            validation.missing_components.append(detail)
            validation.summary = (
                fail_note
                if validation.summary in ("", "All checks passed")
                else f"{validation.summary}; {fail_note}"
            )
            if validation.checks:
                passed_count = sum(1 for c in validation.checks if c["passed"])
                validation.coverage_ratio = passed_count / len(validation.checks)

        if output_validation_enabled:
            # #276: a generated test that hides a broken entrypoint import behind
            # an ImportError fallback validates a stub app, not the deliverable —
            # so `tests_passed` above can be falsely green (the stub collects and
            # passes). Flag it so acceptance fails and the correction loop
            # regenerates the test against the real module.
            from squadops.capabilities.handlers.stub_detection import (
                detect_stub_fallback_tests,
            )

            stub_offenders = detect_stub_fallback_tests(artifacts)
            if stub_offenders:
                validation.checks.append(
                    {
                        "check": "no_stub_fallback_tests",
                        "offenders": stub_offenders,
                        "passed": False,
                    }
                )
                validation.passed = False
                validation.missing_components.append(
                    f"stub_fallback_tests:{','.join(stub_offenders)}"
                )
                note = (
                    "Generated test masks the real entrypoint behind an "
                    f"ImportError stub: {', '.join(stub_offenders)}"
                )
                validation.summary = (
                    note
                    if validation.summary in ("", "All checks passed")
                    else f"{validation.summary}; {note}"
                )
                passed_count = sum(1 for c in validation.checks if c["passed"])
                validation.coverage_ratio = passed_count / len(validation.checks)

            evidence_extra["validation_result"] = {
                "passed": validation.passed,
                "checks": validation.checks,
                "missing_components": validation.missing_components,
                "coverage_ratio": validation.coverage_ratio,
                "summary": validation.summary,
            }

            # Issue #114: emit per-task typed-check evaluation artifact for
            # the gate evaluator. Same shape/semantics as the dev handler.
            tce_artifact = self._build_typed_check_evaluation_artifact(
                validation.checks,
                inputs.get("subtask_index"),
                self._capability_id,
            )
            if tce_artifact is not None:
                artifacts.append(tce_artifact)

        if test_result.tests_passed:
            test_suffix = ", all tests passed"
        elif test_result.executed:
            test_suffix = f", tests failed (exit code {test_result.exit_code})"
        else:
            test_suffix = f", tests not run: {test_result.error}" if test_result.error else ""

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
            "summary": f"[qa] Generated {len(artifacts) - 1} test file(s){test_suffix}",
            "role": self._role,
            "artifacts": artifacts,
            "test_result": {
                "executed": test_result.executed,
                "exit_code": test_result.exit_code,
                "tests_passed": test_result.tests_passed,
                "test_file_count": test_result.test_file_count,
                "source_file_count": test_result.source_file_count,
                "summary": test_result.summary,
            },
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

        # #407: record the fullstack frontend build as a first-class SIP-0096
        # check on BOTH the pass and fail paths. run_build_validation folds a
        # frontend skip/failure into the combined result, so without this a
        # required frontend_build that never executed (Node absent, #306) would
        # read green — the SIP-0070 D13 false-green. A *passing* fullstack run
        # must record frontend_build=passed too, or requiring it would false-block.
        # Runs after the classification above so it isn't overwritten by the
        # failure-path validation_result assignment.
        fb = test_result.frontend_build
        if fb is not None:
            if fb.ran:
                fb_row: dict[str, Any] = {"check": CHECK_FRONTEND_BUILD, "passed": fb.ok}
            else:
                fb_row = {
                    "check": CHECK_FRONTEND_BUILD,
                    "executed": False,
                    "reason": _frontend_skip_reason(fb.error),
                }
            vr = outputs.setdefault("validation_result", {})
            vr.setdefault("checks", []).append(fb_row)

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

    async def _build_qa_prompt(
        self,
        context: ExecutionContext,
        prd: str,
        prior_outputs: dict | None,
        capability: Any,
        val_plan: str | None,
        sources: dict[str, str],
        capability_name: str,
    ) -> tuple[Any, str]:
        """Build the QA prompt via renderer or fallback. Returns (rendered, user_prompt)."""
        rendered = None
        renderer = getattr(context.ports, "request_renderer", None)
        if renderer is not None:
            variables: dict[str, str] = {
                "prd": prd,
                "test_supplement": capability.test_prompt_supplement,
            }
            if val_plan:
                variables["validation_plan"] = f"\n\n## Validation Plan\n\n{val_plan}"
            if sources:
                source_parts = ["\n\n## Source Files to Test\n"]
                for path, code in sources.items():
                    lang = self._fence_lang(path)
                    source_parts.append(f"\n### {path}\n```{lang}\n{code}\n```\n")
                variables["source_files"] = "\n".join(source_parts)
            variables["prior_outputs"] = self._format_prior_outputs(prior_outputs)
            rendered = await renderer.render(
                "request.qa_test.test_validate",
                variables,
            )
            return rendered, rendered.content

        user_prompt = self._build_user_prompt(
            prd,
            prior_outputs,
            val_plan=val_plan,
            sources=sources,
            capability_name=capability_name,
        )
        return None, user_prompt
