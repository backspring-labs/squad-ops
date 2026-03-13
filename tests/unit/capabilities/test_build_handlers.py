"""Unit tests for build handlers (SIP-Enhanced-Agent-Build-Capabilities).

Tests DevelopmentDevelopHandler and QATestHandler in
``squadops.capabilities.handlers.cycle_tasks``.

Part of Phase 1.
"""

from __future__ import annotations

from datetime import UTC
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from squadops.bootstrap.handlers import HANDLER_CONFIGS
from squadops.capabilities.handlers.base import HandlerEvidence
from squadops.capabilities.handlers.cycle_tasks import (
    DevelopmentDevelopHandler,
    QATestHandler,
    _classify_file,
    _is_test_file,
)
from squadops.capabilities.handlers.test_runner import RunTestsResult
from squadops.llm.exceptions import LLMConnectionError
from squadops.llm.models import ChatMessage

_MOCK_TEST_RESULT_PASSED = RunTestsResult(
    executed=True,
    exit_code=0,
    stdout="1 passed",
    stderr="",
    test_file_count=2,
    source_file_count=2,
)

_MOCK_TEST_RESULT_FAILED = RunTestsResult(
    executed=True,
    exit_code=1,
    stdout="1 failed",
    stderr="AssertionError",
    test_file_count=2,
    source_file_count=2,
)

_MOCK_TEST_RESULT_NOT_RUN = RunTestsResult(
    executed=False,
    error="no test files provided",
    test_file_count=0,
    source_file_count=0,
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

LLM_SINGLE_FILE_RESPONSE = "```python:app.py\nprint('hello')\n```\n"

LLM_NO_FENCES_RESPONSE = (
    "I have generated the code but forgot to use fenced blocks.\ndef main(): pass\n"
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
    ctx.ports.request_renderer = None
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
        errors = handler.validate_inputs(
            {
                "prd": "something",
                "artifact_contents": {"plan.md": "content"},
            }
        )
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
        yaml_response = "```yaml:config.yaml\nkey: value\n```\n"
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
        from datetime import datetime

        from squadops.cycles.models import ArtifactRef

        plan_ref = ArtifactRef(
            artifact_id="art_001",
            project_id="test",
            artifact_type="document",
            filename="implementation_plan.md",
            content_hash="abc",
            size_bytes=100,
            media_type="text/markdown",
            created_at=datetime(2026, 1, 1, tzinfo=UTC),
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
        from datetime import datetime

        from squadops.cycles.models import ArtifactRef

        other_ref = ArtifactRef(
            artifact_id="art_099",
            project_id="test",
            artifact_type="document",
            filename="unrelated.md",
            content_hash="abc",
            size_bytes=100,
            media_type="text/markdown",
            created_at=datetime(2026, 1, 1, tzinfo=UTC),
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
        from datetime import datetime

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
            created_at=datetime(2026, 1, 1, tzinfo=UTC),
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
                role="assistant",
                content=LLM_MULTI_FILE_RESPONSE,
            ),
        )
        ctx.ports.llm.default_model = "ollama/llama3"
        assembled = MagicMock()
        assembled.content = "You are a dev agent."
        ctx.ports.prompt_service.get_system_prompt = MagicMock(return_value=assembled)

        # Enable LangFuse
        llm_obs = MagicMock()
        ctx.ports.llm_observability = llm_obs
        ctx.ports.request_renderer = None
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
                role="assistant",
                content=LLM_TEST_FILE_RESPONSE,
            ),
        )
        ctx.ports.llm.default_model = "ollama/llama3"
        assembled = MagicMock()
        assembled.content = "You are a QA agent."
        ctx.ports.prompt_service.get_system_prompt = MagicMock(return_value=assembled)

        llm_obs = MagicMock()
        ctx.ports.llm_observability = llm_obs
        ctx.ports.request_renderer = None
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
    async def test_handler_succeeds_when_tests_not_executed(
        self, _mock_run, mock_context, qa_inputs
    ):
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


# ---------------------------------------------------------------------------
# File classification expansion (SIP-0072 Phase 1)
# ---------------------------------------------------------------------------


