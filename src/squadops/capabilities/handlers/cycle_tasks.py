"""Cycle task handlers — LLM-powered handlers for cycle execution pipeline.

5 handlers whose capability_id matches the pinned task_type values
from the static task plan (SIP-0066 §5.4). Each handler calls
``context.ports.llm.chat()`` with role-specific system prompts
assembled via ``PromptService`` (SIP-0057), passing the PRD and
upstream outputs as context. Per-agent models are threaded from
squad profile metadata.

Part of SIP-0066.
"""

from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING, Any

from squadops.capabilities.dev_capabilities import get_capability
from squadops.capabilities.handlers.base import (
    CapabilityHandler,
    HandlerEvidence,
    HandlerResult,
)
from squadops.capabilities.handlers.prompt_guard import _guard_prompt_size
from squadops.llm.exceptions import LLMError
from squadops.llm.model_registry import get_model_spec
from squadops.llm.models import ChatMessage

if TYPE_CHECKING:
    from squadops.capabilities.handlers.context import ExecutionContext

logger = logging.getLogger(__name__)


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
    ) -> str:
        """Assemble user prompt from PRD and upstream handler outputs."""
        parts = [f"## Product Requirements Document\n\n{prd}"]
        if prior_outputs:
            parts.append("\n\n## Prior Analysis from Upstream Roles\n")
            for role, summary in prior_outputs.items():
                parts.append(f"### {role}\n{summary}\n")
        parts.append(f"\nPlease provide your {self._role} analysis and deliverables.")
        return "\n".join(parts)

    @staticmethod
    def _format_prior_outputs(prior_outputs: dict[str, Any] | None) -> str:
        """Format prior outputs dict as a prompt section string for template injection."""
        if not prior_outputs:
            return ""
        parts = ["\n\n## Prior Analysis from Upstream Roles\n"]
        for role, summary in prior_outputs.items():
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

    def _fail_result(
        self,
        start_time: float,
        inputs: dict[str, Any],
        error: str,
        outputs: dict[str, Any] | None = None,
    ) -> HandlerResult:
        """Build a failure HandlerResult with evidence."""
        duration_ms = (time.perf_counter() - start_time) * 1000
        evidence = HandlerEvidence.create(
            handler_name=self._handler_name,
            capability_id=self._capability_id,
            duration_ms=duration_ms,
            inputs_hash=self._hash_dict(inputs),
        )
        return HandlerResult(
            success=False,
            outputs=outputs or {},
            _evidence=evidence,
            error=error,
        )

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
        """Build chat() kwargs from agent config overrides (SIP-0075 §3.2)."""
        overrides = inputs.get("agent_config_overrides", {})
        agent_model = inputs.get("agent_model") or None
        kwargs: dict[str, Any] = {}
        if agent_model:
            kwargs["model"] = agent_model
        if "temperature" in overrides:
            kwargs["temperature"] = overrides["temperature"]
        if "max_completion_tokens" in overrides:
            kwargs["max_tokens"] = overrides["max_completion_tokens"]
        if "timeout_seconds" in overrides:
            kwargs["timeout_seconds"] = overrides["timeout_seconds"]
        return kwargs

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
            user_prompt = self._build_user_prompt(prd, prior_outputs)

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
                tokens_per_second=response.tokens_per_second,
                prompt_tokens=response.prompt_tokens,
                completion_tokens=response.completion_tokens,
                total_tokens=response.total_tokens,
                prompt_name=rendered.template_id if rendered else None,
                prompt_version=(
                    int(rendered.template_version)
                    if rendered and rendered.template_version
                    else None
                ),
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


class StrategyAnalyzeHandler(_CycleTaskHandler):
    """Cycle task handler for strategy analysis (strat role)."""

    _handler_name = "strategy_analyze_handler"
    _capability_id = "strategy.analyze_prd"
    _role = "strat"
    _artifact_name = "strategy_analysis.md"


class DevelopmentDesignHandler(_CycleTaskHandler):
    """Cycle task handler for development design (dev role)."""

    _handler_name = "development_design_handler"
    _capability_id = "development.design"
    _role = "dev"
    _artifact_name = "implementation_plan.md"


