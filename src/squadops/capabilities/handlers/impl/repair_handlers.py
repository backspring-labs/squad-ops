"""Repair handlers for the SIP-0079 correction protocol.

Thin subclasses of _CycleTaskHandler used by the repair-task selector in
cycles/task_plan.py: development.correction_repair (dev),
builder.assemble_repair (builder), and qa.validate_repair (qa).

Issue #100: this file used to define a `DevelopmentRepairHandler` with
`_capability_id = "development.repair"`. That collided with the SIP-0070
pulse-check `DevelopmentRepairHandler` in handlers/repair_tasks.py. The
correction-loop variant is now `DevelopmentCorrectionRepairHandler` with
`_capability_id = "development.correction_repair"` so the pulse-check and
correction-loop flows have distinct, non-overlapping capability ids.
"""

from __future__ import annotations

from typing import Any

from squadops.capabilities.handlers.cycle_tasks import _classify_file, _CycleTaskHandler
from squadops.capabilities.handlers.fenced_parser import extract_fenced_files


def _artifacts_from_fenced_blocks(content: str, fallback_name: str) -> list[dict[str, Any]]:
    """Extract per-file artifacts from fenced code blocks in *content*.

    Repair handlers ask the LLM to emit replacement source files in the
    same fenced format the develop handler uses. Without this extraction
    the base handler wraps the entire response as a single markdown doc
    and the repaired files never land in artifact storage — the failure
    mode that motivated this helper.

    Falls back to a single markdown wrap when no fenced blocks are found
    so the LLM output is not silently dropped.
    """
    extracted = extract_fenced_files(content)
    if not extracted:
        return [
            {
                "name": fallback_name,
                "content": content,
                "media_type": "text/markdown",
                "type": "document",
            },
        ]
    artifacts: list[dict[str, Any]] = []
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
    return artifacts


def _format_bullets(items: Any) -> str:
    """Format list-of-strings inputs as a markdown bullet list, "(none)" if empty."""
    if not items:
        return "(none specified)"
    if isinstance(items, str):
        return items
    try:
        rendered = "\n".join(
            f"- `{item}`" if "/" in str(item) or "." in str(item) else f"- {item}" for item in items
        )
        return rendered or "(none specified)"
    except TypeError:
        return str(items)


def _format_failure_summary(failure_evidence: Any, failure_analysis: Any) -> str:
    """Compose a compact failure description from evidence + analysis."""
    parts: list[str] = []
    if isinstance(failure_evidence, dict):
        vr = failure_evidence.get("validation_result") or {}
        summary = vr.get("summary") or failure_evidence.get("error") or ""
        if summary:
            parts.append(f"Validation summary: {summary}")
        missing = vr.get("missing_components") or []
        if missing:
            parts.append("Missing components: " + ", ".join(str(m) for m in missing))
        rejected = failure_evidence.get("rejected_artifacts") or []
        if rejected:
            names = ", ".join(str(r.get("name", "?")) for r in rejected)
            parts.append(f"Rejected artifacts: {names}")
    if isinstance(failure_analysis, dict):
        analysis = failure_analysis.get("analysis_summary")
        if analysis:
            parts.append(f"Analyzer summary: {analysis}")
        factors = failure_analysis.get("contributing_factors") or []
        if factors:
            parts.append("Contributing factors:\n" + "\n".join(f"- {f}" for f in factors))
    return "\n\n".join(parts) if parts else "(no structured failure evidence available)"


_FENCE_LANG_BY_EXT: dict[str, str] = {
    ".py": "python",
    ".js": "javascript",
    ".jsx": "jsx",
    ".ts": "typescript",
    ".tsx": "tsx",
    ".json": "json",
    ".md": "markdown",
    ".yml": "yaml",
    ".yaml": "yaml",
    ".sh": "bash",
    ".sql": "sql",
    ".html": "html",
    ".css": "css",
    ".toml": "toml",
}


def _fence_language_for(filename: str) -> str:
    if not isinstance(filename, str):
        return ""
    lower = filename.lower()
    for ext, lang in _FENCE_LANG_BY_EXT.items():
        if lower.endswith(ext):
            return lang
    return ""


def _format_repair_artifacts(artifacts: Any) -> str:
    """Render repair artifacts as fenced code blocks with filename headers.

    The qa role previously saw only the role-keyed one-line summary, so
    it would return Verdict: FAIL on repairs whose artifacts were
    already in the registry. Surfacing the full content here lets the
    validator cite specific lines when checking acceptance criteria.
    """
    if not isinstance(artifacts, list) or not artifacts:
        return ""
    rendered: list[str] = []
    for art in artifacts:
        if not isinstance(art, dict):
            continue
        name = art.get("name") or "(unnamed)"
        content = art.get("content")
        if content is None:
            continue
        lang = _fence_language_for(name)
        fence_open = f"```{lang}" if lang else "```"
        rendered.append(f"#### `{name}`\n{fence_open}\n{content}\n```")
    return "\n\n".join(rendered)