class TestClassifyFileJS:
    def test_js_classified_as_source(self):
        assert _classify_file("app.js") == ("source", "text/javascript")

    def test_jsx_classified_as_source(self):
        assert _classify_file("App.jsx") == ("source", "text/javascript")

    def test_mjs_classified_as_source(self):
        assert _classify_file("utils.mjs") == ("source", "text/javascript")

    def test_ts_classified_as_source(self):
        assert _classify_file("app.ts") == ("source", "text/typescript")

    def test_tsx_classified_as_source(self):
        assert _classify_file("App.tsx") == ("source", "text/typescript")


class TestClassifyFileWebAssets:
    def test_css_classified_as_source(self):
        assert _classify_file("styles.css") == ("source", "text/css")

    def test_html_classified_as_source(self):
        assert _classify_file("index.html") == ("source", "text/html")


class TestClassifyFileFilenameMap:
    def test_package_json_classified_as_config(self):
        assert _classify_file("package.json") == ("config", "application/json")

    def test_vite_config_classified_as_config(self):
        assert _classify_file("vite.config.js") == ("config", "text/javascript")

    def test_tsconfig_classified_as_config(self):
        assert _classify_file("tsconfig.json") == ("config", "application/json")

    def test_requirements_txt_still_config(self):
        assert _classify_file("requirements.txt") == ("config", "text/plain")


class TestClassifyFileExistingBehavior:
    def test_py_still_source(self):
        assert _classify_file("main.py") == ("source", "text/x-python")

    def test_md_still_document(self):
        assert _classify_file("README.md") == ("document", "text/markdown")

    def test_yaml_still_config(self):
        assert _classify_file("config.yaml") == ("config", "text/yaml")

    def test_json_still_config(self):
        assert _classify_file("data.json") == ("config", "application/json")

    def test_filename_map_takes_precedence(self):
        """package.json uses filename map (config), not ext map (config)."""
        result = _classify_file("package.json")
        assert result == ("config", "application/json")


# ---------------------------------------------------------------------------
# _is_test_file helper (SIP-0072 Phase 2)
# ---------------------------------------------------------------------------


class TestIsTestFilePython:
    def test_test_prefix_py(self):
        assert _is_test_file("test_api.py", ("test_*.py", "*_test.py")) is True

    def test_suffix_py(self):
        assert _is_test_file("api_test.py", ("test_*.py", "*_test.py")) is True

    def test_non_test_py(self):
        assert _is_test_file("main.py", ("test_*.py", "*_test.py")) is False

    def test_nested_path(self):
        assert _is_test_file("tests/test_api.py", ("test_*.py", "*_test.py")) is True

    def test_deeply_nested_path(self):
        assert _is_test_file("backend/tests/test_api.py", ("test_*.py", "*_test.py")) is True


class TestIsTestFileJS:
    def test_test_jsx(self):
        assert _is_test_file("App.test.jsx", ("*.test.jsx", "*.test.js")) is True

    def test_test_js(self):
        assert _is_test_file("utils.test.js", ("*.test.jsx", "*.test.js")) is True

    def test_spec_jsx(self):
        assert _is_test_file("App.spec.jsx", ("*.spec.jsx",)) is True

    def test_non_test_jsx(self):
        assert _is_test_file("App.jsx", ("*.test.jsx", "*.test.js")) is False

    def test_dunder_tests_dir(self):
        assert (
            _is_test_file(
                "frontend/src/__tests__/App.test.jsx",
                ("*.test.jsx",),
            )
            is True
        )

    def test_dunder_tests_dir_even_without_pattern_match(self):
        """Files inside __tests__/ are test files regardless of pattern."""
        assert (
            _is_test_file(
                "frontend/src/__tests__/helpers.js",
                ("*.test.jsx",),
            )
            is True
        )


# ---------------------------------------------------------------------------
# DevelopmentDevelopHandler capability selection (SIP-0072 Phase 2)
# ---------------------------------------------------------------------------


