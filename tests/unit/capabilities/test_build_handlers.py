"""Unit tests for build handlers (SIP-Enhanced-Agent-Build-Capabilities).

Tests DevelopmentDevelopHandler and QATestHandler in
``squadops.capabilities.handlers.cycle_tasks``.

Part of Phase 1.
"""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from squadops.capabilities.handlers.cycle_tasks import (
    DevelopmentDevelopHandler,
    QATestHandler,
)
from squadops.capabilities.handlers.base import HandlerEvidence, HandlerResult
from squadops.capabilities.handlers.test_runner import TestRunResult
from squadops.bootstrap.handlers import HANDLER_CONFIGS
from squadops.llm.exceptions import LLMConnectionError
from squadops.llm.models import ChatMessage

_MOCK_TEST_RESULT_PASSED = TestRunResult(
    executed=True, exit_code=0, stdout="1 passed", stderr="",
    test_file_count=2, source_file_count=2,
)

_MOCK_TEST_RESULT_FAILED = TestRunResult(
    executed=True, exit_code=1, stdout="1 failed", stderr="AssertionError",
    test_file_count=2, source_file_count=2,
)

_MOCK_TEST_RESULT_NOT_RUN = TestRunResult(
    executed=False, error="no test files provided",
    test_file_count=0, source_file_count=0,
)

_RUN_TESTS_PATH = "squadops.capabilities.handlers.test_runner.run_generated_tests"

pytestmark = [pytest.mark.domain_capabilities]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

LLM_MULTI_FILE_RESPONSE = (
    "Here are the source files:\n\n"
    "```python:src/main.py\n"
    "def main():\n"
    "    print('Hello from SquadOps!')\n"
    "```\n\n"
    "```python:src/utils.py\n"
    "def helper():\n"
    "    return 42\n"
    "```\n"
)

LLM_SINGLE_FILE_RESPONSE = (
    "```python:app.py\n"
    "print('hello')\n"
    "```\n"
)

LLM_NO_FENCES_RESPONSE = (
    "I have generated the code but forgot to use fenced blocks.\n"
    "def main(): pass\n"
)

LLM_TEST_FILE_RESPONSE = (
    "```python:tests/test_main.py\n"
    "def test_main():\n"
    "    assert True\n"
    "```\n\n"
    "```python:tests/test_utils.py\n"
    "def test_helper():\n"
    "    from src.utils import helper\n"
    "    assert helper() == 42\n"
    "```\n"
)


@pytest.fixture()
def mock_context():
    """Return a MagicMock with llm.chat and prompt_service stubbed."""
    ctx = MagicMock()
    ctx.ports.llm.chat = AsyncMock(
        return_value=ChatMessage(role="assistant", content=LLM_MULTI_FILE_RESPONSE),
    )
    ctx.ports.llm.default_model = "test-model"
    assembled = MagicMock()
    assembled.content = "You are a dev agent."
    ctx.ports.prompt_service.get_system_prompt = MagicMock(return_value=assembled)
    # No LangFuse by default
    ctx.ports.llm_observability = None
    ctx.correlation_context = None
    return ctx


@pytest.fixture()
def build_inputs():
    """Standard inputs for build handlers."""
    return {
        "prd": "Build a CLI tool that prints hello world.",
        "artifact_contents": {
            "implementation_plan.md": "# Plan\n\n1. Create main.py\n2. Add hello function",
            "strategy_analysis.md": "# Strategy\n\nSimple CLI approach.",
        },
    }


@pytest.fixture()
def qa_inputs():
    """Standard inputs for QA build handler."""
    return {
        "prd": "Build a CLI tool that prints hello world.",
        "artifact_contents": {
            "validation_plan.md": "# Test Plan\n\n1. Test main function",
            "src/main.py": "def main():\n    print('hello')",
            "src/utils.py": "def helper():\n    return 42",
        },
    }


# ---------------------------------------------------------------------------
# DevelopmentDevelopHandler
# ---------------------------------------------------------------------------


