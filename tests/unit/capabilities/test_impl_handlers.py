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
    def test_capability_id(self):
        h = GovernanceEstablishContractHandler()
        assert h.capability_id == "governance.establish_contract"
        assert h._role == "lead"

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

    async def test_contract_fields_extracted(self, mock_context):
        contract = {
            "objective": "Goal",
            "acceptance_criteria": ["A", "B"],
            "non_goals": ["X"],
            "time_budget_seconds": 7200,
            "stop_conditions": ["fail 3x"],
            "required_artifacts": ["out.py"],
        }
        mock_context.ports.llm.chat = AsyncMock(
            return_value=ChatMessage(role="assistant", content=json.dumps(contract)),
        )

        h = GovernanceEstablishContractHandler()
        result = await h.handle(mock_context, {"prd": "test"})

        c = result.outputs["contract"]
        assert c["acceptance_criteria"] == ["A", "B"]
        assert c["time_budget_seconds"] == 7200

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
    def test_capability_id(self):
        h = DataAnalyzeFailureHandler()
        assert h.capability_id == "data.analyze_failure"
        assert h._role == "data"

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
            mock_context, {"prd": "test", "failure_evidence": {"error": "bad output"}}
        )

        assert result.success is True
        assert result.outputs["classification"] == FailureClassification.WORK_PRODUCT
        assert "quality" in result.outputs["analysis_summary"]

    async def test_all_classifications_mapped(self):
        """All FailureClassification values are valid strings."""
        all_values = [
            FailureClassification.EXECUTION,
            FailureClassification.WORK_PRODUCT,
            FailureClassification.ALIGNMENT,
            FailureClassification.DECISION,
            FailureClassification.MODEL_LIMITATION,
        ]
        assert len(all_values) == 5
        assert all(isinstance(v, str) for v in all_values)

    async def test_unparseable_falls_back_to_execution(self, mock_context):
        mock_context.ports.llm.chat = AsyncMock(
            return_value=ChatMessage(role="assistant", content="unstructured analysis text"),
        )

        h = DataAnalyzeFailureHandler()
        result = await h.handle(mock_context, {"prd": "test"})

        assert result.success is True
        assert result.outputs["classification"] == FailureClassification.EXECUTION

    async def test_evidence_included(self, mock_context):
        analysis = {
            "classification": FailureClassification.EXECUTION,
            "analysis_summary": "Timeout",
            "contributing_factors": [],
        }
        mock_context.ports.llm.chat = AsyncMock(
            return_value=ChatMessage(role="assistant", content=json.dumps(analysis)),
        )

        h = DataAnalyzeFailureHandler()
        result = await h.handle(mock_context, {"prd": "test"})

        assert result._evidence is not None
        assert result._evidence.handler_name == "data_analyze_failure_handler"


# ---------------------------------------------------------------------------
# GovernanceCorrectionDecisionHandler
# ---------------------------------------------------------------------------


class TestCorrectionDecision:
    def test_capability_id(self):
        h = GovernanceCorrectionDecisionHandler()
        assert h.capability_id == "governance.correction_decision"
        assert h._role == "lead"

    @pytest.mark.parametrize("path", ["continue", "patch", "rewind", "abort"])
    async def test_all_paths_selectable(self, mock_context, path):
        decision = {
            "correction_path": path,
            "decision_rationale": f"Choosing {path} because...",
            "affected_task_types": ["development.develop"],
        }
        mock_context.ports.llm.chat = AsyncMock(
            return_value=ChatMessage(role="assistant", content=json.dumps(decision)),
        )

        h = GovernanceCorrectionDecisionHandler()
        result = await h.handle(
            mock_context, {"prd": "test", "failure_analysis": {"classification": "execution"}}
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
        mock_context.ports.llm.chat = AsyncMock(
            return_value=ChatMessage(role="assistant", content=json.dumps(decision)),
        )

        h = GovernanceCorrectionDecisionHandler()
        result = await h.handle(mock_context, {"prd": "test"})

        assert result.outputs["correction_path"] == "abort"

    async def test_unparseable_falls_back_to_abort(self, mock_context):
        mock_context.ports.llm.chat = AsyncMock(
            return_value=ChatMessage(role="assistant", content="I think we should..."),
        )

        h = GovernanceCorrectionDecisionHandler()
        result = await h.handle(mock_context, {"prd": "test"})

        assert result.outputs["correction_path"] == "abort"


# ---------------------------------------------------------------------------
# Repair handlers (thin subclasses)
# ---------------------------------------------------------------------------


class TestRepairHandlers:
    def test_development_repair_capability_id(self):
        h = DevelopmentRepairHandler()
        assert h.capability_id == "development.repair"
        assert h._role == "dev"

    def test_qa_validate_repair_capability_id(self):
        h = QAValidateRepairHandler()
        assert h.capability_id == "qa.validate_repair"
        assert h._role == "qa"

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

    async def test_repair_artifact_name(self):
        h = DevelopmentRepairHandler()
        assert h._artifact_name == "repair_output.md"

    async def test_validate_repair_artifact_name(self):
        h = QAValidateRepairHandler()
        assert h._artifact_name == "repair_validation.md"