class TestDevHandlerCapabilityDefault:
    async def test_default_capability_is_python_cli(self, mock_context, build_inputs):
        """Without resolved_config, handler defaults to python_cli."""
        handler = DevelopmentDevelopHandler()
        result = await handler.handle(mock_context, build_inputs)

        assert result.success is True
        call_args = mock_context.ports.llm.chat.call_args
        messages = call_args[0][0]
        system_msg = messages[0].content
        assert "Python package" in system_msg
        user_msg = messages[1].content
        assert "__init__.py" in user_msg

    async def test_explicit_python_cli(self, mock_context, build_inputs):
        """Explicit dev_capability=python_cli reproduces default behavior."""
        build_inputs["resolved_config"] = {"dev_capability": "python_cli"}
        handler = DevelopmentDevelopHandler()
        result = await handler.handle(mock_context, build_inputs)

        assert result.success is True
        call_args = mock_context.ports.llm.chat.call_args
        user_msg = call_args[0][0][1].content
        assert "RELATIVE imports" in user_msg
        assert "python -m" in user_msg


class TestDevHandlerFullstackCapability:
    async def test_fullstack_prompt_contains_backend_frontend(self, mock_context, build_inputs):
        build_inputs["resolved_config"] = {"dev_capability": "fullstack_fastapi_react"}
        handler = DevelopmentDevelopHandler()
        result = await handler.handle(mock_context, build_inputs)

        assert result.success is True
        call_args = mock_context.ports.llm.chat.call_args
        messages = call_args[0][0]
        user_msg = messages[1].content
        assert "backend/" in user_msg
        assert "frontend/" in user_msg

    async def test_fullstack_prompt_does_not_contain_python_only_guidance(
        self,
        mock_context,
        build_inputs,
    ):
        build_inputs["resolved_config"] = {"dev_capability": "fullstack_fastapi_react"}
        handler = DevelopmentDevelopHandler()
        await handler.handle(mock_context, build_inputs)

        call_args = mock_context.ports.llm.chat.call_args
        user_msg = call_args[0][0][1].content
        assert "__init__.py" not in user_msg
        assert "python -m" not in user_msg

    async def test_fullstack_system_prompt_mentions_fullstack(self, mock_context, build_inputs):
        build_inputs["resolved_config"] = {"dev_capability": "fullstack_fastapi_react"}
        handler = DevelopmentDevelopHandler()
        await handler.handle(mock_context, build_inputs)

        call_args = mock_context.ports.llm.chat.call_args
        system_msg = call_args[0][0][0].content
        assert "fullstack" in system_msg.lower() or "backend" in system_msg.lower()


class TestDevHandlerUnknownCapability:
    async def test_unknown_capability_fails(self, mock_context, build_inputs):
        build_inputs["resolved_config"] = {"dev_capability": "unknown_stack"}
        handler = DevelopmentDevelopHandler()
        result = await handler.handle(mock_context, build_inputs)

        assert result.success is False
        assert "Unknown" in result.error
        assert "python_cli" in result.error

    async def test_unknown_capability_does_not_call_llm(self, mock_context, build_inputs):
        build_inputs["resolved_config"] = {"dev_capability": "unknown_stack"}
        handler = DevelopmentDevelopHandler()
        await handler.handle(mock_context, build_inputs)

        mock_context.ports.llm.chat.assert_not_called()


# ---------------------------------------------------------------------------
# QATestHandler capability selection (SIP-0072 Phase 2)
# ---------------------------------------------------------------------------


