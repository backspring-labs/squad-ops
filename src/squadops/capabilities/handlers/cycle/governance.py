"""GovernanceReviewHandler (lead role) — governance review + implementation plan.
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
    _PRD_COVERAGE_DISCIPLINE_SECTION,
    _rewrite_manifest_identifiers,
)

logger = logging.getLogger(__name__)


class GovernanceReviewHandler(_CycleTaskHandler):
    """Cycle task handler for governance review (lead role).

    When ``implementation_plan`` is enabled in resolved config, this handler
    produces both a governance review document AND an implementation plan
    (SIP-0086 §6.1.3 / SIP-0092). The plan is a control-plane artifact that
    decomposes the build into focused subtasks.
    """

    _handler_name = "governance_review_handler"
    _capability_id = "governance.review"
    _role = "lead"
    _artifact_name = "governance_review.md"

    # Issue #109: project_id / cycle_id / prd_hash are facts the system
    # owns, not values the LLM should invent. The braced placeholders
    # below are substituted with authoritative values at render time
    # (see _render_manifest_extension); the parsed manifest is also
    # rewritten with these same values at extract time so the artifact
    # is correct even if the LLM ignores the substituted prompt.
    _MANIFEST_PROMPT_EXTENSION = (
        "\n\n---\n\n"
        "## Build Task Manifest\n\n"
        "In addition to your governance review above, produce a build task manifest "
        "that decomposes the upcoming build into focused subtasks.\n\n"
        "Each subtask should:\n"
        "1. Have a clear, narrow focus (e.g., 'Backend data models' not 'Build the app')\n"
        "2. List the specific files it should produce\n"
        "3. Declare dependencies on prior subtasks by task_index\n"
        "4. Define acceptance criteria (what must be true for this subtask to pass)\n"
        "5. Be completable in a single focused LLM generation (~2-10 minutes)\n\n"
        "Decomposition guidelines:\n"
        "- Separate backend and frontend into distinct tasks\n"
        "- Separate models/data from API endpoints/routes\n"
        "- Separate UI shell/routing from individual view components\n"
        "- Put integration config (CORS, proxy, requirements) in its own task\n"
        "- Put tests after the code they test\n"
        "- Put QA handoff last\n\n" + _PRD_COVERAGE_DISCIPLINE_SECTION + "\n"
        "Output the manifest as a YAML code block with filename: "
        "implementation_plan.yaml\n\n"
        "Use this exact schema. The first three fields are pre-filled with "
        "the cycle's authoritative values — copy them verbatim, do not invent "
        "or modify them:\n"
        "```yaml:implementation_plan.yaml\n"
        "version: 1\n"
        "project_id: {project_id}\n"
        "cycle_id: {cycle_id}\n"
        "prd_hash: {prd_hash}\n"
        "tasks:\n"
        "  - task_index: 0\n"
        "    task_type: development.develop  # or qa.test\n"
        "    role: dev  # or qa\n"
        '    focus: "Short description of this subtask"\n'
        "    description: |\n"
        "      Detailed description of what to build.\n"
        "    expected_artifacts:\n"
        '      - "path/to/file.py"\n'
        "    acceptance_criteria:\n"
        '      - "Criterion 1"\n'
        "    depends_on: []  # list of task_index values\n"
        "summary:\n"
        "  total_dev_tasks: N\n"
        "  total_qa_tasks: M\n"
        "  total_tasks: N+M\n"
        "  estimated_layers: [backend, frontend, test, config]\n"
        "```\n"
    )

    @staticmethod
    def _render_manifest_extension(project_id: str, cycle_id: str, prd_hash: str) -> str:
        return GovernanceReviewHandler._MANIFEST_PROMPT_EXTENSION.format(
            project_id=project_id or "(unknown)",
            cycle_id=cycle_id or "(unknown)",
            prd_hash=prd_hash or "(unknown)",
        )

    async def handle(
        self,
        context: ExecutionContext,
        inputs: dict[str, Any],
    ) -> HandlerResult:
        resolved_config = inputs.get("resolved_config", {})
        implementation_plan_enabled = resolved_config.get("implementation_plan", True)

        if not implementation_plan_enabled:
            return await super().handle(context, inputs)

        # Multi-artifact path: governance review + implementation plan
        import hashlib

        start_time = time.perf_counter()
        prd = inputs.get("prd", "")
        prior_outputs = inputs.get("prior_outputs")

        # Issue #109: substitute authoritative cycle identifiers into the
        # manifest prompt so the LLM never has to invent project_id /
        # cycle_id / prd_hash. Same values also overwrite the parsed
        # manifest at extract time as a defense-in-depth measure.
        prd_hash = hashlib.sha256(prd.encode()).hexdigest() if prd else ""
        manifest_extension = self._render_manifest_extension(
            project_id=context.project_id,
            cycle_id=context.cycle_id,
            prd_hash=prd_hash,
        )

        # Build prompt with manifest extension
        renderer = getattr(context.ports, "request_renderer", None)
        rendered = None
        if renderer is not None:
            variables = self._build_render_variables(prd, prior_outputs, inputs)
            rendered = await renderer.render(self._request_template_id, variables)
            user_prompt = rendered.content + manifest_extension
        else:
            user_prompt = self._build_user_prompt(prd, prior_outputs) + manifest_extension

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
            logger.warning("LLM call failed for %s: %s", self._handler_name, exc)
            return self._fail_result(start_time, inputs, str(exc))

        content = response.content
        llm_duration_ms = (time.perf_counter() - start_time) * 1000

        # Record LLM generation for tracing
        self._record_generation(
            context, user_prompt, content, llm_duration_ms, chat_kwargs, rendered
        )

        prd_summary = str(prd)[:80] if prd else "(no PRD)"

        # Build prompt provenance
        provenance = self._build_provenance(assembled, renderer, rendered)

        # Primary artifact: governance review (full response content)
        artifacts: list[dict[str, Any]] = [
            {
                "name": self._artifact_name,
                "content": content,
                "media_type": "text/markdown",
                "type": "document",
            },
        ]

        # Extract and validate build task manifest
        manifest_artifact = self._extract_manifest(
            content,
            resolved_config,
            prd,
            project_id=context.project_id,
            cycle_id=context.cycle_id,
            prd_hash=prd_hash,
        )
        if manifest_artifact is not None:
            artifacts.append(manifest_artifact)

        outputs = {
            "summary": f"[{self._role}] {prd_summary}",
            "role": self._role,
            "artifacts": artifacts,
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

    def _extract_manifest(
        self,
        content: str,
        resolved_config: dict[str, Any],
        prd: str = "",
        project_id: str = "",
        cycle_id: str = "",
        prd_hash: str = "",
    ) -> dict[str, Any] | None:
        """Extract and validate build task manifest from LLM response.

        Returns manifest artifact dict, or None on graceful fallback (RC-4).
        Issue #109: overwrites project_id / cycle_id / prd_hash in the
        emitted YAML with the authoritative values held by the executor —
        these are facts the system owns, not values the LLM should
        invent. We log when the LLM-emitted value disagreed so the
        substitution remains observable.
        """
        from squadops.capabilities.handlers.fenced_parser import extract_fenced_files
        from squadops.cycles.implementation_plan import ImplementationPlan

        extracted = extract_fenced_files(content)
        manifest_files = [f for f in extracted if f["filename"] == "implementation_plan.yaml"]

        if manifest_files:
            yaml_content = manifest_files[0]["content"]
        else:
            # Fallback: LLM may have used ```yaml without the filename tag.
            # Search for untagged YAML blocks that contain manifest-like content.
            yaml_content = self._find_manifest_in_raw_yaml(content)
            if yaml_content is None:
                logger.warning(
                    "%s: no implementation_plan.yaml found in response, "
                    "falling back to static task steps",
                    self._handler_name,
                )
                return None
            logger.info(
                "%s: manifest found via untagged YAML fallback",
                self._handler_name,
            )

        # Issue #109: substitute authoritative identifiers before
        # parsing-validation so a structurally-fine manifest with
        # fabricated identifiers can't poison downstream lookups.
        yaml_content = _rewrite_manifest_identifiers(
            yaml_content,
            project_id=project_id,
            cycle_id=cycle_id,
            prd_hash=prd_hash,
            handler_name=self._handler_name,
        )

        # Structural validation
        try:
            manifest = ImplementationPlan.from_yaml(yaml_content)
        except ValueError as exc:
            logger.warning(
                "%s: manifest validation failed (%s), falling back to static task steps",
                self._handler_name,
                exc,
            )
            return None

        # Policy validation — subtask count bounds from resolved config
        min_subtasks = resolved_config.get("min_build_subtasks", 3)
        max_subtasks = resolved_config.get("max_build_subtasks", 15)

        if len(manifest.tasks) < min_subtasks:
            logger.warning(
                "%s: manifest has %d subtasks (min %d), falling back to static task steps",
                self._handler_name,
                len(manifest.tasks),
                min_subtasks,
            )
            return None

        if len(manifest.tasks) > max_subtasks:
            logger.warning(
                "%s: manifest has %d subtasks (max %d), falling back to static task steps",
                self._handler_name,
                len(manifest.tasks),
                max_subtasks,
            )
            return None

        return {
            "name": "implementation_plan.yaml",
            "content": yaml_content,
            "media_type": "text/yaml",
            "type": "control_implementation_plan",
        }

    @staticmethod
    def _find_manifest_in_raw_yaml(content: str) -> str | None:
        """Search for an untagged ```yaml block containing manifest-like content.

        Fallback for when the LLM uses ```yaml instead of ```yaml:implementation_plan.yaml.
        Returns the YAML string if found, or None.
        """
        import re

        # Match ```yaml ... ``` blocks (without filename tag)
        pattern = r"```yaml\s*\n(.*?)```"
        for match in re.finditer(pattern, content, re.DOTALL):
            block = match.group(1).strip()
            # Check for manifest-like content markers
            if "task_index" in block and "task_type" in block and "focus" in block:
                return block
        return None

    def _record_generation(
        self,
        context: ExecutionContext,
        user_prompt: str,
        content: str,
        llm_duration_ms: float,
        chat_kwargs: dict[str, Any],
        rendered: Any,
    ) -> None:
        """Record LLM generation for LangFuse tracing (SIP-0061)."""
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
                prompt_layer_set_id=f"{self._role}-cycle",
                layers=(
                    PromptLayer(layer_type="system", layer_id=f"{self._role}-system"),
                    PromptLayer(layer_type="user", layer_id=f"cycle-{self._capability_id}"),
                ),
            )
            llm_obs.record_generation(context.correlation_context, gen_record, layers)

    def _build_provenance(self, assembled: Any, renderer: Any, rendered: Any) -> dict[str, Any]:
        """Build prompt provenance dict for artifact traceability (SIP-0084)."""
        provenance: dict[str, Any] = {
            "system_prompt_bundle_hash": assembled.assembly_hash,
        }
        if renderer is not None and rendered is not None:
            provenance["request_template_id"] = rendered.template_id
            provenance["request_template_version"] = rendered.template_version
            provenance["request_render_hash"] = rendered.render_hash
            provenance["prompt_environment"] = "production"
        return provenance