def _format_correction_decision(correction_decision: Any) -> str:
    """Render the lead's correction decision rationale for the prompt."""
    if isinstance(correction_decision, dict):
        rationale = correction_decision.get("decision_rationale") or ""
        path = correction_decision.get("correction_path") or ""
        if rationale:
            return f"Path: {path}\n\n{rationale}" if path else rationale
        return str(correction_decision)
    return str(correction_decision or "(no decision available)")


class _RepairPromptMixin:
    """Shared prompt-building for correction-loop repair handlers.

    The base `_CycleTaskHandler` user prompt is PRD + prior_outputs only —
    the repair handler never sees the failed task's expected_artifacts /
    acceptance_criteria, so the dev/builder roles emit generic content
    instead of re-producing the named artifact that failed acceptance.
    This mixin surfaces the failed task's contract and the failure
    context to the LLM. Used by all three repair handlers below.
    """

    _request_template_id = "request.cycle_repair_task"

    def _build_render_variables(
        self,
        prd: str,
        prior_outputs: dict[str, Any] | None,
        inputs: dict[str, Any],
    ) -> dict[str, str]:
        return {
            "prd": prd,
            "role": self._role,
            "failed_task_type": str(inputs.get("failed_task_type", "")),
            "failure_summary": _format_failure_summary(
                inputs.get("failure_evidence"),
                inputs.get("failure_analysis"),
            ),
            "correction_decision": _format_correction_decision(inputs.get("correction_decision")),
            "subtask_focus": str(inputs.get("subtask_focus") or ""),
            "subtask_description": str(inputs.get("subtask_description") or ""),
            "expected_artifacts": _format_bullets(inputs.get("expected_artifacts")),
            "acceptance_criteria": _format_bullets(inputs.get("acceptance_criteria")),
            "prior_outputs": self._format_prior_outputs(prior_outputs),
        }

    def _build_user_prompt(
        self,
        prd: str,
        prior_outputs: dict[str, Any] | None,
        inputs: dict[str, Any] | None = None,
    ) -> str:
        inputs = inputs or {}
        parts = ["## Repair Task"]
        failed_type = inputs.get("failed_task_type")
        if failed_type:
            parts.append(
                f"You are repairing a failed `{failed_type}` task. Re-produce the "
                "named artifact(s) below so they satisfy the acceptance criteria. "
                "Do not produce a generic narrative."
            )

        focus = inputs.get("subtask_focus")
        if focus:
            parts.append(f"### Focus\n{focus}")
        desc = inputs.get("subtask_description")
        if desc:
            parts.append(f"### Description\n{desc}")

        expected = inputs.get("expected_artifacts")
        if expected:
            parts.append(
                "### Required Output Artifacts\n"
                "Emit each file with a fenced code block in the format "
                "` ```language:path/to/file `:\n" + _format_bullets(expected)
            )

        criteria = inputs.get("acceptance_criteria")
        if criteria:
            parts.append("### Acceptance Criteria\n" + _format_bullets(criteria))

        failure_summary = _format_failure_summary(
            inputs.get("failure_evidence"),
            inputs.get("failure_analysis"),
        )
        parts.append("### Why the Prior Attempt Failed\n" + failure_summary)

        decision = _format_correction_decision(inputs.get("correction_decision"))
        parts.append("### Correction Decision\n" + decision)

        parts.append(f"### Product Requirements Document\n\n{prd}")

        if prior_outputs:
            parts.append("### Prior Analysis from Upstream Roles")
            for role, summary in prior_outputs.items():
                parts.append(f"#### {role}\n{summary}")

        parts.append(
            "Produce the named artifacts now using fenced code blocks "
            "(` ```language:path/to/file `). Do not emit unrelated files."
        )
        return "\n\n".join(parts)


class DevelopmentCorrectionRepairHandler(_RepairPromptMixin, _CycleTaskHandler):
    """Correction-loop repair handler.

    Reads `failure_evidence`, `failure_analysis`, and `correction_decision`
    from inputs (set by the executor's correction protocol) and asks the
    LLM to author a repair. Distinct from the SIP-0070 pulse-check
    `DevelopmentRepairHandler`, which consumes `verification_context` from
    a different upstream chain.
    """

    _handler_name = "development_correction_repair_handler"
    _capability_id = "development.correction_repair"
    _role = "dev"
    _artifact_name = "repair_output.md"

    def _build_artifacts_from_content(self, content: str) -> list[dict[str, Any]]:
        return _artifacts_from_fenced_blocks(content, self._artifact_name)


