"""Unit tests for BuilderBuildHandler (SIP-0071).

Tests handler instantiation, profile selection, QA handoff generation,
required file validation, duplicate filename detection, and routing
diagnostics.
"""
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock

from squadops.capabilities.handlers.cycle_tasks import BuilderBuildHandler
from squadops.capabilities.handlers.base import HandlerResult
from squadops.llm.exceptions import LLMConnectionError
from squadops.llm.models import ChatMessage

pytestmark = [pytest.mark.domain_capabilities]


# ---------------------------------------------------------------------------
# LLM response fixtures
# ---------------------------------------------------------------------------

LLM_GOOD_RESPONSE = (
    "Here are the source files:\n\n"
    "```python:my_app/__init__.py\n"
    "# my_app package\n"
    "```\n\n"
    "```python:my_app/__main__.py\n"
    "from .main import main\n"
    "if __name__ == '__main__':\n"
    "    main()\n"
    "```\n\n"
    "```python:my_app/main.py\n"
    "def main():\n"
    "    print('Hello from builder!')\n"
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
    "```python:my_app/__init__.py\n"
    "# package\n"
    "```\n\n"
    "```python:my_app/__main__.py\n"
    "pass\n"
    "```\n\n"
    "```python:my_app/main.py\n"
    "def main(): pass\n"
    "```\n"
)

LLM_QA_HANDOFF_MISSING_SECTION = (
    "```python:my_app/__init__.py\n"
    "# package\n"
    "```\n\n"
    "```python:my_app/__main__.py\n"
    "pass\n"
    "```\n\n"
    "```python:my_app/main.py\n"
    "def main(): pass\n"
    "```\n\n"
    "```markdown:qa_handoff.md\n"
    "## How to Run\n"
    "python -m my_app\n\n"
    "## How to Test\n"
    "pytest tests/\n"
    "```\n"
)