class QAValidateHandler(_CycleTaskHandler):
    """Cycle task handler for QA validation (qa role)."""

    _handler_name = "qa_validate_handler"
    _capability_id = "qa.validate"
    _role = "qa"
    _artifact_name = "validation_plan.md"


class DataReportHandler(_CycleTaskHandler):
    """Cycle task handler for data reporting (data role)."""

    _handler_name = "data_report_handler"
    _capability_id = "data.report"
    _role = "data"
    _artifact_name = "data_report.md"


class GovernanceReviewHandler(_CycleTaskHandler):
    """Cycle task handler for governance review (lead role).

    When ``build_manifest`` is enabled in resolved config, this handler
    produces both a governance review document AND a build task manifest
    (SIP-0086 §6.1.3). The manifest is a control-plane artifact that
    decomposes the build into focused subtasks.
    """

    _handler_name = "governance_review_handler"
    _capability_id = "governance.review"
    _role = "lead"
    _artifact_name = "governance_review.md"

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
        "- Put QA handoff last\n\n"
        "Output the manifest as a YAML code block with filename: "
        "build_task_manifest.yaml\n\n"
        "Use this exact schema:\n"
        "```yaml:build_task_manifest.yaml\n"
        "version: 1\n"
        "project_id: <project_id>\n"
        "cycle_id: <cycle_id>\n"
        "prd_hash: <sha256 of PRD>\n"
        "tasks:\n"
        "  - task_index: 0\n"
        "    task_type: development.develop  # or qa.test\n"
        "    role: dev  # or qa\n"
        "    focus: \"Short description of this subtask\"\n"
        "    description: |\n"
        "      Detailed description of what to build.\n"
        "    expected_artifacts:\n"
        "      - \"path/to/file.py\"\n"
        "    acceptance_criteria:\n"
        "      - \"Criterion 1\"\n"
        "    depends_on: []  # list of task_index values\n"
        "summary:\n"
        "  total_dev_tasks: N\n"
        "  total_qa_tasks: M\n"
        "  total_tasks: N+M\n"
        "  estimated_layers: [backend, frontend, test, config]\n"
        "```\n"
    )

    async def handle(
        self,
        context: ExecutionContext,
        inputs: dict[str, Any],
    ) -> HandlerResult:
        resolved_config = inputs.get("resolved_config", {})
        build_manifest_enabled = resolved_config.get("build_manifest", True)

        if not build_manifest_enabled:
            return await super().handle(context, inputs)

        # Multi-artifact path: governance review + build task manifest
        start_time = time.perf_counter()
        prd = inputs.get("prd", "")
        prior_outputs = inputs.get("prior_outputs")

        # Build prompt with manifest extension
        renderer = getattr(context.ports, "request_renderer", None)
        rendered = None
        if renderer is not None:
            variables = self._build_render_variables(prd, prior_outputs, inputs)
            rendered = await renderer.render(self._request_template_id, variables)
            user_prompt = rendered.content + self._MANIFEST_PROMPT_EXTENSION
        else:
            user_prompt = (
                self._build_user_prompt(prd, prior_outputs)
                + self._MANIFEST_PROMPT_EXTENSION
            )

        assembled = context.ports.prompt_service.get_system_prompt(self._role)
        system_prompt = assembled.content

        messages = [
            ChatMessage(role="system", content=system_prompt),
            ChatMessage(role="user", content=user_prompt),
        ]

        chat_kwargs = self._build_chat_kwargs(inputs)

        try:
            response = await context.ports.llm.chat_stream_with_usage(
                messages, **chat_kwargs
            )
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
        manifest_artifact = self._extract_manifest(content, resolved_config)
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
        self, content: str, resolved_config: dict[str, Any]
    ) -> dict[str, Any] | None:
        """Extract and validate build task manifest from LLM response.

        Returns manifest artifact dict, or None on graceful fallback (RC-4).
        """
        from squadops.capabilities.handlers.fenced_parser import extract_fenced_files
        from squadops.cycles.build_manifest import BuildTaskManifest

        extracted = extract_fenced_files(content)
        manifest_files = [
            f for f in extracted if f["filename"] == "build_task_manifest.yaml"
        ]

        if not manifest_files:
            logger.warning(
                "%s: no build_task_manifest.yaml found in response, "
                "falling back to static task steps",
                self._handler_name,
            )
            return None

        yaml_content = manifest_files[0]["content"]

        # Structural validation
        try:
            manifest = BuildTaskManifest.from_yaml(yaml_content)
        except ValueError as exc:
            logger.warning(
                "%s: manifest validation failed (%s), "
                "falling back to static task steps",
                self._handler_name,
                exc,
            )
            return None

        # Policy validation — subtask count bounds from resolved config
        min_subtasks = resolved_config.get("min_build_subtasks", 3)
        max_subtasks = resolved_config.get("max_build_subtasks", 15)

        if len(manifest.tasks) < min_subtasks:
            logger.warning(
                "%s: manifest has %d subtasks (min %d), "
                "falling back to static task steps",
                self._handler_name,
                len(manifest.tasks),
                min_subtasks,
            )
            return None

        if len(manifest.tasks) > max_subtasks:
            logger.warning(
                "%s: manifest has %d subtasks (max %d), "
                "falling back to static task steps",
                self._handler_name,
                len(manifest.tasks),
                max_subtasks,
            )
            return None

        return {
            "name": "build_task_manifest.yaml",
            "content": yaml_content,
            "media_type": "text/yaml",
            "type": "control_manifest",
        }

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
                    PromptLayer(
                        layer_type="user", layer_id=f"cycle-{self._capability_id}"
                    ),
                ),
            )
            llm_obs.record_generation(context.correlation_context, gen_record, layers)

    def _build_provenance(
        self, assembled: Any, renderer: Any, rendered: Any
    ) -> dict[str, Any]:
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