class BuilderAssembleRepairHandler(_RepairPromptMixin, _CycleTaskHandler):
    """Correction-loop repair handler for failed builder.assemble tasks.

    Mirrors `DevelopmentCorrectionRepairHandler` but routed to the builder
    role so packaging/handoff failures (e.g. qa_handoff.md missing
    required sections, missing requirements.txt or package.json) get
    repaired by the builder role with the build-profile system prompt
    rather than by the dev role with the dev system prompt — the dev
    role has no useful context for builder.assemble outputs and simply
    ignores the assignment.
    """

    _handler_name = "builder_assemble_repair_handler"
    _capability_id = "builder.assemble_repair"
    _role = "builder"
    _artifact_name = "repair_output.md"

    def _build_artifacts_from_content(self, content: str) -> list[dict[str, Any]]:
        return _artifacts_from_fenced_blocks(content, self._artifact_name)


class QAValidateRepairHandler(_CycleTaskHandler):
    """Validate repair handler: verifies the repair was successful.

    Receives the original failed task's contract (expected_artifacts,
    acceptance_criteria) plus the upstream repair handler's outputs via
    `prior_outputs`, and produces a structured PASS/FAIL `repair_validation.md`
    against those criteria — not a fresh QA strategy document.
    """

    _handler_name = "qa_validate_repair_handler"
    _capability_id = "qa.validate_repair"
    _role = "qa"
    _artifact_name = "repair_validation.md"
    _request_template_id = "request.cycle_validate_repair"

    @staticmethod
    def _format_repair_summary(prior_outputs: dict[str, Any] | None) -> str:
        """Render the upstream repair handler's artifacts for the qa prompt.

        The executor stores the repair task's outputs under its role key
        (e.g. `prior_outputs["builder"]` for builder.assemble_repair). For
        repair tasks the executor preserves the `artifacts` list (unlike
        the regular fan-in path), so we surface filename + content here
        so the qa role can verify against the original acceptance
        criteria. Falls back to the role-keyed summary when no artifacts
        are present.
        """
        if not prior_outputs:
            return "(no repair output available)"
        repair_keys = [k for k in ("dev", "builder") if k in prior_outputs]
        if not repair_keys:
            return "(no repair output from dev or builder role)"
        parts: list[str] = []
        for key in repair_keys:
            block = prior_outputs[key]
            if not isinstance(block, dict):
                parts.append(f"### {key} repair\n{block!r}")
                continue

            section = [f"### {key} repair"]
            summary = block.get("summary")
            if summary:
                section.append(str(summary))

            artifacts = block.get("artifacts") or []
            rendered_artifacts = _format_repair_artifacts(artifacts)
            if rendered_artifacts:
                section.append(rendered_artifacts)
            elif not summary:
                section.append(repr(block))
            parts.append("\n\n".join(section))
        return "\n\n".join(parts)

    def _build_render_variables(
        self,
        prd: str,
        prior_outputs: dict[str, Any] | None,
        inputs: dict[str, Any],
    ) -> dict[str, str]:
        return {
            "prd": prd,
            "role": self._role,
            "failed_task_type": str(inputs.get("failed_task_type", "")),
            "expected_artifacts": _format_bullets(inputs.get("expected_artifacts")),
            "acceptance_criteria": _format_bullets(inputs.get("acceptance_criteria")),
            "failure_summary": _format_failure_summary(
                inputs.get("failure_evidence"),
                inputs.get("failure_analysis"),
            ),
            "repair_summary": self._format_repair_summary(prior_outputs),
            "prior_outputs": self._format_prior_outputs(prior_outputs),
        }

    def _build_user_prompt(
        self,
        prd: str,
        prior_outputs: dict[str, Any] | None,
        inputs: dict[str, Any] | None = None,
    ) -> str:
        inputs = inputs or {}
        parts = [
            "## Validate Repair",
            "Decide whether the repair output satisfies the original acceptance "
            "criteria. Do NOT write a fresh QA strategy. Answer the specific "
            "question: was the failure fixed?",
        ]

        failed_type = inputs.get("failed_task_type")
        if failed_type:
            parts.append(f"### Failed Task Type\n`{failed_type}`")

        expected = inputs.get("expected_artifacts")
        if expected:
            parts.append("### Original Required Artifacts\n" + _format_bullets(expected))

        criteria = inputs.get("acceptance_criteria")
        if criteria:
            parts.append("### Original Acceptance Criteria\n" + _format_bullets(criteria))

        failure_summary = _format_failure_summary(
            inputs.get("failure_evidence"),
            inputs.get("failure_analysis"),
        )
        parts.append("### Original Failure\n" + failure_summary)

        parts.append("### Repair Output\n" + self._format_repair_summary(prior_outputs))

        parts.append(f"### Product Requirements Document\n\n{prd}")

        parts.append(
            "Produce a `repair_validation.md` with sections: Verdict (PASS|FAIL), "
            "Per-Artifact Findings, Per-Criterion Findings, Recommendation. "
            "Be concrete. Cite the criterion and the specific content (or absence) "
            "that satisfies or violates it."
        )
        return "\n\n".join(parts)
