"""BuilderAssembleHandler — assembly into deployable artifacts (SIP-0071).
Split from cycle_tasks.py (#152).
"""

from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING, Any

from squadops.capabilities.handlers.base import (
    HandlerEvidence,
    HandlerResult,
)
from squadops.llm.exceptions import LLMError
from squadops.llm.models import ChatMessage

if TYPE_CHECKING:
    from squadops.capabilities.handlers.context import ExecutionContext

from squadops.capabilities.handlers.cycle.base import _CycleTaskHandler
from squadops.capabilities.handlers.cycle.validation import (
    _classify_file,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Builder build handler (SIP-0071)
# ---------------------------------------------------------------------------


class BuilderAssembleHandler(_CycleTaskHandler):
    """Assembly handler for dedicated builder role (SIP-0071).

    Takes source code produced by the dev role (from artifact_contents)
    and assembles it into deployable artifacts: packaging, entrypoints,
    Dockerfile, startup scripts, and qa_handoff.md.
    """

    _handler_name = "builder_assemble_handler"
    _capability_id = "builder.assemble"
    _role = "builder"
    _artifact_name = "build_output"
    _prompt_layer_kind = "assemble"

    def validate_inputs(self, inputs: dict[str, Any], contract=None) -> list[str]:
        errors = super().validate_inputs(inputs, contract)
        if "artifact_contents" not in inputs and "artifact_vault" not in inputs:
            errors.append("'artifact_contents' or 'artifact_vault' is required for assembly tasks")
        return errors

    @staticmethod
    def _validate_builder_output(
        extracted: list[dict],
        profile: Any,
        required_sections: tuple[str, ...],
        task_required_files: tuple[str, ...] | list[str] | None = None,
    ) -> str | None:
        """Validate builder output: qa_handoff, sections, required files.

        Issue #107: when `task_required_files` is provided and non-empty,
        the active task's expected_artifacts are the source of truth for
        what must be emitted (framing decomposed builder work and the
        active task only owns a subset of the profile's defaults). When
        omitted/empty, falls back to `profile.required_files` to preserve
        single-task builder behavior. The qa_handoff section check is
        skipped when `qa_handoff.md` is not in scope, otherwise the builder
        role would be forced to emit a full qa_handoff in every builder
        task even if framing routed it to a different task.

        Returns an error message string if validation fails, None if OK.
        """
        import os

        effective_required = (
            tuple(task_required_files) if task_required_files else profile.required_files
        )

        extracted_basenames = {os.path.basename(f["filename"]) for f in extracted}

        if "qa_handoff.md" in effective_required:
            qa_handoff_content = None
            for file_rec in extracted:
                if os.path.basename(file_rec["filename"]) == "qa_handoff.md":
                    qa_handoff_content = file_rec["content"]
                    break

            if qa_handoff_content is None:
                return "qa_handoff.md not found in builder output"

            qa_lower = qa_handoff_content.lower()
            _SECTION_KEYWORDS: dict[str, tuple[str, ...]] = {
                "## How to Run": ("how to run", "running", "## run"),
                "## How to Test": ("how to test", "testing", "## test"),
                "## Expected Behavior": ("expected behavior", "expected output", "## expected"),
            }
            missing_sections = []
            for section in required_sections:
                keywords = _SECTION_KEYWORDS.get(section, (section.lower(),))
                if not any(kw in qa_lower for kw in keywords):
                    missing_sections.append(section)
            if missing_sections:
                return f"qa_handoff.md missing required sections: {missing_sections}"

        missing_files = [rf for rf in effective_required if rf not in extracted_basenames]
        if missing_files:
            return f"Required deployment files missing: {missing_files}"

        return None

    @staticmethod
    def _resolve_task_tags(profile: Any, resolved_config: dict) -> dict[str, str]:
        """Merge profile default tags with experiment_context overrides."""
        task_tags = dict(profile.default_task_tags)
        experiment_ctx = resolved_config.get("experiment_context", {})
        if isinstance(experiment_ctx, dict):
            for key, value in experiment_ctx.items():
                if isinstance(value, str):
                    task_tags[key] = value
                else:
                    logger.warning(
                        "Ignoring non-string tag %r=%r from experiment_context",
                        key,
                        value,
                    )
        return task_tags

    async def _build_assembly_prompt(
        self,
        context: ExecutionContext,
        prd: str,
        prior_outputs: dict | None,
        sources: dict[str, str],
        task_tags: dict[str, str],
    ) -> tuple[Any, str]:
        """Build the assembly prompt via renderer or fallback. Returns (rendered, user_prompt)."""
        rendered = None
        renderer = getattr(context.ports, "request_renderer", None)
        if renderer is not None:
            source_parts = []
            for path, code in sorted(sources.items()):
                source_parts.append(f"\n### {path}\n```\n{code}\n```\n")
            variables: dict[str, str] = {
                "prd": prd,
                "source_files": "\n".join(source_parts),
                "prior_outputs": self._format_prior_outputs(prior_outputs),
            }
            if task_tags:
                tag_parts = ["\n\n## Builder Tags\n"]
                for tag_key, tag_value in sorted(task_tags.items()):
                    tag_parts.append(f"- **{tag_key}**: {tag_value}")
                variables["task_tags"] = "\n".join(tag_parts)
            rendered = await renderer.render(
                "request.builder_assemble.build_assemble",
                variables,
            )
            return rendered, rendered.content

        parts = [f"## Product Requirements Document\n\n{prd}"]
        parts.append("\n\n## Source Files (from developer)\n")
        for path, code in sorted(sources.items()):
            parts.append(f"\n### {path}\n```\n{code}\n```\n")
        if prior_outputs:
            parts.append("\n\n## Prior Analysis from Upstream Roles\n")
            for role, summary in prior_outputs.items():
                parts.append(f"### {role}\n{summary}\n")
        if task_tags:
            parts.append("\n\n## Builder Tags\n")
            for tag_key, tag_value in sorted(task_tags.items()):
                parts.append(f"- **{tag_key}**: {tag_value}")
        # Issue #92: do NOT enumerate filenames here. The build profile's
        # `full_system_prompt` (composed from required_files/optional_files)
        # is the single source of truth for what the builder role must
        # produce. This fallback only carries the format/path rules that
        # are universal.
        parts.append(
            "\n\nYou are ASSEMBLING the source code above into a deployable package. "
            "Do NOT rewrite or regenerate the source code — it is already written. "
            "Your job is to add deployment and packaging artifacts.\n\n"
            "Use tagged fenced code blocks with the language and path "
            "separated by a colon, for example:\n"
            "```dockerfile:Dockerfile\n<content>\n```\n"
            "```markdown:qa_handoff.md\n<content>\n```\n\n"
            "File path rules:\n"
            "- File paths must use forward slashes, no colons, no spaces.\n"
            "- Do NOT re-emit source files that the developer already wrote.\n"
            "- Only emit NEW files needed for packaging and deployment.\n"
            "- The required and optional file list, plus qa_handoff.md required "
            "sections, is given in the system prompt — produce exactly that set."
        )
        return None, "\n".join(parts)

    @staticmethod
    def _dedup_and_classify(
        extracted: list[dict],
    ) -> tuple[list[dict], list[dict], str | None]:
        """Deduplicate by full path and classify files into artifacts.

        Returns (deduped_extracted, artifacts, qa_handoff_content).
        """
        import os

        seen_paths: dict[str, int] = {}
        for idx, file_rec in enumerate(extracted):
            seen_paths[file_rec["filename"]] = idx
        if len(seen_paths) < len(extracted):
            logger.info(
                "Builder output contained duplicate paths; deduplicating %d → %d files",
                len(extracted),
                len(seen_paths),
            )
            deduped_indices = sorted(seen_paths.values())
            extracted = [extracted[i] for i in deduped_indices]

        artifacts = []
        qa_handoff_content = None
        for file_rec in extracted:
            filename = file_rec["filename"]
            basename = os.path.basename(filename)
            if basename == "qa_handoff.md":
                qa_handoff_content = file_rec["content"]
                artifacts.append(
                    {
                        "name": filename,
                        "content": file_rec["content"],
                        "media_type": "text/markdown",
                        "type": "qa_handoff",
                    }
                )
            else:
                artifact_type, media_type = _classify_file(filename)
                artifacts.append(
                    {
                        "name": filename,
                        "content": file_rec["content"],
                        "media_type": media_type,
                        "type": artifact_type,
                    }
                )
        return extracted, artifacts, qa_handoff_content

    def _get_assembly_inputs(self, inputs: dict[str, Any]) -> dict[str, str]:
        """Get all source/config artifacts for assembly (D8 — static, not capability-driven).

        The builder role always needs to see all source files regardless of
        stack to produce correct packaging.
        """
        contents = inputs.get("artifact_contents", {})
        sources = {}
        for key, value in contents.items():
            if key.endswith(
                (
                    ".py",
                    ".js",
                    ".jsx",
                    ".ts",
                    ".tsx",
                    ".html",
                    ".css",
                    ".mjs",
                    ".txt",
                    ".yaml",
                    ".yml",
                    ".toml",
                    ".json",
                    ".md",
                )
            ):
                sources[key] = value
        return sources

    async def handle(
        self,
        context: ExecutionContext,
        inputs: dict[str, Any],
    ) -> HandlerResult:
        from squadops.capabilities.handlers.build_profiles import (
            QA_HANDOFF_REQUIRED_SECTIONS,
            get_profile,
        )
        from squadops.capabilities.handlers.fenced_parser import extract_fenced_files
        from squadops.cycles.check_registry import CHECK_REQUIRED_FILES

        start_time = time.perf_counter()

        prd = inputs.get("prd", "")
        prior_outputs = inputs.get("prior_outputs")
        resolved_config = inputs.get("resolved_config", {})

        # Step 1: Resolve build profile. Required — no default (#392). A missing
        # build_profile is a misconfiguration, not something to paper over with an
        # assumed stack; generate_task_plan rejects it before dispatch, and this
        # is the handler-level backstop.
        from squadops.cycles.task_outcome import FailureClassification, TaskOutcome

        profile_name = resolved_config.get("build_profile")
        if not profile_name:
            return self._fail_result(
                start_time,
                inputs,
                "build_profile is required for builder runs but was not configured "
                "(no default is assumed). Set build_profile in the cycle request profile.",
                outcome_class=TaskOutcome.SEMANTIC_FAILURE,
                failure_classification=FailureClassification.EXECUTION,
            )
        try:
            profile = get_profile(profile_name)
        except ValueError as exc:
            return self._fail_result(start_time, inputs, str(exc))

        # Step 1b: Resolve task tags (profile defaults + experiment_context overrides)
        task_tags = self._resolve_task_tags(profile, resolved_config)

        # Issue #107: when framing decomposed builder work, the active
        # task's expected_artifacts is the source of truth for what must
        # be emitted. Tuple of basenames (paths normalized) is what the
        # validator and prompt scoper both expect.
        import os as _os

        task_expected = inputs.get("expected_artifacts") or []
        task_required_files: tuple[str, ...] = tuple(
            _os.path.basename(p) for p in task_expected if isinstance(p, str) and p
        )

        # Step 2: Resolve source artifacts from dev role (assembly input)
        sources = self._get_assembly_inputs(inputs)

        if not sources:
            from squadops.cycles.task_outcome import FailureClassification, TaskOutcome

            return self._fail_result(
                start_time,
                inputs,
                "No source artifacts found for assembly",
                outcome_class=TaskOutcome.SEMANTIC_FAILURE,
                failure_classification=FailureClassification.WORK_PRODUCT,
            )

        # Step 3: Build assembly prompt
        rendered, user_prompt = await self._build_assembly_prompt(
            context, prd, prior_outputs, sources, task_tags
        )

        assembled = context.ports.prompt_service.get_system_prompt(self._role)
        # Issue #107: scope the profile prompt to this task's required
        # files when the framing step decomposed builder work.
        profile_prompt = profile.system_prompt_for_files(task_required_files or None)
        system_prompt = assembled.content + "\n\n" + profile_prompt

        messages = [
            ChatMessage(role="system", content=system_prompt),
            ChatMessage(role="user", content=user_prompt),
        ]

        # Step 4: LLM call — SIP-0075 §3.3 V1 boundary: builder uses only model + temperature
        agent_overrides = inputs.get("agent_config_overrides", {})
        agent_model = inputs.get("agent_model") or None
        builder_kwargs: dict[str, Any] = {}
        if agent_model:
            builder_kwargs["model"] = agent_model
        if "temperature" in agent_overrides:
            builder_kwargs["temperature"] = agent_overrides["temperature"]

        try:
            response = await context.ports.llm.chat_stream_with_usage(messages, **builder_kwargs)
        except LLMError as exc:
            logger.warning("LLM call failed for %s: %s", self._handler_name, exc)
            return self._fail_result(start_time, inputs, str(exc))

        content = response.content
        llm_duration_ms = (time.perf_counter() - start_time) * 1000

        # Record LLM generation for LangFuse tracing
        resolved_model = agent_model or context.ports.llm.default_model
        self._record_generation(
            context,
            user_prompt,
            content,
            llm_duration_ms,
            resolved_model,
            rendered=rendered,
            chat_response=response,
        )

        # Step 5: Parse fenced code blocks
        extracted = extract_fenced_files(content)

        if not extracted:
            from squadops.cycles.task_outcome import FailureClassification, TaskOutcome

            self._log_no_fenced_blocks(content)
            return self._fail_result(
                start_time,
                inputs,
                "No valid fenced code blocks found",
                outcome_class=TaskOutcome.SEMANTIC_FAILURE,
                failure_classification=FailureClassification.WORK_PRODUCT,
            )

        # Step 6-8: Validate builder output
        validation_error = self._validate_builder_output(
            extracted,
            profile,
            QA_HANDOFF_REQUIRED_SECTIONS,
            task_required_files=task_required_files or None,
        )

        # #399: emit a required_files check row so the SIP-0096 roll-up sees this
        # builder task's deliverable evidence. Recorded on BOTH paths — so the
        # common in-loop failure (a builder that can't emit its required files,
        # then exhausts correction) is disclosed as executed-failed instead of
        # leaving the run with zero evidence and a vacuous `accepted` verdict.
        # Independent of the section check: this row tracks *files* only.
        effective_required = task_required_files or profile.required_files
        extracted_basenames = {_os.path.basename(f["filename"]) for f in extracted}
        rf_missing = [rf for rf in effective_required if rf not in extracted_basenames]
        required_files_row = {"check": CHECK_REQUIRED_FILES, "passed": not rf_missing}

        if validation_error is not None:
            from squadops.cycles.task_outcome import FailureClassification, TaskOutcome

            return self._fail_result(
                start_time,
                inputs,
                validation_error,
                outputs={"validation_result": {"checks": [required_files_row]}},
                outcome_class=TaskOutcome.SEMANTIC_FAILURE,
                failure_classification=FailureClassification.WORK_PRODUCT,
            )

        # Step 8b: Deduplicate and classify
        extracted, artifacts, qa_handoff_content = self._dedup_and_classify(extracted)

        # Step 9: Build outputs with diagnostics
        # SIP-0084 §10: build prompt provenance for artifact traceability
        provenance: dict[str, Any] = {
            "system_prompt_bundle_hash": assembled.assembly_hash,
        }
        if rendered is not None:
            provenance["request_template_id"] = rendered.template_id
            provenance["request_template_version"] = rendered.template_version
            provenance["request_render_hash"] = rendered.render_hash
            provenance["prompt_environment"] = "production"

        qa_validation_errors: list[str] = []
        outputs = {
            "summary": f"[builder] Assembled {len(artifacts)} deployment artifact(s)",
            "role": self._role,
            "artifacts": artifacts,
            # #399: per-task required_files evidence for the SIP-0096 roll-up
            # (passed here — validation succeeded, so every required file present).
            "validation_result": {"checks": [required_files_row]},
            "diagnostics": {
                "resolved_handler": self._handler_name,
                "build_profile": profile_name,
                "source_files_count": len(sources),
                "qa_handoff_present": qa_handoff_content is not None,
                "qa_validation_errors": qa_validation_errors,
                "missing_required_files": [],
                "resolved_tags": task_tags,
            },
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

        return HandlerResult(success=True, outputs=outputs, _evidence=evidence)