class TestQASourceFilterPythonCli:
    @patch(_RUN_TESTS_PATH, return_value=_MOCK_TEST_RESULT_PASSED)
    async def test_python_cli_picks_py_files(self, _mock_run, mock_context, qa_inputs):
        """Default capability filters to .py files only."""
        mock_context.ports.llm.chat = AsyncMock(
            return_value=ChatMessage(role="assistant", content=LLM_TEST_FILE_RESPONSE),
        )
        handler = QATestHandler()
        await handler.handle(mock_context, qa_inputs)

        call_args = mock_context.ports.llm.chat.call_args
        user_msg = call_args[0][0][1].content
        assert "src/main.py" in user_msg
        assert "src/utils.py" in user_msg

    @patch(_RUN_TESTS_PATH, return_value=_MOCK_TEST_RESULT_PASSED)
    async def test_python_cli_excludes_test_files(self, _mock_run, mock_context):
        """Source filter excludes test_*.py files."""
        mock_context.ports.llm.chat = AsyncMock(
            return_value=ChatMessage(role="assistant", content=LLM_TEST_FILE_RESPONSE),
        )
        inputs = {
            "prd": "Test project.",
            "artifact_contents": {
                "validation_plan.md": "# Plan",
                "src/main.py": "def main(): pass",
                "test_main.py": "def test_main(): pass",
            },
        }
        handler = QATestHandler()
        await handler.handle(mock_context, inputs)

        call_args = mock_context.ports.llm.chat.call_args
        user_msg = call_args[0][0][1].content
        assert "src/main.py" in user_msg
        assert "test_main.py" not in user_msg


class TestQASourceFilterFullstack:
    @patch(_RUN_TESTS_PATH, return_value=_MOCK_TEST_RESULT_PASSED)
    async def test_fullstack_picks_py_and_jsx(self, _mock_run, mock_context):
        """Fullstack capability includes both .py and .jsx source files."""
        mock_context.ports.llm.chat = AsyncMock(
            return_value=ChatMessage(role="assistant", content=LLM_TEST_FILE_RESPONSE),
        )
        inputs = {
            "prd": "Fullstack app.",
            "resolved_config": {"dev_capability": "fullstack_fastapi_react"},
            "artifact_contents": {
                "validation_plan.md": "# Plan",
                "backend/main.py": "from fastapi import FastAPI",
                "frontend/src/App.jsx": "export default function App() {}",
                "frontend/src/App.test.jsx": "test('renders', () => {})",
                "backend/tests/test_api.py": "def test_api(): pass",
            },
        }
        handler = QATestHandler()
        await handler.handle(mock_context, inputs)

        call_args = mock_context.ports.llm.chat.call_args
        user_msg = call_args[0][0][1].content
        # Source files included in ### headings
        assert "### backend/main.py" in user_msg
        assert "### frontend/src/App.jsx" in user_msg
        # Test files excluded from ### headings
        assert "### frontend/src/App.test.jsx" not in user_msg
        assert "### backend/tests/test_api.py" not in user_msg


class TestQAPromptCapability:
    """test_prompt_supplement appears in user prompt (not system prompt)."""

    @patch(_RUN_TESTS_PATH, return_value=_MOCK_TEST_RESULT_PASSED)
    async def test_python_cli_user_prompt_mentions_pytest(self, _mock_run, mock_context, qa_inputs):
        mock_context.ports.llm.chat = AsyncMock(
            return_value=ChatMessage(role="assistant", content=LLM_TEST_FILE_RESPONSE),
        )
        handler = QATestHandler()
        await handler.handle(mock_context, qa_inputs)

        call_args = mock_context.ports.llm.chat.call_args
        user_msg = call_args[0][0][1].content
        assert "pytest" in user_msg

    @patch(_RUN_TESTS_PATH, return_value=_MOCK_TEST_RESULT_PASSED)
    async def test_react_app_user_prompt_mentions_vitest(self, _mock_run, mock_context):
        mock_context.ports.llm.chat = AsyncMock(
            return_value=ChatMessage(role="assistant", content=LLM_TEST_FILE_RESPONSE),
        )
        inputs = {
            "prd": "React app.",
            "resolved_config": {"dev_capability": "react_app"},
            "artifact_contents": {
                "validation_plan.md": "# Plan",
                "src/App.jsx": "export default function App() {}",
            },
        }
        handler = QATestHandler()
        await handler.handle(mock_context, inputs)

        call_args = mock_context.ports.llm.chat.call_args
        user_msg = call_args[0][0][1].content
        assert "vitest" in user_msg.lower()

    @patch(_RUN_TESTS_PATH, return_value=_MOCK_TEST_RESULT_PASSED)
    async def test_fullstack_user_prompt_mentions_both(self, _mock_run, mock_context):
        mock_context.ports.llm.chat = AsyncMock(
            return_value=ChatMessage(role="assistant", content=LLM_TEST_FILE_RESPONSE),
        )
        inputs = {
            "prd": "Fullstack app.",
            "resolved_config": {"dev_capability": "fullstack_fastapi_react"},
            "artifact_contents": {
                "validation_plan.md": "# Plan",
                "backend/main.py": "from fastapi import FastAPI",
            },
        }
        handler = QATestHandler()
        await handler.handle(mock_context, inputs)

        call_args = mock_context.ports.llm.chat.call_args
        user_msg = call_args[0][0][1].content
        assert "pytest" in user_msg
        assert "vitest" in user_msg.lower()