class TestDevBuildMultiFile:
    async def test_dev_build_multi_file(self, mock_context, build_inputs):
        handler = DevelopmentDevelopHandler()
        result = await handler.handle(mock_context, build_inputs)

        assert result.success is True
        artifacts = result.outputs["artifacts"]
        assert len(artifacts) == 2
        assert artifacts[0]["name"] == "src/main.py"
        assert artifacts[0]["type"] == "source"
        assert artifacts[0]["media_type"] == "text/x-python"
        assert artifacts[1]["name"] == "src/utils.py"

    async def test_dev_build_single_file(self, mock_context, build_inputs):
        mock_context.ports.llm.chat = AsyncMock(
            return_value=ChatMessage(role="assistant", content=LLM_SINGLE_FILE_RESPONSE),
        )
        handler = DevelopmentDevelopHandler()
        result = await handler.handle(mock_context, build_inputs)

        assert result.success is True
        assert len(result.outputs["artifacts"]) == 1
        assert result.outputs["artifacts"][0]["name"] == "app.py"

    async def test_dev_build_summary(self, mock_context, build_inputs):
        handler = DevelopmentDevelopHandler()
        result = await handler.handle(mock_context, build_inputs)

        assert "[dev]" in result.outputs["summary"]
        assert result.outputs["role"] == "dev"


class TestDevBuildParseFailure:
    async def test_dev_build_parse_failure_returns_failed(self, mock_context, build_inputs):
        mock_context.ports.llm.chat = AsyncMock(
            return_value=ChatMessage(role="assistant", content=LLM_NO_FENCES_RESPONSE),
        )
        handler = DevelopmentDevelopHandler()
        result = await handler.handle(mock_context, build_inputs)

        assert result.success is False
        assert "No valid fenced code blocks found" in result.error
        # Raw response preserved in build_warnings.md artifact
        artifacts = result.outputs.get("artifacts", [])
        assert len(artifacts) == 1
        assert artifacts[0]["name"] == "build_warnings.md"


class TestDevBuildLLMError:
    async def test_dev_build_llm_error(self, mock_context, build_inputs):
        mock_context.ports.llm.chat = AsyncMock(side_effect=LLMConnectionError("timeout"))
        handler = DevelopmentDevelopHandler()
        result = await handler.handle(mock_context, build_inputs)

        assert result.success is False
        assert "timeout" in result.error


class TestDevBuildValidation:
    def test_missing_prd(self):
        handler = DevelopmentDevelopHandler()
        errors = handler.validate_inputs({"artifact_contents": {}})
        assert "'prd' is required" in errors

    def test_missing_artifact_contents_and_vault(self):
        handler = DevelopmentDevelopHandler()
        errors = handler.validate_inputs({"prd": "something"})
        assert any("artifact_contents" in e for e in errors)

    def test_valid_inputs(self):
        handler = DevelopmentDevelopHandler()
        errors = handler.validate_inputs({
            "prd": "something",
            "artifact_contents": {"plan.md": "content"},
        })
        assert errors == []


class TestDevBuildEvidence:
    async def test_evidence_present(self, mock_context, build_inputs):
        handler = DevelopmentDevelopHandler()
        result = await handler.handle(mock_context, build_inputs)

        assert isinstance(result._evidence, HandlerEvidence)
        assert result.evidence.capability_id == "development.develop"
        assert result.evidence.handler_name == "development_develop_handler"
        assert result.evidence.duration_ms >= 0


class TestDevBuildPromptContent:
    async def test_prompt_includes_plan_artifacts(self, mock_context, build_inputs):
        handler = DevelopmentDevelopHandler()
        await handler.handle(mock_context, build_inputs)

        call_args = mock_context.ports.llm.chat.call_args
        messages = call_args[0][0]
        user_msg = messages[1].content
        assert "Implementation Plan" in user_msg
        assert "Strategy Analysis" in user_msg
        assert "Build a CLI tool" in user_msg


class TestDevBuildFileClassification:
    async def test_yaml_classified_as_config(self, mock_context, build_inputs):
        yaml_response = (
            "```yaml:config.yaml\n"
            "key: value\n"
            "```\n"
        )
        mock_context.ports.llm.chat = AsyncMock(
            return_value=ChatMessage(role="assistant", content=yaml_response),
        )
        handler = DevelopmentDevelopHandler()
        result = await handler.handle(mock_context, build_inputs)

        assert result.success is True
        assert result.outputs["artifacts"][0]["type"] == "config"
        assert result.outputs["artifacts"][0]["media_type"] == "text/yaml"


# ---------------------------------------------------------------------------
# QATestHandler
# ---------------------------------------------------------------------------


