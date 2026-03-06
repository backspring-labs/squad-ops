"""Tests for SIP-0079 implementation handlers.

Covers GovernanceEstablishContractHandler, DataAnalyzeFailureHandler,
GovernanceCorrectionDecisionHandler, DevelopmentRepairHandler,
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
    DevelopmentRepairHandler,
    QAValidateRepairHandler,
)
from squadops.cycles.task_outcome import FailureClassification, TaskOutcome
from squadops.llm.exceptions import LLMConnectionError
from squadops.llm.models import ChatMessage

pytestmark = [pytest.mark.domain_capabilities]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def mock_context():
    ctx = MagicMock()
    ctx.ports.llm.chat = AsyncMock(
        return_value=ChatMessage(role="assistant", content="stub"),
    )
    assembled = MagicMock()
    assembled.content = "System prompt"
    ctx.ports.prompt_service.get_system_prompt = MagicMock(return_value=assembled)
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
        mock_context.ports.llm.chat = AsyncMock(
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
        mock_context.ports.llm.chat = AsyncMock(
            return_value=ChatMessage(role="assistant", content="not valid json"),
        )

        h = GovernanceEstablishContractHandler()
        result = await h.handle(mock_context, {"prd": "test"})

        assert result.success is False
        assert result.outputs["outcome_class"] == TaskOutcome.NEEDS_REPLAN

    async def test_llm_error_returns_needs_replan(self, mock_context):
        mock_context.ports.llm.chat = AsyncMock(
            side_effect=LLMConnectionError("timeout"),
        )

        h = GovernanceEstablishContractHandler()
        result = await h.handle(mock_context, {"prd": "test"})

        assert result.success is False
        assert result.outputs["outcome_class"] == TaskOutcome.NEEDS_REPLAN

    async def test_strips_markdown_fences(self, mock_context):
        contract = {"objective": "Test", "acceptance_criteria": []}
        fenced = f"```json\n{json.dumps(contract)}\n```"
        mock_context.ports.llm.chat = AsyncMock(
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
        mock_context.ports.llm.chat = AsyncMock(
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

    async def test_unparseable_falls_back_to_execution(self, mock_context):
        mock_context.ports.llm.chat = AsyncMock(
            return_value=ChatMessage(
                role="assistant", content="unstructured analysis text"
            ),
        )

        h = DataAnalyzeFailureHandler()
        result = await h.handle(mock_context, {"prd": "test"})

        assert result.success is True
        assert result.outputs["classification"] == FailureClassification.EXECUTION


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
        mock_context.ports.llm.chat = AsyncMock(
            return_value=ChatMessage(
                role="assistant", content=json.dumps(decision)
            ),
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
        mock_context.ports.llm.chat = AsyncMock(
            return_value=ChatMessage(
                role="assistant", content=json.dumps(decision)
            ),
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
        mock_context.ports.llm.chat = AsyncMock(
            return_value=ChatMessage(
                role="assistant", content=json.dumps(decision)
            ),
        )

        h = GovernanceCorrectionDecisionHandler()
        result = await h.handle(mock_context, {"prd": "test"})

        assert result.outputs["correction_path"] == "abort"

    async def test_unparseable_falls_back_to_abort(self, mock_context):
        mock_context.ports.llm.chat = AsyncMock(
            return_value=ChatMessage(
                role="assistant", content="I think we should..."
            ),
        )

        h = GovernanceCorrectionDecisionHandler()
        result = await h.handle(mock_context, {"prd": "test"})

        assert result.outputs["correction_path"] == "abort"


# ---------------------------------------------------------------------------
# Repair handlers (thin subclasses)
# ---------------------------------------------------------------------------


class TestRepairHandlers:
    async def test_repair_produces_output(self, mock_context):
        mock_context.ports.llm.chat = AsyncMock(
            return_value=ChatMessage(role="assistant", content="Repair applied"),
        )

        h = DevelopmentRepairHandler()
        result = await h.handle(mock_context, {"prd": "test"})

        assert result.success is True
        assert result.outputs["role"] == "dev"

    async def test_validate_repair_produces_output(self, mock_context):
        mock_context.ports.llm.chat = AsyncMock(
            return_value=ChatMessage(role="assistant", content="Repair validated"),
        )

        h = QAValidateRepairHandler()
        result = await h.handle(mock_context, {"prd": "test"})

        assert result.success is True
        assert result.outputs["role"] == "qa"