class TestQAUnknownCapability:
    async def test_unknown_capability_fails(self, mock_context, qa_inputs):
        qa_inputs["resolved_config"] = {"dev_capability": "nonexistent"}
        handler = QATestHandler()
        result = await handler.handle(mock_context, qa_inputs)

        assert result.success is False
        assert "Unknown" in result.error


class TestQAFenceLang:
    def test_py_gets_python_fence(self):
        assert QATestHandler._fence_lang("backend/main.py") == "python"

    def test_jsx_gets_javascript_fence(self):
        assert QATestHandler._fence_lang("frontend/App.jsx") == "javascript"

    def test_js_gets_javascript_fence(self):
        assert QATestHandler._fence_lang("utils.js") == "javascript"

    def test_ts_gets_typescript_fence(self):
        assert QATestHandler._fence_lang("app.ts") == "typescript"

    def test_tsx_gets_typescript_fence(self):
        assert QATestHandler._fence_lang("Component.tsx") == "typescript"

    def test_mjs_gets_javascript_fence(self):
        assert QATestHandler._fence_lang("module.mjs") == "javascript"

    def test_unknown_defaults_to_python(self):
        assert QATestHandler._fence_lang("data.yaml") == "python"


class TestQAUserPromptFenceLang:
    @patch(_RUN_TESTS_PATH, return_value=_MOCK_TEST_RESULT_PASSED)
    async def test_jsx_files_fenced_as_javascript(self, _mock_run, mock_context):
        """JSX source files use ```javascript fences, not ```python."""
        mock_context.ports.llm.chat = AsyncMock(
            return_value=ChatMessage(role="assistant", content=LLM_TEST_FILE_RESPONSE),
        )
        inputs = {
            "prd": "React app.",
            "resolved_config": {"dev_capability": "react_app"},
            "artifact_contents": {
                "validation_plan.md": "# Plan",
                "src/App.jsx": "export default function App() {}",
            },
        }
        handler = QATestHandler()
        await handler.handle(mock_context, inputs)

        call_args = mock_context.ports.llm.chat.call_args
        user_msg = call_args[0][0][1].content
        assert "```javascript" in user_msg
        assert "```python" not in user_msg


# ---------------------------------------------------------------------------
# SIP-0073: Token budget + timeout wiring
# ---------------------------------------------------------------------------


