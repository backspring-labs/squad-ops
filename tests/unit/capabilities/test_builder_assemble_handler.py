"""Unit tests for BuilderAssembleHandler (SIP-0071).

Tests handler instantiation, profile selection, assembly from source artifacts,
QA handoff generation, required deployment file validation, duplicate filename
detection, and routing diagnostics.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from squadops.capabilities.handlers.cycle_tasks import BuilderAssembleHandler
from squadops.llm.exceptions import LLMConnectionError
from squadops.llm.models import ChatMessage

pytestmark = [pytest.mark.domain_capabilities]


# ---------------------------------------------------------------------------
# LLM response fixtures (deployment artifacts, NOT source code)
# ---------------------------------------------------------------------------

LLM_GOOD_RESPONSE = (
    "Here are the deployment artifacts:\n\n"
    "```python:my_app/__main__.py\n"
    "from .main import main\n"
    "if __name__ == '__main__':\n"
    "    main()\n"
    "```\n\n"
    "```dockerfile:Dockerfile\n"
    "FROM python:3.11-slim\n"
    "WORKDIR /app\n"
    "COPY requirements.txt .\n"
    "RUN pip install -r requirements.txt\n"
    "COPY . .\n"
    'CMD ["python", "-m", "my_app"]\n'
    "```\n\n"
    "```text:requirements.txt\n"
    "# no external dependencies\n"
    "```\n\n"
    "```markdown:qa_handoff.md\n"
    "## How to Run\n"
    "python -m my_app\n\n"
    "## How to Test\n"
    "pytest tests/\n\n"
    "## Expected Behavior\n"
    "Prints 'Hello from builder!'\n"
    "```\n"
)

LLM_MISSING_QA_HANDOFF = (
    "```python:my_app/__main__.py\n"
    "pass\n"
    "```\n\n"
    "```dockerfile:Dockerfile\n"
    "FROM python:3.11-slim\n"
    "```\n\n"
    "```text:requirements.txt\n"
    "# none\n"
    "```\n"
)

LLM_QA_HANDOFF_MISSING_SECTION = (
    "```python:my_app/__main__.py\n"
    "pass\n"
    "```\n\n"
    "```dockerfile:Dockerfile\n"
    "FROM python:3.11-slim\n"
    "```\n\n"
    "```text:requirements.txt\n"
    "# none\n"
    "```\n\n"
    "```markdown:qa_handoff.md\n"
    "## How to Run\n"
    "python -m my_app\n\n"
    "## How to Test\n"
    "pytest tests/\n"
    "```\n"
)

LLM_MISSING_REQUIRED_FILE = (
    "```python:my_app/__main__.py\n"
    "pass\n"
    "```\n\n"
    "```text:requirements.txt\n"
    "# none\n"
    "```\n\n"
    "```markdown:qa_handoff.md\n"
    "## How to Run\n"
    "python -m my_app\n\n"
    "## How to Test\n"
    "pytest\n\n"
    "## Expected Behavior\n"
    "Works\n"
    "```\n"
)

LLM_NO_FENCES = "I generated the deployment files but forgot fences.\nFROM python:3.11\n"

LLM_DUPLICATE_BASENAMES_DIFFERENT_PATHS = (
    "```python:my_app/__main__.py\n"
    "pass\n"
    "```\n\n"
    "```dockerfile:Dockerfile\n"
    "FROM python:3.11-slim\n"
    "```\n\n"
    "```text:requirements.txt\n"
    "# none\n"
    "```\n\n"
    "```dockerfile:deploy/Dockerfile\n"
    "# different path, same basename\n"
    "```\n\n"
    "```markdown:qa_handoff.md\n"
    "## How to Run\nrun it\n\n"
    "## How to Test\ntest it\n\n"
    "## Expected Behavior\nworks\n"
    "```\n"
)

LLM_DUPLICATE_EXACT_PATHS = (
    "```python:my_app/__main__.py\n"
    "pass\n"
    "```\n\n"
    "```dockerfile:Dockerfile\n"
    "FROM python:3.11-slim\n"
    "```\n\n"
    "```text:requirements.txt\n"
    "# none\n"
    "```\n\n"
    "```dockerfile:Dockerfile\n"
    "FROM python:3.11-slim\nCOPY . .\n"
    "```\n\n"
    "```markdown:qa_handoff.md\n"
    "## How to Run\nrun it\n\n"
    "## How to Test\ntest it\n\n"
    "## Expected Behavior\nworks\n"
    "```\n"
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def mock_context():
    """Return a MagicMock with llm.chat and prompt_service stubbed."""
    ctx = MagicMock()
    ctx.ports.llm.chat = AsyncMock(
        return_value=ChatMessage(role="assistant", content=LLM_GOOD_RESPONSE),
    )
    ctx.ports.llm.chat_stream_with_usage = AsyncMock(
        return_value=ChatMessage(role="assistant", content=LLM_GOOD_RESPONSE),
    )
    ctx.ports.llm.default_model = "test-model"
    assembled = MagicMock()
    assembled.content = "You are a builder agent."
    ctx.ports.prompt_service.get_system_prompt = MagicMock(return_value=assembled)
    ctx.ports.llm_observability = None
    ctx.ports.request_renderer = None
    ctx.correlation_context = None
    return ctx


@pytest.fixture()
def builder_inputs():
    """Standard inputs for assembly handler — source files from dev role."""
    return {
        "prd": "Build a CLI tool that prints hello world.",
        "resolved_config": {
            "build_profile": "python_cli_builder",
        },
        "artifact_contents": {
            "my_app/__init__.py": "# my_app package",
            "my_app/main.py": "def main():\n    print('Hello from builder!')\n",
        },
    }


# ---------------------------------------------------------------------------
# Handler instantiation
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Successful assembly
# ---------------------------------------------------------------------------


class TestBuilderAssembleSuccess:
    async def test_success_with_good_response(self, mock_context, builder_inputs):
        handler = BuilderAssembleHandler()
        result = await handler.handle(mock_context, builder_inputs)

        assert result.success is True
        artifacts = result.outputs["artifacts"]
        assert len(artifacts) == 4  # __main__.py, Dockerfile, requirements.txt, qa_handoff

    async def test_qa_handoff_artifact_present(self, mock_context, builder_inputs):
        handler = BuilderAssembleHandler()
        result = await handler.handle(mock_context, builder_inputs)

        qa_artifacts = [a for a in result.outputs["artifacts"] if a["type"] == "qa_handoff"]
        assert len(qa_artifacts) == 1
        assert "## How to Run" in qa_artifacts[0]["content"]

    async def test_summary_contains_builder(self, mock_context, builder_inputs):
        handler = BuilderAssembleHandler()
        result = await handler.handle(mock_context, builder_inputs)

        assert "[builder]" in result.outputs["summary"]
        assert "Assembled" in result.outputs["summary"]

    async def test_diagnostics_in_outputs(self, mock_context, builder_inputs):
        handler = BuilderAssembleHandler()
        result = await handler.handle(mock_context, builder_inputs)

        diag = result.outputs["diagnostics"]
        assert diag["resolved_handler"] == "builder_assemble_handler"
        assert diag["build_profile"] == "python_cli_builder"
        assert diag["source_files_count"] == 2
        assert diag["qa_handoff_present"] is True
        assert diag["qa_validation_errors"] == []
        assert diag["missing_required_files"] == []

    async def test_source_files_in_prompt(self, mock_context, builder_inputs):
        """Source artifacts from dev role appear in the LLM prompt."""
        handler = BuilderAssembleHandler()
        await handler.handle(mock_context, builder_inputs)

        call_args = mock_context.ports.llm.chat_stream_with_usage.call_args
        messages = call_args[0][0]
        user_msg = [m for m in messages if m.role == "user"][0]
        assert "my_app/main.py" in user_msg.content
        assert "Hello from builder!" in user_msg.content

    async def test_prompt_instructs_assembly_not_generation(self, mock_context, builder_inputs):
        """Prompt tells LLM to assemble, not generate source code."""
        handler = BuilderAssembleHandler()
        await handler.handle(mock_context, builder_inputs)

        call_args = mock_context.ports.llm.chat_stream_with_usage.call_args
        messages = call_args[0][0]
        user_msg = [m for m in messages if m.role == "user"][0]
        assert "ASSEMBLING" in user_msg.content
        assert "Do NOT rewrite" in user_msg.content


# ---------------------------------------------------------------------------
# Assembly requires source artifacts
# ---------------------------------------------------------------------------


class TestAssemblyRequiresSource:
    async def test_no_source_artifacts_returns_failure(self, mock_context):
        """Assembly fails if no source artifacts are provided."""
        inputs = {
            "prd": "Build something",
            "resolved_config": {},
            "artifact_contents": {},
        }
        handler = BuilderAssembleHandler()
        result = await handler.handle(mock_context, inputs)

        assert result.success is False
        assert "No source artifacts found" in result.error


# ---------------------------------------------------------------------------
# Profile selection
# ---------------------------------------------------------------------------


class TestProfileSelection:
    async def test_default_profile_when_not_specified(self, mock_context, builder_inputs):
        builder_inputs["resolved_config"] = {}
        handler = BuilderAssembleHandler()
        result = await handler.handle(mock_context, builder_inputs)

        assert result.outputs["diagnostics"]["build_profile"] == "python_cli_builder"

    async def test_unknown_profile_returns_failure(self, mock_context, builder_inputs):
        builder_inputs["resolved_config"] = {"build_profile": "nonexistent"}
        handler = BuilderAssembleHandler()
        result = await handler.handle(mock_context, builder_inputs)

        assert result.success is False
        assert "Unknown build profile" in result.error


# ---------------------------------------------------------------------------
# QA handoff validation
# ---------------------------------------------------------------------------


class TestQAHandoffValidation:
    async def test_missing_qa_handoff_reports_error(self, mock_context, builder_inputs):
        mock_context.ports.llm.chat = AsyncMock(
            return_value=ChatMessage(role="assistant", content=LLM_MISSING_QA_HANDOFF),
        )
        mock_context.ports.llm.chat_stream_with_usage = AsyncMock(
            return_value=ChatMessage(role="assistant", content=LLM_MISSING_QA_HANDOFF),
        )
        handler = BuilderAssembleHandler()
        result = await handler.handle(mock_context, builder_inputs)

        assert result.success is False
        assert "qa_handoff.md not found" in result.error

    async def test_missing_section_reports_error(self, mock_context, builder_inputs):
        mock_context.ports.llm.chat = AsyncMock(
            return_value=ChatMessage(
                role="assistant",
                content=LLM_QA_HANDOFF_MISSING_SECTION,
            ),
        )
        mock_context.ports.llm.chat_stream_with_usage = AsyncMock(
            return_value=ChatMessage(
                role="assistant",
                content=LLM_QA_HANDOFF_MISSING_SECTION,
            ),
        )
        handler = BuilderAssembleHandler()
        result = await handler.handle(mock_context, builder_inputs)

        assert result.success is False
        assert "Expected Behavior" in result.error


# ---------------------------------------------------------------------------
# Required file validation
# ---------------------------------------------------------------------------


class TestRequiredFileValidation:
    async def test_missing_required_file_reports_error(self, mock_context, builder_inputs):
        mock_context.ports.llm.chat = AsyncMock(
            return_value=ChatMessage(role="assistant", content=LLM_MISSING_REQUIRED_FILE),
        )
        mock_context.ports.llm.chat_stream_with_usage = AsyncMock(
            return_value=ChatMessage(role="assistant", content=LLM_MISSING_REQUIRED_FILE),
        )
        handler = BuilderAssembleHandler()
        result = await handler.handle(mock_context, builder_inputs)

        assert result.success is False
        # Dockerfile is missing
        assert "Dockerfile" in result.error


# ---------------------------------------------------------------------------
# Duplicate filename detection
# ---------------------------------------------------------------------------


class TestDuplicateFilenames:
    async def test_same_basename_different_paths_succeeds(self, mock_context, builder_inputs):
        """Fullstack projects can have same basename in different dirs."""
        mock_context.ports.llm.chat = AsyncMock(
            return_value=ChatMessage(
                role="assistant",
                content=LLM_DUPLICATE_BASENAMES_DIFFERENT_PATHS,
            ),
        )
        mock_context.ports.llm.chat_stream_with_usage = AsyncMock(
            return_value=ChatMessage(
                role="assistant",
                content=LLM_DUPLICATE_BASENAMES_DIFFERENT_PATHS,
            ),
        )
        handler = BuilderAssembleHandler()
        result = await handler.handle(mock_context, builder_inputs)

        assert result.success is True
        filenames = [a["name"] for a in result.outputs["artifacts"]]
        assert "Dockerfile" in filenames
        assert "deploy/Dockerfile" in filenames

    async def test_exact_duplicate_paths_deduped(self, mock_context, builder_inputs):
        """LLM emits same file twice — last occurrence wins, no failure."""
        mock_context.ports.llm.chat = AsyncMock(
            return_value=ChatMessage(
                role="assistant",
                content=LLM_DUPLICATE_EXACT_PATHS,
            ),
        )
        mock_context.ports.llm.chat_stream_with_usage = AsyncMock(
            return_value=ChatMessage(
                role="assistant",
                content=LLM_DUPLICATE_EXACT_PATHS,
            ),
        )
        handler = BuilderAssembleHandler()
        result = await handler.handle(mock_context, builder_inputs)

        assert result.success is True
        # Deduped: only one Dockerfile
        dockerfiles = [a for a in result.outputs["artifacts"] if a["name"] == "Dockerfile"]
        assert len(dockerfiles) == 1
        # Last occurrence kept (has COPY)
        assert "COPY" in dockerfiles[0]["content"]


# ---------------------------------------------------------------------------
# No fenced blocks
# ---------------------------------------------------------------------------


class TestNoFencedBlocks:
    async def test_no_fences_returns_failure(self, mock_context, builder_inputs):
        mock_context.ports.llm.chat = AsyncMock(
            return_value=ChatMessage(role="assistant", content=LLM_NO_FENCES),
        )
        mock_context.ports.llm.chat_stream_with_usage = AsyncMock(
            return_value=ChatMessage(role="assistant", content=LLM_NO_FENCES),
        )
        handler = BuilderAssembleHandler()
        result = await handler.handle(mock_context, builder_inputs)

        assert result.success is False
        assert "No valid fenced code blocks" in result.error


# ---------------------------------------------------------------------------
# LLM failure
# ---------------------------------------------------------------------------


class TestLLMFailure:
    async def test_llm_error_returns_failure(self, mock_context, builder_inputs):
        mock_context.ports.llm.chat = AsyncMock(
            side_effect=LLMConnectionError("Connection refused"),
        )
        mock_context.ports.llm.chat_stream_with_usage = AsyncMock(
            side_effect=LLMConnectionError("Connection refused"),
        )
        handler = BuilderAssembleHandler()
        result = await handler.handle(mock_context, builder_inputs)

        assert result.success is False
        assert "Connection refused" in result.error


# ---------------------------------------------------------------------------
# Input validation
# ---------------------------------------------------------------------------


class TestInputValidation:
    def test_requires_artifact_contents_or_vault(self):
        handler = BuilderAssembleHandler()
        errors = handler.validate_inputs({"prd": "test"})
        assert any("artifact_contents" in e for e in errors)

    def test_passes_with_artifact_contents(self):
        handler = BuilderAssembleHandler()
        errors = handler.validate_inputs(
            {
                "prd": "test",
                "artifact_contents": {"main.py": "# source"},
            }
        )
        assert not any("artifact_contents" in e for e in errors)

    def test_requires_prd(self):
        handler = BuilderAssembleHandler()
        errors = handler.validate_inputs(
            {
                "artifact_contents": {"main.py": "# source"},
            }
        )
        assert any("prd" in e for e in errors)


# ---------------------------------------------------------------------------
# Task tag interpolation (Phase 2)
# ---------------------------------------------------------------------------


class TestTagInterpolation:
    async def test_experiment_context_tags_in_prompt(self, mock_context, builder_inputs):
        """Tags from experiment_context appear in the LLM prompt."""
        builder_inputs["resolved_config"]["experiment_context"] = {
            "framework": "flask",
            "style": "minimal",
        }
        handler = BuilderAssembleHandler()
        await handler.handle(mock_context, builder_inputs)

        call_args = mock_context.ports.llm.chat_stream_with_usage.call_args
        messages = call_args[0][0]
        user_msg = [m for m in messages if m.role == "user"][0]
        assert "framework" in user_msg.content
        assert "flask" in user_msg.content
        assert "style" in user_msg.content
        assert "minimal" in user_msg.content

    async def test_default_task_tags_applied(self, mock_context, builder_inputs):
        """Profile default_task_tags appear in prompt when no experiment_context."""
        from squadops.capabilities.handlers.build_profiles import BUILD_PROFILES, BuildProfile

        original = BUILD_PROFILES.get("python_cli_builder")
        patched = BuildProfile(
            name="python_cli_builder",
            system_prompt_template=original.system_prompt_template,
            required_files=original.required_files,
            optional_files=original.optional_files,
            validation_rules=original.validation_rules,
            artifact_output_mode=original.artifact_output_mode,
            qa_handoff_expectations=original.qa_handoff_expectations,
            default_task_tags={"target_python": "3.11"},
        )
        BUILD_PROFILES["python_cli_builder"] = patched
        try:
            handler = BuilderAssembleHandler()
            await handler.handle(mock_context, builder_inputs)

            call_args = mock_context.ports.llm.chat_stream_with_usage.call_args
            messages = call_args[0][0]
            user_msg = [m for m in messages if m.role == "user"][0]
            assert "target_python" in user_msg.content
            assert "3.11" in user_msg.content
        finally:
            BUILD_PROFILES["python_cli_builder"] = original

    async def test_experiment_context_overrides_default_tags(self, mock_context, builder_inputs):
        """experiment_context tags override profile default_task_tags."""
        from squadops.capabilities.handlers.build_profiles import BUILD_PROFILES, BuildProfile

        original = BUILD_PROFILES.get("python_cli_builder")
        patched = BuildProfile(
            name="python_cli_builder",
            system_prompt_template=original.system_prompt_template,
            required_files=original.required_files,
            optional_files=original.optional_files,
            validation_rules=original.validation_rules,
            artifact_output_mode=original.artifact_output_mode,
            qa_handoff_expectations=original.qa_handoff_expectations,
            default_task_tags={"target_python": "3.11"},
        )
        BUILD_PROFILES["python_cli_builder"] = patched
        try:
            builder_inputs["resolved_config"]["experiment_context"] = {
                "target_python": "3.12",
            }
            handler = BuilderAssembleHandler()
            await handler.handle(mock_context, builder_inputs)

            call_args = mock_context.ports.llm.chat_stream_with_usage.call_args
            messages = call_args[0][0]
            user_msg = [m for m in messages if m.role == "user"][0]
            assert "3.12" in user_msg.content
            assert "3.11" not in user_msg.content
        finally:
            BUILD_PROFILES["python_cli_builder"] = original

    async def test_tags_cannot_remove_required_files(self, mock_context, builder_inputs):
        """Tags in experiment_context cannot weaken profile required_files."""
        builder_inputs["resolved_config"]["experiment_context"] = {
            "required_files": "none",
        }
        handler = BuilderAssembleHandler()
        result = await handler.handle(mock_context, builder_inputs)

        assert result.success is True
        diag = result.outputs["diagnostics"]
        assert diag["missing_required_files"] == []

    async def test_non_string_tags_ignored(self, mock_context, builder_inputs):
        """Non-string values in experiment_context are ignored with warning."""
        builder_inputs["resolved_config"]["experiment_context"] = {
            "valid_tag": "value",
            "invalid_tag": 42,
            "also_invalid": ["list"],
        }
        handler = BuilderAssembleHandler()
        result = await handler.handle(mock_context, builder_inputs)

        assert result.success is True
        diag = result.outputs["diagnostics"]
        resolved_tags = diag["resolved_tags"]
        assert "valid_tag" in resolved_tags
        assert "invalid_tag" not in resolved_tags
        assert "also_invalid" not in resolved_tags

    async def test_resolved_tags_in_diagnostics(self, mock_context, builder_inputs):
        """Resolved tags appear in diagnostics output."""
        builder_inputs["resolved_config"]["experiment_context"] = {
            "framework": "flask",
        }
        handler = BuilderAssembleHandler()
        result = await handler.handle(mock_context, builder_inputs)

        diag = result.outputs["diagnostics"]
        assert diag["resolved_tags"] == {"framework": "flask"}

    async def test_no_tags_produces_empty_dict(self, mock_context, builder_inputs):
        """When no tags are configured, diagnostics shows empty dict."""
        handler = BuilderAssembleHandler()
        result = await handler.handle(mock_context, builder_inputs)

        diag = result.outputs["diagnostics"]
        assert diag["resolved_tags"] == {}


# ---------------------------------------------------------------------------
# Assembly input expansion (SIP-0072 Phase 2, D8)
# ---------------------------------------------------------------------------


class TestAssemblyInputsExpandedExtensions:
    """_get_assembly_inputs() picks up JS/TS/HTML/CSS files (D8)."""

    async def test_jsx_files_included(self, mock_context):
        handler = BuilderAssembleHandler()
        inputs = {
            "prd": "Fullstack app.",
            "resolved_config": {"build_profile": "python_cli_builder"},
            "artifact_contents": {
                "backend/main.py": "from fastapi import FastAPI",
                "frontend/src/App.jsx": "export default function App() {}",
                "frontend/src/index.html": "<html></html>",
                "frontend/src/styles.css": "body { margin: 0; }",
            },
        }
        result = await handler.handle(mock_context, inputs)
        # Handler should succeed and include all files in the prompt
        assert result.success is True
        call_args = mock_context.ports.llm.chat_stream_with_usage.call_args
        user_msg = call_args[0][0][1].content
        assert "backend/main.py" in user_msg
        assert "frontend/src/App.jsx" in user_msg
        assert "frontend/src/index.html" in user_msg
        assert "frontend/src/styles.css" in user_msg

    async def test_ts_tsx_files_included(self, mock_context):
        handler = BuilderAssembleHandler()
        inputs = {
            "prd": "TS app.",
            "resolved_config": {"build_profile": "python_cli_builder"},
            "artifact_contents": {
                "src/app.ts": "const x: number = 1",
                "src/Component.tsx": "export default () => <div/>",
            },
        }
        result = await handler.handle(mock_context, inputs)
        assert result.success is True
        call_args = mock_context.ports.llm.chat_stream_with_usage.call_args
        user_msg = call_args[0][0][1].content
        assert "src/app.ts" in user_msg
        assert "src/Component.tsx" in user_msg

    async def test_mjs_files_included(self, mock_context):
        handler = BuilderAssembleHandler()
        inputs = {
            "prd": "ESM app.",
            "resolved_config": {"build_profile": "python_cli_builder"},
            "artifact_contents": {
                "utils.mjs": "export const foo = 42",
            },
        }
        result = await handler.handle(mock_context, inputs)
        assert result.success is True

    async def test_py_still_included(self, mock_context, builder_inputs):
        """Existing .py file inclusion is unchanged."""
        handler = BuilderAssembleHandler()
        result = await handler.handle(mock_context, builder_inputs)
        assert result.success is True
        call_args = mock_context.ports.llm.chat_stream_with_usage.call_args
        user_msg = call_args[0][0][1].content
        assert "my_app/main.py" in user_msg


# ---------------------------------------------------------------------------
# SIP-0086 closeout Fix #3: BuilderAssembleHandler emits outcome_class on
# structural validation failures. Before this fix, _fail_result returned an
# empty outputs dict and the executor's D5 fallback classified the failure
# as "unknown" after a retry — observed on cycle cyc_a2a15b81d3b9 run
# run_33a4c714b818 where plan_delta.failure_classification was "unknown"
# and data.analyze_failure produced "N/A".
# ---------------------------------------------------------------------------


class TestBuilderFailureOutcomeClass:
    async def test_missing_qa_handoff_emits_semantic_failure(
        self, mock_context, builder_inputs
    ):
        from squadops.cycles.task_outcome import FailureClassification, TaskOutcome

        mock_context.ports.llm.chat_stream_with_usage = AsyncMock(
            return_value=ChatMessage(role="assistant", content=LLM_MISSING_QA_HANDOFF),
        )
        handler = BuilderAssembleHandler()
        result = await handler.handle(mock_context, builder_inputs)

        assert result.success is False
        assert result.outputs["outcome_class"] == TaskOutcome.SEMANTIC_FAILURE
        assert result.outputs["failure_classification"] == FailureClassification.WORK_PRODUCT
        assert "qa_handoff.md not found" in result.error

    async def test_missing_required_file_emits_semantic_failure(
        self, mock_context, builder_inputs
    ):
        from squadops.cycles.task_outcome import FailureClassification, TaskOutcome

        mock_context.ports.llm.chat_stream_with_usage = AsyncMock(
            return_value=ChatMessage(role="assistant", content=LLM_MISSING_REQUIRED_FILE),
        )
        handler = BuilderAssembleHandler()
        result = await handler.handle(mock_context, builder_inputs)

        assert result.success is False
        assert result.outputs["outcome_class"] == TaskOutcome.SEMANTIC_FAILURE
        assert result.outputs["failure_classification"] == FailureClassification.WORK_PRODUCT

    async def test_no_fenced_blocks_emits_semantic_failure(
        self, mock_context, builder_inputs
    ):
        """LLM responds with prose only — no fenced code blocks extractable."""
        from squadops.cycles.task_outcome import FailureClassification, TaskOutcome

        mock_context.ports.llm.chat_stream_with_usage = AsyncMock(
            return_value=ChatMessage(
                role="assistant",
                content="I would build the package but no code was produced.",
            ),
        )
        handler = BuilderAssembleHandler()
        result = await handler.handle(mock_context, builder_inputs)

        assert result.success is False
        assert result.outputs["outcome_class"] == TaskOutcome.SEMANTIC_FAILURE
        assert result.outputs["failure_classification"] == FailureClassification.WORK_PRODUCT
        assert "No valid fenced code blocks" in result.error

    async def test_no_source_artifacts_emits_semantic_failure(self, mock_context):
        """Bob given no sources to assemble → SEMANTIC_FAILURE, not unclassified."""
        from squadops.cycles.task_outcome import FailureClassification, TaskOutcome

        inputs = {
            "prd": "Build something",
            "resolved_config": {},
            "artifact_contents": {},
        }
        handler = BuilderAssembleHandler()
        result = await handler.handle(mock_context, inputs)

        assert result.success is False
        assert result.outputs["outcome_class"] == TaskOutcome.SEMANTIC_FAILURE
        assert result.outputs["failure_classification"] == FailureClassification.WORK_PRODUCT

    async def test_llm_exception_stays_unclassified(self, mock_context, builder_inputs):
        """LLM connection errors are transient — D5 fallback retries; no semantic class."""
        mock_context.ports.llm.chat_stream_with_usage = AsyncMock(
            side_effect=LLMConnectionError("connection refused"),
        )
        handler = BuilderAssembleHandler()
        result = await handler.handle(mock_context, builder_inputs)

        assert result.success is False
        # Transient failures must NOT set outcome_class so the executor's
        # D5 retry-before-semantic-failure path activates.
        assert "outcome_class" not in result.outputs
