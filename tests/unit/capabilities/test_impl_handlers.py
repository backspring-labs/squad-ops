"""Tests for SIP-0079 implementation handlers.

Covers GovernanceEstablishContractHandler, DataAnalyzeFailureHandler,
GovernanceCorrectionDecisionHandler, DevelopmentCorrectionRepairHandler,
QAValidateRepairHandler.
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from squadops.capabilities.handlers.impl.analyze_failure import (
    DataAnalyzeFailureHandler,
)
from squadops.capabilities.handlers.impl.correction_decision import (
    GovernanceCorrectionDecisionHandler,
)
from squadops.capabilities.handlers.impl.establish_contract import (
    GovernanceEstablishContractHandler,
)
from squadops.capabilities.handlers.impl.repair_handlers import (
    BuilderAssembleRepairHandler,
    DevelopmentCorrectionRepairHandler,
    QAValidateRepairHandler,
)
from squadops.cycles.task_outcome import FailureClassification, TaskOutcome
from squadops.llm.exceptions import LLMConnectionError
from squadops.llm.models import ChatMessage

pytestmark = [pytest.mark.domain_capabilities]


def _set_llm_mock(ctx, **kwargs):
    """Set both chat and chat_stream_with_usage to the same AsyncMock."""
    mock = AsyncMock(**kwargs)
    ctx.ports.llm.chat = mock
    ctx.ports.llm.chat_stream_with_usage = mock


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def mock_context():
    ctx = MagicMock()
    chat_mock = AsyncMock(
        return_value=ChatMessage(role="assistant", content="stub"),
    )
    ctx.ports.llm.chat = chat_mock
    ctx.ports.llm.chat_stream_with_usage = chat_mock
    assembled = MagicMock()
    assembled.content = "System prompt"
    ctx.ports.prompt_service.get_system_prompt = MagicMock(return_value=assembled)
    ctx.ports.request_renderer = None
    ctx.correlation_context = None
    return ctx


# ---------------------------------------------------------------------------
# GovernanceEstablishContractHandler
# ---------------------------------------------------------------------------


class TestEstablishContract:
    async def test_contract_generated(self, mock_context):
        contract = {
            "objective": "Build CLI tool",
            "acceptance_criteria": ["Passes tests"],
            "non_goals": ["UI"],
            "time_budget_seconds": 3600,
            "stop_conditions": ["3 consecutive failures"],
            "required_artifacts": ["main.py"],
        }
        _set_llm_mock(
            mock_context,
            return_value=ChatMessage(role="assistant", content=json.dumps(contract)),
        )

        h = GovernanceEstablishContractHandler()
        result = await h.handle(mock_context, {"prd": "Build a CLI tool"})

        assert result.success is True
        assert result.outputs["contract"]["objective"] == "Build CLI tool"
        assert result.outputs["contract"]["acceptance_criteria"] == ["Passes tests"]
        assert result.outputs["contract"]["time_budget_seconds"] == 3600
        assert result.outputs["artifacts"][0]["type"] == "run_contract"
        assert result.outputs["artifacts"][0]["name"] == "run_contract.json"

    async def test_parse_failure_returns_needs_replan(self, mock_context):
        _set_llm_mock(
            mock_context,
            return_value=ChatMessage(role="assistant", content="not valid json"),
        )

        h = GovernanceEstablishContractHandler()
        result = await h.handle(mock_context, {"prd": "test"})

        assert result.success is False
        assert result.outputs["outcome_class"] == TaskOutcome.NEEDS_REPLAN

    async def test_llm_error_returns_needs_replan(self, mock_context):
        _set_llm_mock(
            mock_context,
            side_effect=LLMConnectionError("timeout"),
        )

        h = GovernanceEstablishContractHandler()
        result = await h.handle(mock_context, {"prd": "test"})

        assert result.success is False
        assert result.outputs["outcome_class"] == TaskOutcome.NEEDS_REPLAN

    async def test_strips_markdown_fences(self, mock_context):
        contract = {"objective": "Test", "acceptance_criteria": []}
        fenced = f"```json\n{json.dumps(contract)}\n```"
        _set_llm_mock(
            mock_context,
            return_value=ChatMessage(role="assistant", content=fenced),
        )

        h = GovernanceEstablishContractHandler()
        result = await h.handle(mock_context, {"prd": "test"})

        assert result.success is True
        assert result.outputs["contract"]["objective"] == "Test"


# ---------------------------------------------------------------------------
# DataAnalyzeFailureHandler
# ---------------------------------------------------------------------------


class TestAnalyzeFailure:
    async def test_classification_produced(self, mock_context):
        analysis = {
            "classification": FailureClassification.WORK_PRODUCT,
            "analysis_summary": "Output quality below bar",
            "contributing_factors": ["insufficient context"],
        }
        _set_llm_mock(
            mock_context,
            return_value=ChatMessage(role="assistant", content=json.dumps(analysis)),
        )

        h = DataAnalyzeFailureHandler()
        result = await h.handle(
            mock_context,
            {"prd": "test", "failure_evidence": {"error": "bad output"}},
        )

        assert result.success is True
        assert result.outputs["classification"] == FailureClassification.WORK_PRODUCT
        assert "quality" in result.outputs["analysis_summary"]

    async def test_unparseable_routes_to_needs_replan(self, mock_context):
        """Issue #84: unparseable LLM output rejects to NEEDS_REPLAN
        instead of silently coercing to a useless EXECUTION default."""
        _set_llm_mock(
            mock_context,
            return_value=ChatMessage(role="assistant", content="unstructured analysis text"),
        )

        h = DataAnalyzeFailureHandler()
        result = await h.handle(mock_context, {"prd": "test"})

        assert result.success is False
        assert result.outputs["outcome_class"] == TaskOutcome.NEEDS_REPLAN
        assert (
            "rejected" in (result.error or "").lower() or "schema" in (result.error or "").lower()
        )

    async def test_empty_analysis_summary_rejected(self, mock_context):
        """Issue #84: ``analysis_summary: ""`` is the failure mode that
        produced ``analysis_summary: "N/A"`` corrections in the wild."""
        analysis = {
            "classification": FailureClassification.EXECUTION,
            "analysis_summary": "",  # blocked by min_length=20
            "contributing_factors": ["something specific enough"],
        }
        _set_llm_mock(
            mock_context,
            return_value=ChatMessage(role="assistant", content=json.dumps(analysis)),
        )
        h = DataAnalyzeFailureHandler()
        result = await h.handle(mock_context, {"prd": "test"})
        assert result.success is False
        assert result.outputs["outcome_class"] == TaskOutcome.NEEDS_REPLAN

    async def test_unknown_classification_rejected(self, mock_context):
        analysis = {
            "classification": "weird-made-up-bucket",
            "analysis_summary": "Plenty long enough to pass the length gate.",
            "contributing_factors": ["something specific enough"],
        }
        _set_llm_mock(
            mock_context,
            return_value=ChatMessage(role="assistant", content=json.dumps(analysis)),
        )
        h = DataAnalyzeFailureHandler()
        result = await h.handle(mock_context, {"prd": "test"})
        assert result.success is False

    async def test_empty_contributing_factors_rejected(self, mock_context):
        analysis = {
            "classification": FailureClassification.EXECUTION,
            "analysis_summary": "Plenty long enough to pass the length gate.",
            "contributing_factors": [],  # blocked by min_length=1
        }
        _set_llm_mock(
            mock_context,
            return_value=ChatMessage(role="assistant", content=json.dumps(analysis)),
        )
        h = DataAnalyzeFailureHandler()
        result = await h.handle(mock_context, {"prd": "test"})
        assert result.success is False

    async def test_short_contributing_factor_rejected(self, mock_context):
        analysis = {
            "classification": FailureClassification.EXECUTION,
            "analysis_summary": "Plenty long enough to pass the length gate.",
            "contributing_factors": ["x"],  # blocked by per-item >=5 chars
        }
        _set_llm_mock(
            mock_context,
            return_value=ChatMessage(role="assistant", content=json.dumps(analysis)),
        )
        h = DataAnalyzeFailureHandler()
        result = await h.handle(mock_context, {"prd": "test"})
        assert result.success is False


# ---------------------------------------------------------------------------
# GovernanceCorrectionDecisionHandler
# ---------------------------------------------------------------------------


class TestCorrectionDecision:
    @pytest.mark.parametrize("path", ["continue", "patch", "rewind", "abort"])
    async def test_all_paths_selectable(self, mock_context, path):
        decision = {
            "correction_path": path,
            "decision_rationale": f"Choosing {path} because...",
            "affected_task_types": ["development.develop"],
        }
        _set_llm_mock(
            mock_context,
            return_value=ChatMessage(role="assistant", content=json.dumps(decision)),
        )

        h = GovernanceCorrectionDecisionHandler()
        result = await h.handle(
            mock_context,
            {"prd": "test", "failure_analysis": {"classification": "execution"}},
        )

        assert result.success is True
        assert result.outputs["correction_path"] == path

    async def test_rationale_captured(self, mock_context):
        decision = {
            "correction_path": "patch",
            "decision_rationale": "The fix is localized",
            "affected_task_types": ["development.develop"],
        }
        _set_llm_mock(
            mock_context,
            return_value=ChatMessage(role="assistant", content=json.dumps(decision)),
        )

        h = GovernanceCorrectionDecisionHandler()
        result = await h.handle(mock_context, {"prd": "test"})

        assert result.outputs["decision_rationale"] == "The fix is localized"
        assert result.outputs["affected_task_types"] == ["development.develop"]

    async def test_invalid_path_falls_back_to_abort(self, mock_context):
        decision = {
            "correction_path": "invalid_path",
            "decision_rationale": "test",
            "affected_task_types": [],
        }
        _set_llm_mock(
            mock_context,
            return_value=ChatMessage(role="assistant", content=json.dumps(decision)),
        )

        h = GovernanceCorrectionDecisionHandler()
        result = await h.handle(mock_context, {"prd": "test"})

        assert result.outputs["correction_path"] == "abort"

    async def test_unparseable_falls_back_to_abort(self, mock_context):
        _set_llm_mock(
            mock_context,
            return_value=ChatMessage(role="assistant", content="I think we should..."),
        )

        h = GovernanceCorrectionDecisionHandler()
        result = await h.handle(mock_context, {"prd": "test"})

        assert result.outputs["correction_path"] == "abort"


# ---------------------------------------------------------------------------
# Repair handlers (thin subclasses)
# ---------------------------------------------------------------------------


class TestRepairHandlers:
    async def test_repair_produces_output(self, mock_context):
        _set_llm_mock(
            mock_context,
            return_value=ChatMessage(role="assistant", content="Repair applied"),
        )

        h = DevelopmentCorrectionRepairHandler()
        result = await h.handle(mock_context, {"prd": "test"})

        assert result.success is True
        assert result.outputs["role"] == "dev"
        assert h.capability_id == "development.correction_repair"

    async def test_validate_repair_produces_output(self, mock_context):
        _set_llm_mock(
            mock_context,
            return_value=ChatMessage(role="assistant", content="Repair validated"),
        )

        h = QAValidateRepairHandler()
        result = await h.handle(mock_context, {"prd": "test"})

        assert result.success is True
        assert result.outputs["role"] == "qa"

    async def test_dev_repair_extracts_fenced_code_into_per_file_artifacts(
        self, mock_context
    ):
        # Regression: previously this whole response was wrapped as a single
        # repair_output.md document and the source files never landed.
        response = (
            "Here is the patched code.\n\n"
            "```python:backend/main.py\n"
            "from fastapi import FastAPI\n"
            "app = FastAPI()\n"
            "```\n\n"
            "And the helper:\n\n"
            "```python:backend/util.py\n"
            "def helper(): return 1\n"
            "```\n"
        )
        _set_llm_mock(
            mock_context,
            return_value=ChatMessage(role="assistant", content=response),
        )

        h = DevelopmentCorrectionRepairHandler()
        result = await h.handle(mock_context, {"prd": "test"})

        artifacts = result.outputs["artifacts"]
        names = [a["name"] for a in artifacts]
        assert names == ["backend/main.py", "backend/util.py"]
        assert all(a["type"] == "source" for a in artifacts)
        assert artifacts[0]["content"].startswith("from fastapi")
        assert artifacts[1]["content"].strip() == "def helper(): return 1"
        # No leftover repair_output.md when extraction succeeds
        assert "repair_output.md" not in names

    async def test_dev_repair_falls_back_to_markdown_when_no_fenced_blocks(
        self, mock_context
    ):
        # Without fenced files we still preserve the LLM output instead of
        # silently dropping it — the fallback is what keeps narrative-only
        # repairs (e.g. "no code change needed, root cause was X") visible.
        _set_llm_mock(
            mock_context,
            return_value=ChatMessage(
                role="assistant",
                content="No code change needed; the failure was a flaky test.",
            ),
        )

        h = DevelopmentCorrectionRepairHandler()
        result = await h.handle(mock_context, {"prd": "test"})

        artifacts = result.outputs["artifacts"]
        assert len(artifacts) == 1
        assert artifacts[0]["name"] == "repair_output.md"
        assert artifacts[0]["type"] == "document"
        assert "flaky test" in artifacts[0]["content"]

    async def test_builder_assemble_repair_extracts_fenced_files(self, mock_context):
        response = (
            "```markdown:qa_handoff.md\n"
            "## How to run backend\n\n`uvicorn main:app`\n"
            "```\n\n"
            "```text:backend/requirements.txt\n"
            "fastapi==0.115.0\n"
            "```\n"
        )
        _set_llm_mock(
            mock_context,
            return_value=ChatMessage(role="assistant", content=response),
        )

        h = BuilderAssembleRepairHandler()
        result = await h.handle(mock_context, {"prd": "test"})

        assert result.success is True
        assert result.outputs["role"] == "builder"
        assert h.capability_id == "builder.assemble_repair"
        names = [a["name"] for a in result.outputs["artifacts"]]
        assert names == ["qa_handoff.md", "backend/requirements.txt"]