# ---------------------------------------------------------------------------
# Extension → artifact type / media type mapping (D5)
# ---------------------------------------------------------------------------

_EXT_MAP: dict[str, tuple[str, str]] = {
    ".py": ("source", "text/x-python"),
    ".js": ("source", "text/javascript"),
    ".jsx": ("source", "text/javascript"),
    ".ts": ("source", "text/typescript"),
    ".tsx": ("source", "text/typescript"),
    ".mjs": ("source", "text/javascript"),
    ".css": ("source", "text/css"),
    ".html": ("source", "text/html"),
    ".md": ("document", "text/markdown"),
    ".txt": ("config", "text/plain"),
    ".yaml": ("config", "text/yaml"),
    ".yml": ("config", "text/yaml"),
    ".toml": ("config", "application/toml"),
    ".json": ("config", "application/json"),
}

# Special-cased filenames (checked before extension)
_FILENAME_MAP: dict[str, tuple[str, str]] = {
    "requirements.txt": ("config", "text/plain"),
    "package.json": ("config", "application/json"),
    "vite.config.js": ("config", "text/javascript"),
    "tsconfig.json": ("config", "application/json"),
}

_DEFAULT_TYPE = ("source", "application/octet-stream")


def _classify_file(filename: str) -> tuple[str, str]:
    """Derive (artifact_type, media_type) from filename."""
    import os

    basename = os.path.basename(filename)

    # Special-case filenames first
    if basename in _FILENAME_MAP:
        return _FILENAME_MAP[basename]

    _, ext = os.path.splitext(filename)
    return _EXT_MAP.get(ext.lower(), _DEFAULT_TYPE)