LLM_MISSING_REQUIRED_FILE = (
    "```python:my_app/__init__.py\n"
    "# package\n"
    "```\n\n"
    "```python:my_app/main.py\n"
    "def main(): pass\n"
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

LLM_NO_FENCES = "I generated the code but forgot fences.\ndef main(): pass\n"

LLM_DUPLICATE_FILENAMES = (
    "```python:my_app/__init__.py\n"
    "# first\n"
    "```\n\n"
    "```python:my_app/__main__.py\n"
    "pass\n"
    "```\n\n"
    "```python:my_app/main.py\n"
    "def main(): pass\n"
    "```\n\n"
    "```python:other/main.py\n"
    "# duplicate basename main.py\n"
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
    ctx.ports.llm.default_model = "test-model"
    assembled = MagicMock()
    assembled.content = "You are a builder agent."
    ctx.ports.prompt_service.get_system_prompt = MagicMock(return_value=assembled)
    ctx.ports.llm_observability = None
    ctx.correlation_context = None
    return ctx


@pytest.fixture()
def builder_inputs():
    """Standard inputs for builder handler."""
    return {
        "prd": "Build a CLI tool that prints hello world.",
        "resolved_config": {
            "build_profile": "python_cli_builder",
        },
        "artifact_contents": {
            "implementation_plan.md": "# Plan\n\n1. Create main.py\n2. Add hello function",
            "strategy_analysis.md": "# Strategy\n\nSimple CLI approach.",
        },
    }


# ---------------------------------------------------------------------------
# Handler instantiation
# ---------------------------------------------------------------------------


class TestBuilderBuildHandlerMeta:
    def test_capability_id(self):
        handler = BuilderBuildHandler()
        assert handler.capability_id == "builder.build"

    def test_handler_name(self):
        handler = BuilderBuildHandler()
        assert handler.name == "builder_build_handler"

    def test_role_is_builder(self):
        handler = BuilderBuildHandler()
        assert handler._role == "builder"


# ---------------------------------------------------------------------------
# Successful build
# ---------------------------------------------------------------------------


class TestBuilderBuildSuccess:
    async def test_success_with_good_response(self, mock_context, builder_inputs):
        handler = BuilderBuildHandler()
        result = await handler.handle(mock_context, builder_inputs)

        assert result.success is True
        artifacts = result.outputs["artifacts"]
        assert len(artifacts) == 4  # 3 source + 1 qa_handoff

    async def test_qa_handoff_artifact_present(self, mock_context, builder_inputs):
        handler = BuilderBuildHandler()
        result = await handler.handle(mock_context, builder_inputs)

        qa_artifacts = [a for a in result.outputs["artifacts"] if a["type"] == "qa_handoff"]
        assert len(qa_artifacts) == 1
        assert "## How to Run" in qa_artifacts[0]["content"]

    async def test_source_artifacts_classified(self, mock_context, builder_inputs):
        handler = BuilderBuildHandler()
        result = await handler.handle(mock_context, builder_inputs)

        source_artifacts = [a for a in result.outputs["artifacts"] if a["type"] == "source"]
        assert len(source_artifacts) == 3  # __init__.py, __main__.py, main.py

    async def test_summary_contains_builder(self, mock_context, builder_inputs):
        handler = BuilderBuildHandler()
        result = await handler.handle(mock_context, builder_inputs)

        assert "[builder]" in result.outputs["summary"]

    async def test_diagnostics_in_outputs(self, mock_context, builder_inputs):
        handler = BuilderBuildHandler()
        result = await handler.handle(mock_context, builder_inputs)

        diag = result.outputs["diagnostics"]
        assert diag["resolved_handler"] == "builder_build_handler"
        assert diag["build_profile"] == "python_cli_builder"
        assert diag["qa_handoff_present"] is True
        assert diag["qa_validation_errors"] == []
        assert diag["missing_required_files"] == []


# ---------------------------------------------------------------------------
# Profile selection
# ---------------------------------------------------------------------------


class TestProfileSelection:
    async def test_default_profile_when_not_specified(self, mock_context):
        inputs = {
            "prd": "Build something",
            "resolved_config": {},
            "artifact_contents": {
                "implementation_plan.md": "# Plan",
                "strategy_analysis.md": "# Strategy",
            },
        }
        handler = BuilderBuildHandler()
        result = await handler.handle(mock_context, inputs)

        # Should default to python_cli_builder
        assert result.outputs["diagnostics"]["build_profile"] == "python_cli_builder"

    async def test_unknown_profile_returns_failure(self, mock_context):
        inputs = {
            "prd": "Build something",
            "resolved_config": {"build_profile": "nonexistent"},
            "artifact_contents": {
                "implementation_plan.md": "# Plan",
            },
        }
        handler = BuilderBuildHandler()
        result = await handler.handle(mock_context, inputs)

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
        handler = BuilderBuildHandler()
        result = await handler.handle(mock_context, builder_inputs)

        assert result.success is False
        assert "qa_handoff.md not found" in result.error

    async def test_missing_section_reports_error(self, mock_context, builder_inputs):
        mock_context.ports.llm.chat = AsyncMock(
            return_value=ChatMessage(
                role="assistant", content=LLM_QA_HANDOFF_MISSING_SECTION,
            ),
        )
        handler = BuilderBuildHandler()
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
        handler = BuilderBuildHandler()
        result = await handler.handle(mock_context, builder_inputs)

        assert result.success is False
        # __main__.py is missing
        assert "__main__.py" in result.error


# ---------------------------------------------------------------------------
# Duplicate filename detection
# ---------------------------------------------------------------------------


class TestDuplicateFilenames:
    async def test_duplicate_basenames_fail_validation(self, mock_context, builder_inputs):
        mock_context.ports.llm.chat = AsyncMock(
            return_value=ChatMessage(role="assistant", content=LLM_DUPLICATE_FILENAMES),
        )
        handler = BuilderBuildHandler()
        result = await handler.handle(mock_context, builder_inputs)

        assert result.success is False
        assert "Duplicate filenames" in result.error


# ---------------------------------------------------------------------------
# No fenced blocks
# ---------------------------------------------------------------------------


class TestNoFencedBlocks:
    async def test_no_fences_returns_failure(self, mock_context, builder_inputs):
        mock_context.ports.llm.chat = AsyncMock(
            return_value=ChatMessage(role="assistant", content=LLM_NO_FENCES),
        )
        handler = BuilderBuildHandler()
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
        handler = BuilderBuildHandler()
        result = await handler.handle(mock_context, builder_inputs)

        assert result.success is False
        assert "Connection refused" in result.error


# ---------------------------------------------------------------------------
# Input validation
# ---------------------------------------------------------------------------


class TestInputValidation:
    def test_requires_artifact_contents_or_vault(self):
        handler = BuilderBuildHandler()
        errors = handler.validate_inputs({"prd": "test"})
        assert any("artifact_contents" in e for e in errors)

    def test_passes_with_artifact_contents(self):
        handler = BuilderBuildHandler()
        errors = handler.validate_inputs({
            "prd": "test",
            "artifact_contents": {"plan.md": "# Plan"},
        })
        assert not any("artifact_contents" in e for e in errors)

    def test_requires_prd(self):
        handler = BuilderBuildHandler()
        errors = handler.validate_inputs({
            "artifact_contents": {"plan.md": "# Plan"},
        })
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
        handler = BuilderBuildHandler()
        await handler.handle(mock_context, builder_inputs)

        # Inspect the prompt sent to LLM
        call_args = mock_context.ports.llm.chat.call_args
        messages = call_args[0][0]
        user_msg = [m for m in messages if m.role == "user"][0]
        assert "framework" in user_msg.content
        assert "flask" in user_msg.content
        assert "style" in user_msg.content
        assert "minimal" in user_msg.content

    async def test_default_task_tags_applied(self, mock_context):
        """Profile default_task_tags appear in prompt when no experiment_context."""
        from squadops.capabilities.handlers.build_profiles import BUILD_PROFILES, BuildProfile

        # Create a profile with default_task_tags
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
            inputs = {
                "prd": "Build a CLI tool.",
                "resolved_config": {},
                "artifact_contents": {
                    "implementation_plan.md": "# Plan",
                    "strategy_analysis.md": "# Strategy",
                },
            }
            handler = BuilderBuildHandler()
            await handler.handle(mock_context, inputs)

            call_args = mock_context.ports.llm.chat.call_args
            messages = call_args[0][0]
            user_msg = [m for m in messages if m.role == "user"][0]
            assert "target_python" in user_msg.content
            assert "3.11" in user_msg.content
        finally:
            BUILD_PROFILES["python_cli_builder"] = original

    async def test_experiment_context_overrides_default_tags(self, mock_context):
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
            inputs = {
                "prd": "Build a CLI tool.",
                "resolved_config": {
                    "experiment_context": {"target_python": "3.12"},
                },
                "artifact_contents": {
                    "implementation_plan.md": "# Plan",
                    "strategy_analysis.md": "# Strategy",
                },
            }
            handler = BuilderBuildHandler()
            await handler.handle(mock_context, inputs)

            call_args = mock_context.ports.llm.chat.call_args
            messages = call_args[0][0]
            user_msg = [m for m in messages if m.role == "user"][0]
            assert "3.12" in user_msg.content
            # Default 3.11 should NOT appear since it was overridden
            assert "3.11" not in user_msg.content
        finally:
            BUILD_PROFILES["python_cli_builder"] = original

    async def test_tags_cannot_remove_required_files(self, mock_context, builder_inputs):
        """Tags in experiment_context cannot weaken profile required_files."""
        builder_inputs["resolved_config"]["experiment_context"] = {
            "required_files": "none",
        }
        handler = BuilderBuildHandler()
        result = await handler.handle(mock_context, builder_inputs)

        # The profile's required_files are still enforced despite the tag
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
        handler = BuilderBuildHandler()
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
        handler = BuilderBuildHandler()
        result = await handler.handle(mock_context, builder_inputs)

        diag = result.outputs["diagnostics"]
        assert diag["resolved_tags"] == {"framework": "flask"}

    async def test_no_tags_produces_empty_dict(self, mock_context, builder_inputs):
        """When no tags are configured, diagnostics shows empty dict."""
        handler = BuilderBuildHandler()
        result = await handler.handle(mock_context, builder_inputs)

        diag = result.outputs["diagnostics"]
        assert diag["resolved_tags"] == {}