class TestDevHandlerTokenBudget:
    """Dev handler passes max_tokens and timeout_seconds to chat()."""

    async def test_python_cli_max_tokens(self, mock_context, build_inputs):
        """Default python_cli → max_tokens=4000."""
        handler = DevelopmentDevelopHandler()
        await handler.handle(mock_context, build_inputs)

        call_kwargs = mock_context.ports.llm.chat.call_args.kwargs
        assert call_kwargs["max_tokens"] == 4000

    async def test_fullstack_max_tokens(self, mock_context, build_inputs):
        """fullstack_fastapi_react → max_tokens=12000."""
        build_inputs["resolved_config"] = {"dev_capability": "fullstack_fastapi_react"}
        handler = DevelopmentDevelopHandler()
        await handler.handle(mock_context, build_inputs)

        call_kwargs = mock_context.ports.llm.chat.call_args.kwargs
        assert call_kwargs["max_tokens"] == 12000

    async def test_model_spec_caps_tokens(self, mock_context, build_inputs):
        """When model spec has lower limit, max_tokens is capped."""
        # qwen2.5:7b has default_max_completion=4096
        mock_context.ports.llm.default_model = "qwen2.5:7b"
        build_inputs["resolved_config"] = {"dev_capability": "fullstack_fastapi_react"}
        handler = DevelopmentDevelopHandler()
        await handler.handle(mock_context, build_inputs)

        call_kwargs = mock_context.ports.llm.chat.call_args.kwargs
        # min(12000, 4096) = 4096
        assert call_kwargs["max_tokens"] == 4096

    async def test_unknown_model_uses_capability_tokens(self, mock_context, build_inputs):
        """Unknown model → no capping, uses capability's max_completion_tokens."""
        mock_context.ports.llm.default_model = "unknown"
        handler = DevelopmentDevelopHandler()
        await handler.handle(mock_context, build_inputs)

        call_kwargs = mock_context.ports.llm.chat.call_args.kwargs
        assert call_kwargs["max_tokens"] == 4000

    async def test_default_timeout(self, mock_context, build_inputs):
        """No generation_timeout in config → falls back to 300."""
        handler = DevelopmentDevelopHandler()
        await handler.handle(mock_context, build_inputs)

        call_kwargs = mock_context.ports.llm.chat.call_args.kwargs
        assert call_kwargs["timeout_seconds"] == 300

    async def test_config_timeout(self, mock_context, build_inputs):
        """generation_timeout from resolved_config is forwarded."""
        build_inputs["resolved_config"] = {"generation_timeout": 600}
        handler = DevelopmentDevelopHandler()
        await handler.handle(mock_context, build_inputs)

        call_kwargs = mock_context.ports.llm.chat.call_args.kwargs
        assert call_kwargs["timeout_seconds"] == 600


class TestDevHandlerPromptGuard:
    """Dev handler catches prompt overflow ValueError."""

    async def test_prompt_overflow_returns_failure(self, mock_context, build_inputs):
        """When prompt exceeds context window, handler returns structured failure."""
        import json

        # Use a known small model and a very large PRD
        mock_context.ports.llm.default_model = "qwen2.5:7b"
        build_inputs["prd"] = "x" * 200000  # ~50K tokens, exceeds 8K context
        handler = DevelopmentDevelopHandler()
        result = await handler.handle(mock_context, build_inputs)

        assert result.success is False
        payload = json.loads(result.error)
        assert payload["error_code"] == "PROMPT_EXCEEDS_CONTEXT_WINDOW"
        mock_context.ports.llm.chat.assert_not_called()


class TestQAHandlerTokenBudget:
    """QA handler passes max_tokens and timeout_seconds to chat()."""

    @patch(_RUN_TESTS_PATH, return_value=_MOCK_TEST_RESULT_PASSED)
    async def test_python_cli_max_tokens(self, _mock_run, mock_context, qa_inputs):
        mock_context.ports.llm.chat = AsyncMock(
            return_value=ChatMessage(role="assistant", content=LLM_TEST_FILE_RESPONSE),
        )
        handler = QATestHandler()
        await handler.handle(mock_context, qa_inputs)

        call_kwargs = mock_context.ports.llm.chat.call_args.kwargs
        assert call_kwargs["max_tokens"] == 4000

    @patch(_RUN_TESTS_PATH, return_value=_MOCK_TEST_RESULT_PASSED)
    async def test_fullstack_max_tokens(self, _mock_run, mock_context, qa_inputs):
        mock_context.ports.llm.chat = AsyncMock(
            return_value=ChatMessage(role="assistant", content=LLM_TEST_FILE_RESPONSE),
        )
        qa_inputs["resolved_config"] = {"dev_capability": "fullstack_fastapi_react"}
        handler = QATestHandler()
        await handler.handle(mock_context, qa_inputs)

        call_kwargs = mock_context.ports.llm.chat.call_args.kwargs
        assert call_kwargs["max_tokens"] == 12000

    @patch(_RUN_TESTS_PATH, return_value=_MOCK_TEST_RESULT_PASSED)
    async def test_default_timeout(self, _mock_run, mock_context, qa_inputs):
        mock_context.ports.llm.chat = AsyncMock(
            return_value=ChatMessage(role="assistant", content=LLM_TEST_FILE_RESPONSE),
        )
        handler = QATestHandler()
        await handler.handle(mock_context, qa_inputs)

        call_kwargs = mock_context.ports.llm.chat.call_args.kwargs
        assert call_kwargs["timeout_seconds"] == 300