class TestQABuildProducesTestArtifacts:
    @patch(_RUN_TESTS_PATH, return_value=_MOCK_TEST_RESULT_PASSED)
    async def test_qa_build_produces_test_artifacts(self, _mock_run, mock_context, qa_inputs):
        mock_context.ports.llm.chat = AsyncMock(
            return_value=ChatMessage(role="assistant", content=LLM_TEST_FILE_RESPONSE),
        )
        handler = QATestHandler()
        result = await handler.handle(mock_context, qa_inputs)

        assert result.success is True
        artifacts = result.outputs["artifacts"]
        # 2 test files + 1 test_report.md
        assert len(artifacts) == 3
        # First two are test artifacts
        for art in artifacts[:2]:
            assert art["type"] == "test"
        assert artifacts[0]["name"] == "tests/test_main.py"
        assert artifacts[1]["name"] == "tests/test_utils.py"
        # Last is the test report
        assert artifacts[2]["name"] == "test_report.md"
        assert artifacts[2]["type"] == "test_report"

    @patch(_RUN_TESTS_PATH, return_value=_MOCK_TEST_RESULT_PASSED)
    async def test_qa_build_summary(self, _mock_run, mock_context, qa_inputs):
        mock_context.ports.llm.chat = AsyncMock(
            return_value=ChatMessage(role="assistant", content=LLM_TEST_FILE_RESPONSE),
        )
        handler = QATestHandler()
        result = await handler.handle(mock_context, qa_inputs)

        assert "[qa]" in result.outputs["summary"]
        assert result.outputs["role"] == "qa"


class TestQABuildParseFailure:
    async def test_qa_build_parse_failure(self, mock_context, qa_inputs):
        mock_context.ports.llm.chat = AsyncMock(
            return_value=ChatMessage(role="assistant", content=LLM_NO_FENCES_RESPONSE),
        )
        handler = QATestHandler()
        result = await handler.handle(mock_context, qa_inputs)

        assert result.success is False
        assert "No valid fenced code blocks found" in result.error


class TestQABuildPromptContent:
    @patch(_RUN_TESTS_PATH, return_value=_MOCK_TEST_RESULT_PASSED)
    async def test_prompt_includes_source_and_plan(self, _mock_run, mock_context, qa_inputs):
        mock_context.ports.llm.chat = AsyncMock(
            return_value=ChatMessage(role="assistant", content=LLM_TEST_FILE_RESPONSE),
        )
        handler = QATestHandler()
        await handler.handle(mock_context, qa_inputs)

        call_args = mock_context.ports.llm.chat.call_args
        messages = call_args[0][0]
        user_msg = messages[1].content
        assert "Validation Plan" in user_msg
        assert "Source Files to Test" in user_msg
        assert "def main():" in user_msg


# ---------------------------------------------------------------------------
# Bootstrap registration
# ---------------------------------------------------------------------------


class TestBuildHandlerBootstrap:
    def test_dev_build_in_handler_configs(self):
        registered = {entry[0]: entry[1] for entry in HANDLER_CONFIGS}
        assert DevelopmentDevelopHandler in registered
        assert registered[DevelopmentDevelopHandler] == ("dev",)

    def test_qa_build_in_handler_configs(self):
        registered = {entry[0]: entry[1] for entry in HANDLER_CONFIGS}
        assert QATestHandler in registered
        assert registered[QATestHandler] == ("qa",)


# ---------------------------------------------------------------------------
# Capability ID and properties
# ---------------------------------------------------------------------------


class TestBuildHandlerProperties:
    def test_dev_build_capability_id(self):
        handler = DevelopmentDevelopHandler()
        assert handler.capability_id == "development.develop"
        assert handler.name == "development_develop_handler"
        assert "dev" in handler.description

    def test_qa_build_capability_id(self):
        handler = QATestHandler()
        assert handler.capability_id == "qa.test"
        assert handler.name == "qa_test_handler"
        assert "qa" in handler.description


# ---------------------------------------------------------------------------
# Vault fallback (D3)
# ---------------------------------------------------------------------------


