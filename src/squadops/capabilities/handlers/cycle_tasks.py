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

from squadops.capabilities.handlers.base import (
    CapabilityHandler,
    HandlerEvidence,
    HandlerResult,
)
from squadops.llm.exceptions import LLMError
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

    async def handle(
        self,
        context: ExecutionContext,
        inputs: dict[str, Any],
    ) -> HandlerResult:
        start_time = time.perf_counter()

        prd = inputs.get("prd", "")
        prior_outputs = inputs.get("prior_outputs")

        user_prompt = self._build_user_prompt(prd, prior_outputs)

        assembled = context.ports.prompt_service.get_system_prompt(self._role)
        system_prompt = assembled.content

        messages = [
            ChatMessage(role="system", content=system_prompt),
            ChatMessage(role="user", content=user_prompt),
        ]

        try:
            response = await context.ports.llm.chat(messages)
        except LLMError as exc:
            logger.warning(
                "LLM call failed for %s: %s", self._handler_name, exc,
            )
            duration_ms = (time.perf_counter() - start_time) * 1000
            evidence = HandlerEvidence.create(
                handler_name=self._handler_name,
                capability_id=self._capability_id,
                duration_ms=duration_ms,
                inputs_hash=self._hash_dict(inputs),
            )
            return HandlerResult(
                success=False, outputs={}, _evidence=evidence, error=str(exc),
            )

        content = response.content
        llm_duration_ms = (time.perf_counter() - start_time) * 1000

        # Record LLM generation for LangFuse tracing (SIP-0061 Option B)
        llm_obs = getattr(context.ports, "llm_observability", None)
        if llm_obs and context.correlation_context:
            import uuid

            from squadops.telemetry.models import (
                GenerationRecord,
                PromptLayer,
                PromptLayerMetadata,
            )

            gen_record = GenerationRecord(
                generation_id=str(uuid.uuid4()),
                model=context.ports.llm.default_model,
                prompt_text=user_prompt[:2000],
                response_text=content[:2000],
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

        prd_summary = str(prd)[:80] if prd else "(no PRD)"

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


class DevelopmentImplementHandler(_CycleTaskHandler):
    """Cycle task handler for development implementation (dev role)."""

    _handler_name = "development_implement_handler"
    _capability_id = "development.implement"
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
    """Cycle task handler for governance review (lead role)."""

    _handler_name = "governance_review_handler"
    _capability_id = "governance.review"
    _role = "lead"
    _artifact_name = "governance_review.md"


# ---------------------------------------------------------------------------
# Extension → artifact type / media type mapping (D5)
# ---------------------------------------------------------------------------

_EXT_MAP: dict[str, tuple[str, str]] = {
    ".py": ("source", "text/x-python"),
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


# ---------------------------------------------------------------------------
# Build handlers (SIP-Enhanced-Agent-Build-Capabilities)
# ---------------------------------------------------------------------------


class DevelopmentBuildHandler(_CycleTaskHandler):
    """Build handler: generates source code from implementation plan (D1, D8).

    Reads the implementation plan and strategy analysis from
    ``inputs["artifact_contents"]`` (pre-resolved by executor, D3)
    and instructs the LLM to produce runnable source files using
    tagged fenced code blocks.
    """

    _handler_name = "development_build_handler"
    _capability_id = "development.build"
    _role = "dev"
    _artifact_name = "build_output"  # overridden by multi-file output

    def validate_inputs(self, inputs: dict[str, Any], contract=None) -> list[str]:
        errors = super().validate_inputs(inputs, contract)
        # Build handlers require artifact_contents or artifact_vault for plan data
        if "artifact_contents" not in inputs and "artifact_vault" not in inputs:
            errors.append(
                "'artifact_contents' or 'artifact_vault' is required for build tasks"
            )
        return errors

    def _resolve_artifact_content(
        self, inputs: dict[str, Any], filename_substring: str,
    ) -> str | None:
        """Resolve artifact content by filename substring from inputs."""
        contents = inputs.get("artifact_contents", {})
        for key, value in contents.items():
            if filename_substring in key:
                return value
        return None

    async def _resolve_with_vault_fallback(
        self, inputs: dict[str, Any], filename_substring: str,
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
                    "Vault fallback: failed to retrieve %s", ref_id, exc_info=True,
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
        parts = [f"## Product Requirements Document\n\n{prd}"]

        if impl_plan:
            parts.append(f"\n\n## Implementation Plan\n\n{impl_plan}")

        if strategy:
            parts.append(f"\n\n## Strategy Analysis\n\n{strategy}")

        if prior_outputs:
            parts.append("\n\n## Prior Analysis from Upstream Roles\n")
            for role, summary in prior_outputs.items():
                parts.append(f"### {role}\n{summary}\n")

        parts.append(
            "\n\nGenerate complete, runnable source files as a Python package. "
            "Use tagged fenced code blocks with the format:\n"
            "```<language>:<filepath>\n<content>\n```\n\n"
            "IMPORTANT rules for file paths and imports:\n"
            "- Use the project name as the top-level package directory "
            "(e.g., play_game/main.py, play_game/board.py).\n"
            "- Always include a __init__.py for the package.\n"
            "- Use RELATIVE imports within the package "
            "(e.g., `from .board import Board`, NOT `from board import Board`).\n"
            "- File paths must use forward slashes, no colons, no spaces.\n"
            "- Include a requirements.txt at the project root if external "
            "dependencies are needed.\n"
            "- The main entry point should be runnable via "
            "`python -m <package_name>` (use __main__.py) or as a script.\n\n"
            "Example of a correctly structured package:\n"
            "```python:my_app/__init__.py\n```\n"
            "```python:my_app/__main__.py\n"
            "from .main import main\n"
            "if __name__ == '__main__':\n"
            "    main()\n```\n"
            "```python:my_app/main.py\n"
            "import random\n"
            "from .board import Board\n```\n\n"
            "Before emitting each file, verify:\n"
            "- All stdlib and third-party imports are present (import random, etc.)\n"
            "- All intra-package imports use relative form (from .module import X)\n"
            "- __main__.py uses relative imports, not absolute"
        )
        return "\n".join(parts)

    async def handle(
        self,
        context: ExecutionContext,
        inputs: dict[str, Any],
    ) -> HandlerResult:
        from squadops.capabilities.handlers.fenced_parser import extract_fenced_files

        start_time = time.perf_counter()

        prd = inputs.get("prd", "")
        prior_outputs = inputs.get("prior_outputs")

        # Resolve plan artifacts with vault fallback (D3)
        impl_plan = await self._resolve_with_vault_fallback(
            inputs, "implementation_plan",
        )
        strategy = await self._resolve_with_vault_fallback(inputs, "strategy_analysis")

        # Check required artifacts (fail only when vault was available but empty)
        if impl_plan is None and inputs.get("artifact_vault") is not None:
            duration_ms = (time.perf_counter() - start_time) * 1000
            evidence = HandlerEvidence.create(
                handler_name=self._handler_name,
                capability_id=self._capability_id,
                duration_ms=duration_ms,
                inputs_hash=self._hash_dict(inputs),
            )
            return HandlerResult(
                success=False, outputs={}, _evidence=evidence,
                error="Required plan artifacts not available",
            )

        user_prompt = self._build_user_prompt(
            prd, prior_outputs, impl_plan=impl_plan, strategy=strategy,
        )

        assembled = context.ports.prompt_service.get_system_prompt(self._role)
        system_prompt = (
            assembled.content
            + "\n\nYou are generating source code as a Python package. "
            "Emit each file as a fenced code block: ```<lang>:<path>\n"
            "Use relative imports within the package (from .module import X). "
            "Paths must be clean relative paths with no colons or spaces."
        )

        messages = [
            ChatMessage(role="system", content=system_prompt),
            ChatMessage(role="user", content=user_prompt),
        ]

        try:
            response = await context.ports.llm.chat(messages)
        except LLMError as exc:
            logger.warning("LLM call failed for %s: %s", self._handler_name, exc)
            duration_ms = (time.perf_counter() - start_time) * 1000
            evidence = HandlerEvidence.create(
                handler_name=self._handler_name,
                capability_id=self._capability_id,
                duration_ms=duration_ms,
                inputs_hash=self._hash_dict(inputs),
            )
            return HandlerResult(
                success=False, outputs={}, _evidence=evidence, error=str(exc),
            )

        content = response.content
        llm_duration_ms = (time.perf_counter() - start_time) * 1000

        # Record LLM generation for LangFuse tracing
        self._record_generation(context, user_prompt, content, llm_duration_ms)

        # Parse fenced code blocks
        extracted = extract_fenced_files(content)

        if not extracted:
            # Parse failure — return raw response as warning artifact
            duration_ms = (time.perf_counter() - start_time) * 1000
            evidence = HandlerEvidence.create(
                handler_name=self._handler_name,
                capability_id=self._capability_id,
                duration_ms=duration_ms,
                inputs_hash=self._hash_dict(inputs),
            )
            return HandlerResult(
                success=False,
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
                _evidence=evidence,
                error="No valid fenced code blocks found",
            )

        # Build artifact list from extracted files
        artifacts = []
        for file_rec in extracted:
            artifact_type, media_type = _classify_file(file_rec["filename"])
            artifacts.append({
                "name": file_rec["filename"],
                "content": file_rec["content"],
                "media_type": media_type,
                "type": artifact_type,
            })

        outputs = {
            "summary": f"[dev] Generated {len(artifacts)} source file(s)",
            "role": self._role,
            "artifacts": artifacts,
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
        self, context: ExecutionContext, prompt: str, response: str, duration_ms: float,
    ) -> None:
        llm_obs = getattr(context.ports, "llm_observability", None)
        if llm_obs and context.correlation_context:
            import uuid

            from squadops.telemetry.models import (
                GenerationRecord,
                PromptLayer,
                PromptLayerMetadata,
            )

            gen_record = GenerationRecord(
                generation_id=str(uuid.uuid4()),
                model=context.ports.llm.default_model,
                prompt_text=prompt[:2000],
                response_text=response[:2000],
                latency_ms=duration_ms,
            )
            layers = PromptLayerMetadata(
                prompt_layer_set_id=f"{self._role}-build",
                layers=(
                    PromptLayer(layer_type="system", layer_id=f"{self._role}-build-system"),
                    PromptLayer(
                        layer_type="user", layer_id=f"build-{self._capability_id}"
                    ),
                ),
            )
            llm_obs.record_generation(context.correlation_context, gen_record, layers)


class QABuildValidateHandler(_CycleTaskHandler):
    """Build handler: generates test files from validation plan + source (D1).

    Reads the validation plan and source artifacts from
    ``inputs["artifact_contents"]`` and instructs the LLM to produce
    pytest test files.
    """

    _handler_name = "qa_build_validate_handler"
    _capability_id = "qa.build_validate"
    _role = "qa"
    _artifact_name = "test_output"  # overridden by multi-file output

    def validate_inputs(self, inputs: dict[str, Any], contract=None) -> list[str]:
        errors = super().validate_inputs(inputs, contract)
        if "artifact_contents" not in inputs and "artifact_vault" not in inputs:
            errors.append(
                "'artifact_contents' or 'artifact_vault' is required for build tasks"
            )
        return errors

    def _resolve_artifact_content(
        self, inputs: dict[str, Any], filename_substring: str,
    ) -> str | None:
        """Resolve artifact content by filename substring from inputs."""
        contents = inputs.get("artifact_contents", {})
        for key, value in contents.items():
            if filename_substring in key:
                return value
        return None

    async def _resolve_with_vault_fallback(
        self, inputs: dict[str, Any], filename_substring: str,
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
                    "Vault fallback: failed to retrieve %s", ref_id, exc_info=True,
                )
        return None

    def _get_source_artifacts(self, inputs: dict[str, Any]) -> dict[str, str]:
        """Get all source artifacts from artifact_contents."""
        contents = inputs.get("artifact_contents", {})
        sources = {}
        for key, value in contents.items():
            if key.endswith(".py") and not key.startswith("test_"):
                sources[key] = value
        return sources

    def _build_user_prompt(
        self,
        prd: str,
        prior_outputs: dict[str, Any] | None,
        val_plan: str | None = None,
        sources: dict[str, str] | None = None,
    ) -> str:
        """Build prompt with validation plan + source code for test generation."""
        parts = [f"## Product Requirements Document\n\n{prd}"]

        if val_plan:
            parts.append(f"\n\n## Validation Plan\n\n{val_plan}")

        if sources:
            parts.append("\n\n## Source Files to Test\n")
            for path, code in sources.items():
                parts.append(f"\n### {path}\n```python\n{code}\n```\n")

        if prior_outputs:
            parts.append("\n\n## Prior Analysis from Upstream Roles\n")
            for role, summary in prior_outputs.items():
                parts.append(f"### {role}\n{summary}\n")

        parts.append(
            "\n\nGenerate pytest test files that thoroughly test the source code. "
            "Use tagged fenced code blocks with the format:\n"
            "```<language>:<filepath>\n<content>\n```\n\n"
            "IMPORTANT rules for test file paths and imports:\n"
            "- Place test files in a tests/ directory "
            "(e.g., tests/test_board.py, tests/test_game.py).\n"
            "- File paths must use forward slashes, no colons, no spaces.\n"
            "- Each fence path must be ONLY the file path — do NOT append "
            "extra metadata or source references after the path.\n"
            "- Import from the source package using its package name "
            "(e.g., `from play_game.board import Board`), NOT relative imports.\n"
            "- Include a tests/__init__.py if needed.\n"
            "- Use standard pytest conventions (test_ prefix, assert statements).\n\n"
            "Example:\n"
            "```python:tests/test_board.py\n"
            "import pytest\n"
            "from play_game.board import Board\n\n"
            "def test_initial_board_empty():\n"
            "    board = Board()\n"
            "    assert ...\n```\n\n"
            "Before emitting each file, verify:\n"
            "- All imports (pytest, stdlib, source package) are present\n"
            "- Source imports use the package name, not relative imports"
        )
        return "\n".join(parts)

    async def handle(
        self,
        context: ExecutionContext,
        inputs: dict[str, Any],
    ) -> HandlerResult:
        from squadops.capabilities.handlers.fenced_parser import extract_fenced_files

        start_time = time.perf_counter()

        prd = inputs.get("prd", "")
        prior_outputs = inputs.get("prior_outputs")

        # Resolve plan artifacts with vault fallback (D3)
        val_plan = await self._resolve_with_vault_fallback(inputs, "validation_plan")
        sources = self._get_source_artifacts(inputs)

        # Check required artifacts (fail only when vault was available but empty)
        if val_plan is None and inputs.get("artifact_vault") is not None:
            duration_ms = (time.perf_counter() - start_time) * 1000
            evidence = HandlerEvidence.create(
                handler_name=self._handler_name,
                capability_id=self._capability_id,
                duration_ms=duration_ms,
                inputs_hash=self._hash_dict(inputs),
            )
            return HandlerResult(
                success=False, outputs={}, _evidence=evidence,
                error="Required plan artifacts not available",
            )

        user_prompt = self._build_user_prompt(
            prd, prior_outputs, val_plan=val_plan, sources=sources,
        )

        assembled = context.ports.prompt_service.get_system_prompt(self._role)
        system_prompt = (
            assembled.content
            + "\n\nYou are generating pytest test files. "
            "Emit each file as a fenced code block: ```python:<path>\n"
            "Paths must be clean relative paths like tests/test_module.py — "
            "no colons, no spaces, no extra metadata after the path."
        )

        messages = [
            ChatMessage(role="system", content=system_prompt),
            ChatMessage(role="user", content=user_prompt),
        ]

        try:
            response = await context.ports.llm.chat(messages)
        except LLMError as exc:
            logger.warning("LLM call failed for %s: %s", self._handler_name, exc)
            duration_ms = (time.perf_counter() - start_time) * 1000
            evidence = HandlerEvidence.create(
                handler_name=self._handler_name,
                capability_id=self._capability_id,
                duration_ms=duration_ms,
                inputs_hash=self._hash_dict(inputs),
            )
            return HandlerResult(
                success=False, outputs={}, _evidence=evidence, error=str(exc),
            )

        content = response.content
        llm_duration_ms = (time.perf_counter() - start_time) * 1000

        # Record LLM generation for LangFuse tracing
        self._record_generation(context, user_prompt, content, llm_duration_ms)

        # Parse fenced code blocks
        extracted = extract_fenced_files(content)

        if not extracted:
            duration_ms = (time.perf_counter() - start_time) * 1000
            evidence = HandlerEvidence.create(
                handler_name=self._handler_name,
                capability_id=self._capability_id,
                duration_ms=duration_ms,
                inputs_hash=self._hash_dict(inputs),
            )
            return HandlerResult(
                success=False,
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
                _evidence=evidence,
                error="No valid fenced code blocks found",
            )

        # Build artifact list — all test files get artifact_type "test"
        artifacts = []
        for file_rec in extracted:
            _, media_type = _classify_file(file_rec["filename"])
            artifacts.append({
                "name": file_rec["filename"],
                "content": file_rec["content"],
                "media_type": media_type,
                "type": "test",
            })

        # --- Run generated tests against source files ---
        from squadops.capabilities.handlers.test_runner import run_generated_tests

        source_file_records = [
            {"path": path, "content": code} for path, code in sources.items()
        ]
        test_file_records = [
            {"path": rec["filename"], "content": rec["content"]} for rec in extracted
        ]
        test_result = await run_generated_tests(source_file_records, test_file_records)

        # Build test report artifact
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

        artifacts.append({
            "name": "test_report.md",
            "content": "\n".join(report_lines),
            "media_type": "text/markdown",
            "type": "test_report",
        })

        # Build summary with test outcome
        if test_result.tests_passed:
            test_suffix = ", all tests passed"
        elif test_result.executed:
            test_suffix = f", tests failed (exit code {test_result.exit_code})"
        else:
            test_suffix = f", tests not run: {test_result.error}" if test_result.error else ""

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
        self, context: ExecutionContext, prompt: str, response: str, duration_ms: float,
    ) -> None:
        llm_obs = getattr(context.ports, "llm_observability", None)
        if llm_obs and context.correlation_context:
            import uuid

            from squadops.telemetry.models import (
                GenerationRecord,
                PromptLayer,
                PromptLayerMetadata,
            )

            gen_record = GenerationRecord(
                generation_id=str(uuid.uuid4()),
                model=context.ports.llm.default_model,
                prompt_text=prompt[:2000],
                response_text=response[:2000],
                latency_ms=duration_ms,
            )
            layers = PromptLayerMetadata(
                prompt_layer_set_id=f"{self._role}-build",
                layers=(
                    PromptLayer(layer_type="system", layer_id=f"{self._role}-build-system"),
                    PromptLayer(
                        layer_type="user", layer_id=f"build-{self._capability_id}"
                    ),
                ),
            )
            llm_obs.record_generation(context.correlation_context, gen_record, layers)