class TestQAHandlerTestTimeout:
    """QA handler passes capability.test_timeout_seconds to test runner."""

    @patch(_RUN_TESTS_PATH, return_value=_MOCK_TEST_RESULT_PASSED)
    async def test_python_cli_test_timeout(self, mock_run, mock_context, qa_inputs):
        mock_context.ports.llm.chat = AsyncMock(
            return_value=ChatMessage(role="assistant", content=LLM_TEST_FILE_RESPONSE),
        )
        handler = QATestHandler()
        await handler.handle(mock_context, qa_inputs)

        call_kwargs = mock_run.call_args.kwargs
        assert call_kwargs["timeout_seconds"] == 60

    @patch(_RUN_TESTS_PATH, return_value=_MOCK_TEST_RESULT_PASSED)
    async def test_fullstack_test_timeout(self, _mock_run, mock_context, qa_inputs):
        """fullstack_fastapi_react → test runner gets timeout_seconds=180."""
        mock_context.ports.llm.chat = AsyncMock(
            return_value=ChatMessage(role="assistant", content=LLM_TEST_FILE_RESPONSE),
        )
        qa_inputs["resolved_config"] = {"dev_capability": "fullstack_fastapi_react"}
        qa_inputs["artifact_contents"]["backend/main.py"] = "from fastapi import FastAPI"

        with patch(
            "squadops.capabilities.handlers.test_runner.run_fullstack_tests",
            return_value=_MOCK_TEST_RESULT_PASSED,
        ) as mock_fullstack:
            handler = QATestHandler()
            await handler.handle(mock_context, qa_inputs)

            call_kwargs = mock_fullstack.call_args.kwargs
            assert call_kwargs["timeout_seconds"] == 180


class TestBuilderNoTokenBudget:
    """Builder handler calls chat() without max_tokens (D2)."""

    async def test_builder_no_max_tokens(self):
        from squadops.capabilities.handlers.cycle_tasks import BuilderAssembleHandler

        ctx = MagicMock()
        ctx.ports.llm.chat = AsyncMock(
            return_value=ChatMessage(
                role="assistant",
                content=(
                    "```python:my_app/__main__.py\n"
                    "from .main import main\n"
                    "if __name__ == '__main__':\n"
                    "    main()\n```\n\n"
                    "```dockerfile:Dockerfile\n"
                    "FROM python:3.11-slim\nWORKDIR /app\n"
                    'COPY . .\nCMD ["python", "-m", "my_app"]\n```\n\n'
                    "```text:requirements.txt\n# none\n```\n\n"
                    "```markdown:qa_handoff.md\n"
                    "## How to Run\npython -m my_app\n\n"
                    "## How to Test\npytest tests/\n\n"
                    "## Expected Behavior\nPrints hello\n```\n"
                ),
            ),
        )
        ctx.ports.llm.default_model = "test-model"
        assembled = MagicMock()
        assembled.content = "You are a builder agent."
        ctx.ports.prompt_service.get_system_prompt = MagicMock(return_value=assembled)
        ctx.ports.llm_observability = None
        ctx.ports.request_renderer = None
        ctx.correlation_context = None

        inputs = {
            "prd": "Build something.",
            "artifact_contents": {
                "my_app/main.py": "def main():\n    print('hello')",
            },
            "resolved_config": {"build_profile": "python_cli_builder"},
        }
        handler = BuilderAssembleHandler()
        result = await handler.handle(ctx, inputs)

        assert result.success is True
        call_kwargs = ctx.ports.llm.chat.call_args.kwargs
        assert "max_tokens" not in call_kwargs
        assert "timeout_seconds" not in call_kwargs