class TestDevBuildVaultFallback:
    async def test_vault_fallback_resolves_missing_content(self, mock_context):
        """When artifact_contents is empty, vault fallback resolves from refs."""
        from datetime import datetime, timezone

        from squadops.cycles.models import ArtifactRef

        plan_ref = ArtifactRef(
            artifact_id="art_001",
            project_id="test",
            artifact_type="document",
            filename="implementation_plan.md",
            content_hash="abc",
            size_bytes=100,
            media_type="text/markdown",
            created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        )
        vault = AsyncMock()
        vault.retrieve = AsyncMock(return_value=(plan_ref, b"# Plan\nBuild it."))

        inputs = {
            "prd": "Build a CLI tool.",
            "artifact_contents": {},
            "artifact_vault": vault,
            "artifact_refs": ["art_001"],
        }

        handler = DevelopmentDevelopHandler()
        result = await handler.handle(mock_context, inputs)

        assert result.success is True
        # Called twice: once for implementation_plan, once for strategy_analysis
        assert vault.retrieve.call_count == 2
        vault.retrieve.assert_any_call("art_001")
        # Plan content should appear in the LLM prompt
        call_args = mock_context.ports.llm.chat.call_args
        user_msg = call_args[0][0][1].content
        assert "Plan" in user_msg

    async def test_vault_fallback_fails_when_vault_has_no_match(self, mock_context):
        """When vault has no matching artifacts, handler returns failure."""
        from datetime import datetime, timezone

        from squadops.cycles.models import ArtifactRef

        other_ref = ArtifactRef(
            artifact_id="art_099",
            project_id="test",
            artifact_type="document",
            filename="unrelated.md",
            content_hash="abc",
            size_bytes=100,
            media_type="text/markdown",
            created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        )
        vault = AsyncMock()
        vault.retrieve = AsyncMock(return_value=(other_ref, b"unrelated"))

        inputs = {
            "prd": "Build a CLI tool.",
            "artifact_contents": {},
            "artifact_vault": vault,
            "artifact_refs": ["art_099"],
        }

        handler = DevelopmentDevelopHandler()
        result = await handler.handle(mock_context, inputs)

        assert result.success is False
        assert "Required plan artifacts not available" in result.error


class TestQABuildVaultFallback:
    @patch(_RUN_TESTS_PATH, return_value=_MOCK_TEST_RESULT_PASSED)
    async def test_qa_vault_fallback_resolves_validation_plan(self, _mock_run, mock_context):
        """QA handler falls back to vault for validation_plan.md."""
        from datetime import datetime, timezone

        from squadops.cycles.models import ArtifactRef

        mock_context.ports.llm.chat = AsyncMock(
            return_value=ChatMessage(role="assistant", content=LLM_TEST_FILE_RESPONSE),
        )

        plan_ref = ArtifactRef(
            artifact_id="art_val",
            project_id="test",
            artifact_type="document",
            filename="validation_plan.md",
            content_hash="abc",
            size_bytes=100,
            media_type="text/markdown",
            created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        )
        vault = AsyncMock()
        vault.retrieve = AsyncMock(return_value=(plan_ref, b"# Test Plan"))

        inputs = {
            "prd": "Build a CLI tool.",
            "artifact_contents": {
                "src/main.py": "def main(): pass",
            },
            "artifact_vault": vault,
            "artifact_refs": ["art_val"],
        }

        handler = QATestHandler()
        result = await handler.handle(mock_context, inputs)

        assert result.success is True
        vault.retrieve.assert_called_once_with("art_val")


# ---------------------------------------------------------------------------
# LangFuse generation recording
# ---------------------------------------------------------------------------


class TestDevBuildLangFuseRecording:
    async def test_langfuse_generation_recorded(self, build_inputs):
        """When correlation_context and llm_obs are present, generation is recorded."""
        ctx = MagicMock()
        ctx.ports.llm.chat = AsyncMock(
            return_value=ChatMessage(
                role="assistant", content=LLM_MULTI_FILE_RESPONSE,
            ),
        )
        ctx.ports.llm.default_model = "ollama/llama3"
        assembled = MagicMock()
        assembled.content = "You are a dev agent."
        ctx.ports.prompt_service.get_system_prompt = MagicMock(return_value=assembled)

        # Enable LangFuse
        llm_obs = MagicMock()
        ctx.ports.llm_observability = llm_obs
        ctx.correlation_context = MagicMock()

        handler = DevelopmentDevelopHandler()
        result = await handler.handle(ctx, build_inputs)

        assert result.success is True
        llm_obs.record_generation.assert_called_once()
        call_args = llm_obs.record_generation.call_args
        assert call_args[0][0] is ctx.correlation_context  # first arg: context
        gen_record = call_args[0][1]
        assert gen_record.model == "ollama/llama3"