def _is_test_file(path: str, patterns: tuple[str, ...]) -> bool:
    """Check if *path* matches any test file pattern or resides in __tests__/.

    Uses fnmatch for glob-style pattern matching (D4).
    """
    from fnmatch import fnmatch
    from pathlib import PurePosixPath

    name = PurePosixPath(path).name
    return any(fnmatch(name, pat) for pat in patterns) or "/__tests__/" in path


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

        # Resolve capability (fail fast on unknown dev_capability)
        try:
            capability = get_capability(self._resolved_config.get("dev_capability", "python_cli"))
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
            return self._fail_result(start_time, inputs, "Required plan artifacts not available")

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

        # SIP-0084 §10: build prompt provenance for artifact traceability
        provenance: dict[str, Any] = {
            "system_prompt_bundle_hash": assembled.assembly_hash,
        }
        if rendered is not None:
            provenance["request_template_id"] = rendered.template_id
            provenance["request_template_version"] = rendered.template_version
            provenance["request_render_hash"] = rendered.render_hash
            provenance["prompt_environment"] = "production"

        outputs = {
            "summary": f"[dev] Generated {len(artifacts)} source file(s)",
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

    def _record_generation(
        self,
        context: ExecutionContext,
        prompt: str,
        response: str,
        duration_ms: float,
        resolved_model: str | None = None,
        rendered: object | None = None,
        chat_response: ChatMessage | None = None,
    ) -> None:
        if chat_response and chat_response.tokens_per_second:
            logger.info(
                "%s LLM throughput: %.1f t/s (%s tokens)",
                self._handler_name,
                chat_response.tokens_per_second,
                chat_response.completion_tokens,
            )
        llm_obs = getattr(context.ports, "llm_observability", None)
        if llm_obs and context.correlation_context:
            import uuid

            from squadops.telemetry.models import (
                MAX_OBSERVABILITY_TEXT_LENGTH,
                GenerationRecord,
                PromptLayer,
                PromptLayerMetadata,
            )

            gen_record = GenerationRecord(
                generation_id=str(uuid.uuid4()),
                model=resolved_model or context.ports.llm.default_model,
                prompt_text=prompt[:MAX_OBSERVABILITY_TEXT_LENGTH],
                response_text=response[:MAX_OBSERVABILITY_TEXT_LENGTH],
                latency_ms=duration_ms,
                tokens_per_second=(chat_response.tokens_per_second if chat_response else None),
                prompt_tokens=chat_response.prompt_tokens if chat_response else None,
                completion_tokens=(chat_response.completion_tokens if chat_response else None),
                total_tokens=chat_response.total_tokens if chat_response else None,
                prompt_name=getattr(rendered, "template_id", None),
                prompt_version=(
                    int(rendered.template_version)
                    if rendered and getattr(rendered, "template_version", None)
                    else None
                ),
            )
            layers = PromptLayerMetadata(
                prompt_layer_set_id=f"{self._role}-build",
                layers=(
                    PromptLayer(layer_type="system", layer_id=f"{self._role}-build-system"),
                    PromptLayer(layer_type="user", layer_id=f"build-{self._capability_id}"),
                ),
            )
            llm_obs.record_generation(context.correlation_context, gen_record, layers)


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

    def _get_source_artifacts(self, inputs: dict[str, Any]) -> dict[str, str]:
        """Get source artifacts filtered by capability (D4, D9)."""
        capability = get_capability(
            inputs.get("resolved_config", {}).get("dev_capability", "python_cli")
        )
        contents = inputs.get("artifact_contents", {})
        sources = {}
        for key, value in contents.items():
            if any(key.endswith(ext) for ext in capability.source_filter):
                if not _is_test_file(key, capability.test_file_patterns):
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
        """Run test suite and return (test_result, report_artifact)."""
        from squadops.capabilities.dev_capabilities import (
            TEST_FRAMEWORK_BOTH,
            TEST_FRAMEWORK_VITEST,
        )
        from squadops.capabilities.handlers.test_runner import (
            run_fullstack_tests,
            run_generated_tests,
            run_node_tests,
        )

        source_file_records = [{"path": p, "content": c} for p, c in sources.items()]
        test_file_records = [
            {"path": rec["filename"], "content": rec["content"]} for rec in extracted
        ]
        test_timeout = capability.test_timeout_seconds

        if capability.test_framework == TEST_FRAMEWORK_VITEST:
            test_result = await run_node_tests(
                source_file_records,
                test_file_records,
                timeout_seconds=test_timeout,
            )
        elif capability.test_framework == TEST_FRAMEWORK_BOTH:
            test_result = await run_fullstack_tests(
                source_file_records,
                test_file_records,
                timeout_seconds=test_timeout,
            )
        else:
            test_result = await run_generated_tests(
                source_file_records,
                test_file_records,
                timeout_seconds=test_timeout,
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

        # Resolve plan artifacts with vault fallback (D3)
        val_plan = await self._resolve_with_vault_fallback(inputs, "validation_plan")
        sources = self._get_source_artifacts(inputs)

        # Check required artifacts (fail only when vault was available but empty)
        if val_plan is None and inputs.get("artifact_vault") is not None:
            return self._fail_result(start_time, inputs, "Required plan artifacts not available")

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

        # Run generated tests and build report
        test_result, test_report_artifact = await self._run_test_suite(
            capability, sources, extracted
        )
        artifacts.append(test_report_artifact)

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

        outputs = {
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

        duration_ms = (time.perf_counter() - start_time) * 1000
        evidence = HandlerEvidence.create(
            handler_name=self._handler_name,
            capability_id=self._capability_id,
            duration_ms=duration_ms,
            inputs_hash=self._hash_dict(inputs),
            outputs_hash=self._hash_dict(outputs),
        )

        return HandlerResult(success=True, outputs=outputs, _evidence=evidence)

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

    def _record_generation(
        self,
        context: ExecutionContext,
        prompt: str,
        response: str,
        duration_ms: float,
        resolved_model: str | None = None,
        rendered: object | None = None,
        chat_response: ChatMessage | None = None,
    ) -> None:
        if chat_response and chat_response.tokens_per_second:
            logger.info(
                "%s LLM throughput: %.1f t/s (%s tokens)",
                self._handler_name,
                chat_response.tokens_per_second,
                chat_response.completion_tokens,
            )
        llm_obs = getattr(context.ports, "llm_observability", None)
        if llm_obs and context.correlation_context:
            import uuid

            from squadops.telemetry.models import (
                MAX_OBSERVABILITY_TEXT_LENGTH,
                GenerationRecord,
                PromptLayer,
                PromptLayerMetadata,
            )

            gen_record = GenerationRecord(
                generation_id=str(uuid.uuid4()),
                model=resolved_model or context.ports.llm.default_model,
                prompt_text=prompt[:MAX_OBSERVABILITY_TEXT_LENGTH],
                response_text=response[:MAX_OBSERVABILITY_TEXT_LENGTH],
                latency_ms=duration_ms,
                tokens_per_second=(chat_response.tokens_per_second if chat_response else None),
                prompt_tokens=chat_response.prompt_tokens if chat_response else None,
                completion_tokens=(chat_response.completion_tokens if chat_response else None),
                total_tokens=chat_response.total_tokens if chat_response else None,
                prompt_name=getattr(rendered, "template_id", None),
                prompt_version=(
                    int(rendered.template_version)
                    if rendered and getattr(rendered, "template_version", None)
                    else None
                ),
            )
            layers = PromptLayerMetadata(
                prompt_layer_set_id=f"{self._role}-build",
                layers=(
                    PromptLayer(layer_type="system", layer_id=f"{self._role}-build-system"),
                    PromptLayer(layer_type="user", layer_id=f"build-{self._capability_id}"),
                ),
            )
            llm_obs.record_generation(context.correlation_context, gen_record, layers)


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

    def validate_inputs(self, inputs: dict[str, Any], contract=None) -> list[str]:
        errors = super().validate_inputs(inputs, contract)
        if "artifact_contents" not in inputs and "artifact_vault" not in inputs:
            errors.append("'artifact_contents' or 'artifact_vault' is required for assembly tasks")
        return errors

    def _resolve_artifact_content(
        self,
        inputs: dict[str, Any],
        filename_substring: str,
    ) -> str | None:
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

    @staticmethod
    def _validate_builder_output(
        extracted: list[dict],
        profile: Any,
        required_sections: tuple[str, ...],
    ) -> str | None:
        """Validate builder output: qa_handoff, sections, required files.

        Returns an error message string if validation fails, None if OK.
        """
        import os

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

        extracted_basenames = {os.path.basename(f["filename"]) for f in extracted}
        missing_files = [rf for rf in profile.required_files if rf not in extracted_basenames]
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
        parts.append(
            "\n\nYou are ASSEMBLING the source code above into a deployable package. "
            "Do NOT rewrite or regenerate the source code — it is already written. "
            "Your job is to add deployment and packaging artifacts.\n\n"
            "Use tagged fenced code blocks with the language and path "
            "separated by a colon, for example:\n"
            "```dockerfile:Dockerfile\n<content>\n```\n"
            "```markdown:qa_handoff.md\n<content>\n```\n\n"
            "Produce the following deployment artifacts:\n"
            "- __main__.py entrypoint (if not already present)\n"
            "- Dockerfile for containerized deployment\n"
            "- requirements.txt (if not already present)\n"
            "- Any startup scripts or config files needed for deployment\n\n"
            "IMPORTANT: You MUST also include a `qa_handoff.md` file with these "
            "required sections:\n"
            "- ## How to Run\n"
            "- ## How to Test\n"
            "- ## Expected Behavior\n\n"
            "File path rules:\n"
            "- File paths must use forward slashes, no colons, no spaces.\n"
            "- Do NOT re-emit source files that the developer already wrote.\n"
            "- Only emit NEW files needed for packaging and deployment."
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

        Bob always needs to see all source files regardless of stack to produce
        correct packaging.
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

        start_time = time.perf_counter()

        prd = inputs.get("prd", "")
        prior_outputs = inputs.get("prior_outputs")
        resolved_config = inputs.get("resolved_config", {})

        # Step 1: Resolve build profile
        profile_name = resolved_config.get("build_profile", "python_cli_builder")
        try:
            profile = get_profile(profile_name)
        except ValueError as exc:
            return self._fail_result(start_time, inputs, str(exc))

        # Step 1b: Resolve task tags (profile defaults + experiment_context overrides)
        task_tags = self._resolve_task_tags(profile, resolved_config)

        # Step 2: Resolve source artifacts from dev role (assembly input)
        sources = self._get_assembly_inputs(inputs)

        if not sources:
            return self._fail_result(start_time, inputs, "No source artifacts found for assembly")

        # Step 3: Build assembly prompt
        rendered, user_prompt = await self._build_assembly_prompt(
            context, prd, prior_outputs, sources, task_tags
        )

        assembled = context.ports.prompt_service.get_system_prompt(self._role)
        system_prompt = assembled.content + "\n\n" + profile.system_prompt_template

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
            return self._fail_result(start_time, inputs, "No valid fenced code blocks found")

        # Step 6-8: Validate builder output
        validation_error = self._validate_builder_output(
            extracted, profile, QA_HANDOFF_REQUIRED_SECTIONS
        )
        if validation_error is not None:
            return self._fail_result(start_time, inputs, validation_error)

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

    def _record_generation(
        self,
        context: ExecutionContext,
        prompt: str,
        response: str,
        duration_ms: float,
        resolved_model: str | None = None,
        rendered: object | None = None,
        chat_response: ChatMessage | None = None,
    ) -> None:
        if chat_response and chat_response.tokens_per_second:
            logger.info(
                "%s LLM throughput: %.1f t/s (%s tokens)",
                self._handler_name,
                chat_response.tokens_per_second,
                chat_response.completion_tokens,
            )
        llm_obs = getattr(context.ports, "llm_observability", None)
        if llm_obs and context.correlation_context:
            import uuid

            from squadops.telemetry.models import (
                MAX_OBSERVABILITY_TEXT_LENGTH,
                GenerationRecord,
                PromptLayer,
                PromptLayerMetadata,
            )

            gen_record = GenerationRecord(
                generation_id=str(uuid.uuid4()),
                model=resolved_model or context.ports.llm.default_model,
                prompt_text=prompt[:MAX_OBSERVABILITY_TEXT_LENGTH],
                response_text=response[:MAX_OBSERVABILITY_TEXT_LENGTH],
                latency_ms=duration_ms,
                tokens_per_second=(chat_response.tokens_per_second if chat_response else None),
                prompt_tokens=chat_response.prompt_tokens if chat_response else None,
                completion_tokens=(chat_response.completion_tokens if chat_response else None),
                total_tokens=chat_response.total_tokens if chat_response else None,
                prompt_name=getattr(rendered, "template_id", None),
                prompt_version=(
                    int(rendered.template_version)
                    if rendered and getattr(rendered, "template_version", None)
                    else None
                ),
            )
            layers = PromptLayerMetadata(
                prompt_layer_set_id=f"{self._role}-assemble",
                layers=(
                    PromptLayer(
                        layer_type="system",
                        layer_id=f"{self._role}-assemble-system",
                    ),
                    PromptLayer(layer_type="user", layer_id=f"assemble-{self._capability_id}"),
                ),
            )
            llm_obs.record_generation(context.correlation_context, gen_record, layers)