class TestQABuildLangFuseRecording:
    @patch(_RUN_TESTS_PATH, return_value=_MOCK_TEST_RESULT_PASSED)
    async def test_langfuse_generation_recorded(self, _mock_run, qa_inputs):
        """QA handler records generation when LangFuse is enabled."""
        ctx = MagicMock()
        ctx.ports.llm.chat = AsyncMock(
            return_value=ChatMessage(
                role="assistant", content=LLM_TEST_FILE_RESPONSE,
            ),
        )
        ctx.ports.llm.default_model = "ollama/llama3"
        assembled = MagicMock()
        assembled.content = "You are a QA agent."
        ctx.ports.prompt_service.get_system_prompt = MagicMock(return_value=assembled)

        llm_obs = MagicMock()
        ctx.ports.llm_observability = llm_obs
        ctx.correlation_context = MagicMock()

        handler = QATestHandler()
        result = await handler.handle(ctx, qa_inputs)

        assert result.success is True
        llm_obs.record_generation.assert_called_once()


# ---------------------------------------------------------------------------
# QA test execution integration
# ---------------------------------------------------------------------------


class TestQATestReportArtifact:
    @patch(_RUN_TESTS_PATH, return_value=_MOCK_TEST_RESULT_PASSED)
    async def test_test_report_artifact_present(self, _mock_run, mock_context, qa_inputs):
        """test_report.md artifact is always present when tests are extracted."""
        mock_context.ports.llm.chat = AsyncMock(
            return_value=ChatMessage(role="assistant", content=LLM_TEST_FILE_RESPONSE),
        )
        handler = QATestHandler()
        result = await handler.handle(mock_context, qa_inputs)

        report_arts = [a for a in result.outputs["artifacts"] if a["name"] == "test_report.md"]
        assert len(report_arts) == 1
        assert report_arts[0]["type"] == "test_report"
        assert report_arts[0]["media_type"] == "text/markdown"
        assert "all tests passed" in report_arts[0]["content"]


class TestQAHandlerSucceedsWhenTestsFail:
    @patch(_RUN_TESTS_PATH, return_value=_MOCK_TEST_RESULT_FAILED)
    async def test_handler_succeeds_when_tests_fail(self, _mock_run, mock_context, qa_inputs):
        """Handler returns success=True even when tests fail — failures are evidence."""
        mock_context.ports.llm.chat = AsyncMock(
            return_value=ChatMessage(role="assistant", content=LLM_TEST_FILE_RESPONSE),
        )
        handler = QATestHandler()
        result = await handler.handle(mock_context, qa_inputs)

        assert result.success is True
        assert result.outputs["test_result"]["tests_passed"] is False
        assert result.outputs["test_result"]["exit_code"] == 1


class TestQAHandlerSucceedsWhenTestsNotExecuted:
    @patch(_RUN_TESTS_PATH, return_value=_MOCK_TEST_RESULT_NOT_RUN)
    async def test_handler_succeeds_when_tests_not_executed(self, _mock_run, mock_context, qa_inputs):
        """Handler returns success=True even when tests couldn't run."""
        mock_context.ports.llm.chat = AsyncMock(
            return_value=ChatMessage(role="assistant", content=LLM_TEST_FILE_RESPONSE),
        )
        handler = QATestHandler()
        result = await handler.handle(mock_context, qa_inputs)

        assert result.success is True
        assert result.outputs["test_result"]["executed"] is False


class TestQASummaryIncludesTestOutcome:
    @patch(_RUN_TESTS_PATH, return_value=_MOCK_TEST_RESULT_PASSED)
    async def test_summary_includes_passed(self, _mock_run, mock_context, qa_inputs):
        mock_context.ports.llm.chat = AsyncMock(
            return_value=ChatMessage(role="assistant", content=LLM_TEST_FILE_RESPONSE),
        )
        handler = QATestHandler()
        result = await handler.handle(mock_context, qa_inputs)
        assert "all tests passed" in result.outputs["summary"]

    @patch(_RUN_TESTS_PATH, return_value=_MOCK_TEST_RESULT_FAILED)
    async def test_summary_includes_failed(self, _mock_run, mock_context, qa_inputs):
        mock_context.ports.llm.chat = AsyncMock(
            return_value=ChatMessage(role="assistant", content=LLM_TEST_FILE_RESPONSE),
        )
        handler = QATestHandler()
        result = await handler.handle(mock_context, qa_inputs)
        assert "tests failed" in result.outputs["summary"]

    @patch(_RUN_TESTS_PATH, return_value=_MOCK_TEST_RESULT_NOT_RUN)
    async def test_summary_includes_not_run(self, _mock_run, mock_context, qa_inputs):
        mock_context.ports.llm.chat = AsyncMock(
            return_value=ChatMessage(role="assistant", content=LLM_TEST_FILE_RESPONSE),
        )
        handler = QATestHandler()
        result = await handler.handle(mock_context, qa_inputs)
        assert "tests not run" in result.outputs["summary"]
