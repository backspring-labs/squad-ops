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

    async def test_enriched_failure_evidence_appears_in_user_prompt(self, mock_context):
        # Issue #84 follow-up: when the executor passes in validation_result
        # + rejected_artifacts + preliminary_failure_classification, the
        # handler must surface them to the LLM (currently via JSON-dumped
        # failure_evidence under the "## Failure Evidence" heading). Without
        # this the LLM sees only the bare error string and downstream
        # correction-decision picks rewind on patchable content failures.
        captured: dict[str, str] = {}

        async def _capture(messages, **_kwargs):
            captured["user_prompt"] = messages[-1].content
            return ChatMessage(
                role="assistant",
                content=json.dumps(
                    {
                        "classification": FailureClassification.WORK_PRODUCT,
                        "analysis_summary": (
                            "qa_handoff regex check 'how to run backend' failed; "
                            "Bob emitted manifest content but missed required section"
                        ),
                        "contributing_factors": [
                            "build profile required qa_handoff in non-handoff task"
                        ],
                    }
                ),
            )

        mock_context.ports.llm.chat = _capture
        mock_context.ports.llm.chat_stream_with_usage = _capture

        enriched_evidence = {
            "failed_task_id": "t-7",
            "failed_task_type": "builder.assemble",
            "error": "validation failed",
            "outcome_class": "semantic_failure",
            "preliminary_failure_classification": FailureClassification.WORK_PRODUCT,
            "validation_result": {
                "passed": False,
                "summary": "1 typed check failed",
                "missing_components": ["qa_handoff.md::## How to run backend"],
                "checks": [
                    {
                        "name": "regex_match:how to run backend",
                        "status": "failed",
                        "actual": {"match_count": 0},
                    }
                ],
            },
            "rejected_artifacts": [
                {
                    "name": "qa_handoff.md",
                    "type": "document",
                    "size": 4200,
                    "content_snippet": "## Implemented Scope\n\nFastAPI backend...",
                }
            ],
            "prior_plan_deltas_count": 0,
        }

        h = DataAnalyzeFailureHandler()
        result = await h.handle(
            mock_context,
            {"prd": "test PRD", "failure_evidence": enriched_evidence},
        )

        assert result.success is True
        prompt = captured["user_prompt"]
        # Each enriched field must reach the LLM as identifiable text — not
        # buried under a generic "error" string.
        assert "validation_result" in prompt
        assert "regex_match:how to run backend" in prompt
        assert "qa_handoff.md" in prompt
        assert "missing_components" in prompt
        assert "rejected_artifacts" in prompt
        assert "Implemented Scope" in prompt  # snippet content reaches LLM

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

    # ------------------------------------------------------------------
    # SIP-0092 M2 → M3 gate diagnostic field (structural_plan_change_candidate)
    # ------------------------------------------------------------------

    @pytest.mark.parametrize("candidate", ["none", "add_task", "tighten_acceptance", "other"])
    async def test_plan_change_candidate_passes_through(self, mock_context, candidate):
        decision = {
            "correction_path": "patch",
            "decision_rationale": "Localized",
            "affected_task_types": ["development.develop"],
            "structural_plan_change_candidate": candidate,
            "structural_plan_change_rationale": (
                "Coverage gap on join/leave endpoints" if candidate != "none" else ""
            ),
        }
        _set_llm_mock(
            mock_context,
            return_value=ChatMessage(role="assistant", content=json.dumps(decision)),
        )

        h = GovernanceCorrectionDecisionHandler()
        result = await h.handle(mock_context, {"prd": "test"})

        assert result.outputs["structural_plan_change_candidate"] == candidate
        assert (
            result.outputs["structural_plan_change_rationale"]
            == decision["structural_plan_change_rationale"]
        )

    async def test_plan_change_candidate_invalid_falls_back_to_none(self, mock_context):
        """Invalid values shouldn't break the run — degrade to `none` so the
        diagnostic field is always present and parseable for gate aggregation."""
        decision = {
            "correction_path": "patch",
            "decision_rationale": "Localized",
            "affected_task_types": [],
            "structural_plan_change_candidate": "remove_task",  # not in Rev 1 scope
            "structural_plan_change_rationale": "Should be dropped",
        }
        _set_llm_mock(
            mock_context,
            return_value=ChatMessage(role="assistant", content=json.dumps(decision)),
        )

        h = GovernanceCorrectionDecisionHandler()
        result = await h.handle(mock_context, {"prd": "test"})

        assert result.outputs["structural_plan_change_candidate"] == "none"

    async def test_plan_change_candidate_missing_defaults_to_none(self, mock_context):
        """LLM may omit the field; the artifact must still carry the diagnostic
        so gate-evidence aggregation can count `none` cycles separately from
        cycles where the field never appeared."""
        decision = {
            "correction_path": "patch",
            "decision_rationale": "Localized",
            "affected_task_types": [],
        }
        _set_llm_mock(
            mock_context,
            return_value=ChatMessage(role="assistant", content=json.dumps(decision)),
        )

        h = GovernanceCorrectionDecisionHandler()
        result = await h.handle(mock_context, {"prd": "test"})

        assert result.outputs["structural_plan_change_candidate"] == "none"
        assert result.outputs["structural_plan_change_rationale"] == ""

    async def test_plan_change_candidate_persists_in_artifact(self, mock_context):
        """The persisted correction_decision.md JSON must contain both the
        operative decision and the diagnostic so post-run analysis can pull
        them off a single artifact."""
        decision = {
            "correction_path": "patch",
            "decision_rationale": "Localized",
            "affected_task_types": ["development.develop"],
            "structural_plan_change_candidate": "add_task",
            "structural_plan_change_rationale": "Need a separate join/leave test task",
        }
        _set_llm_mock(
            mock_context,
            return_value=ChatMessage(role="assistant", content=json.dumps(decision)),
        )

        h = GovernanceCorrectionDecisionHandler()
        result = await h.handle(mock_context, {"prd": "test"})

        artifact = result.outputs["artifacts"][0]
        body = json.loads(artifact["content"])
        assert body["correction_path"] == "patch"
        assert body["structural_plan_change_candidate"] == "add_task"
        assert "join/leave" in body["structural_plan_change_rationale"]


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

    async def test_dev_repair_extracts_fenced_code_into_per_file_artifacts(self, mock_context):
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

    async def test_dev_repair_falls_back_to_markdown_when_no_fenced_blocks(self, mock_context):
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

    async def test_repair_prompt_carries_failed_task_contract(self, mock_context):
        """Repair handler must surface expected_artifacts + acceptance_criteria.

        Without this plumbing the repair LLM sees only PRD + prior_outputs
        and produces a generic narrative — the cyc_3d5d31717603 failure mode
        where Bob emitted a "Joi communications status tracker" instead of
        the qa_handoff.md the original task was specced to produce.
        """
        captured: dict = {}

        async def _capture(messages, **_kw):
            captured["user"] = messages[-1].content
            return ChatMessage(role="assistant", content="```markdown:qa_handoff.md\nfixed\n```")

        mock_context.ports.llm.chat_stream_with_usage = _capture

        inputs = {
            "prd": "Build a runs app",
            "failed_task_type": "builder.assemble",
            "subtask_focus": "QA handoff packaging",
            "subtask_description": "Assemble the qa_handoff.md with run instructions",
            "expected_artifacts": ["qa_handoff.md", "backend/requirements.txt"],
            "acceptance_criteria": [
                "qa_handoff.md must contain '## How to Test'",
                "qa_handoff.md must contain '## Expected Behavior'",
            ],
            "failure_evidence": {
                "validation_result": {
                    "summary": "Missing required headings in qa_handoff.md",
                    "missing_components": ["## How to Test", "## Expected Behavior"],
                },
                "rejected_artifacts": [{"name": "qa_handoff.md"}],
            },
            "failure_analysis": {
                "analysis_summary": "Builder skipped two mandatory sections.",
            },
            "correction_decision": {
                "correction_path": "patch",
                "decision_rationale": "Append missing headings; do not rewind.",
            },
        }

        h = BuilderAssembleRepairHandler()
        result = await h.handle(mock_context, inputs)

        assert result.success is True
        prompt = captured["user"]
        assert "qa_handoff.md" in prompt
        assert "## How to Test" in prompt
        assert "## Expected Behavior" in prompt
        assert "Missing required headings" in prompt
        assert "Append missing headings" in prompt
        assert "builder.assemble" in prompt
        assert "QA handoff packaging" in prompt

    async def test_repair_prompt_works_without_failure_context(self, mock_context):
        """Backwards compat: handler still works with bare {"prd": ...} inputs."""
        captured: dict = {}

        async def _capture(messages, **_kw):
            captured["user"] = messages[-1].content
            return ChatMessage(role="assistant", content="ok")

        mock_context.ports.llm.chat_stream_with_usage = _capture

        h = DevelopmentCorrectionRepairHandler()
        result = await h.handle(mock_context, {"prd": "test"})

        assert result.success is True
        prompt = captured["user"]
        assert "test" in prompt
        assert "Repair Task" in prompt

    async def test_validate_repair_prompt_carries_criteria_and_repair_output(self, mock_context):
        """Validate-repair must check the repair against the original criteria.

        Otherwise Eve emits a generic QA-strategy doc (the cyc_3d5d31717603
        failure mode) instead of a PASS/FAIL judgement on the named artifact.
        """
        captured: dict = {}

        async def _capture(messages, **_kw):
            captured["user"] = messages[-1].content
            return ChatMessage(role="assistant", content="# Repair Validation\nVerdict: PASS")

        mock_context.ports.llm.chat_stream_with_usage = _capture

        inputs = {
            "prd": "Build a runs app",
            "failed_task_type": "builder.assemble",
            "expected_artifacts": ["qa_handoff.md"],
            "acceptance_criteria": [
                "qa_handoff.md must contain '## How to Test'",
            ],
            "failure_evidence": {
                "validation_result": {"summary": "Missing '## How to Test'"},
            },
            "prior_outputs": {
                "builder": {"summary": "Repaired qa_handoff.md with new sections"},
            },
        }

        h = QAValidateRepairHandler()
        result = await h.handle(mock_context, inputs)

        assert result.success is True
        prompt = captured["user"]
        assert "qa_handoff.md" in prompt
        assert "## How to Test" in prompt
        assert "Repaired qa_handoff.md with new sections" in prompt
        assert "Validate Repair" in prompt
        assert "PASS" in prompt or "FAIL" in prompt

    async def test_validate_repair_prompt_includes_repaired_artifact_content(self, mock_context):
        """Eve must see the actual repaired files, not just a one-line summary.

        Cycle 8 regression: both repair_validation.md outputs returned
        Verdict: FAIL because `_format_repair_summary` only rendered the
        role-keyed summary string, so Eve had no way to verify the
        artifact against the acceptance criteria. Surfacing the artifact
        name + content lets her cite specific lines.
        """
        captured: dict = {}

        async def _capture(messages, **_kw):
            captured["user"] = messages[-1].content
            return ChatMessage(role="assistant", content="# Repair Validation\nVerdict: PASS")

        mock_context.ports.llm.chat_stream_with_usage = _capture

        repaired_handoff = (
            "# QA Handoff\n\n"
            "## How to Test\n\nRun `pytest backend/tests`.\n\n"
            "## Expected Behavior\n\nAll tests pass.\n"
        )
        inputs = {
            "prd": "Build a runs app",
            "failed_task_type": "builder.assemble",
            "expected_artifacts": ["qa_handoff.md"],
            "acceptance_criteria": [
                "qa_handoff.md must contain '## How to Test'",
                "qa_handoff.md must contain '## Expected Behavior'",
            ],
            "prior_outputs": {
                "builder": {
                    "summary": "[builder] Build a runs app",
                    "artifacts": [
                        {
                            "name": "qa_handoff.md",
                            "content": repaired_handoff,
                            "media_type": "text/markdown",
                            "type": "document",
                        },
                    ],
                },
            },
        }

        h = QAValidateRepairHandler()
        result = await h.handle(mock_context, inputs)

        assert result.success is True
        prompt = captured["user"]
        assert "qa_handoff.md" in prompt
        assert "## How to Test" in prompt
        assert "## Expected Behavior" in prompt
        assert "Run `pytest backend/tests`." in prompt
        assert "```markdown" in prompt

    async def test_validate_repair_prompt_falls_back_to_summary_without_artifacts(
        self, mock_context
    ):
        """Backwards compat: pre-fix executor checkpoints have no artifacts key."""
        captured: dict = {}

        async def _capture(messages, **_kw):
            captured["user"] = messages[-1].content
            return ChatMessage(role="assistant", content="Verdict: PASS")

        mock_context.ports.llm.chat_stream_with_usage = _capture

        inputs = {
            "prd": "test",
            "failed_task_type": "builder.assemble",
            "prior_outputs": {
                "builder": {"summary": "Repaired qa_handoff.md"},
            },
        }

        h = QAValidateRepairHandler()
        result = await h.handle(mock_context, inputs)

        assert result.success is True
        assert "Repaired qa_handoff.md" in captured["user"]


# ---------------------------------------------------------------------------
# _format_repair_summary unit tests
# ---------------------------------------------------------------------------


class TestFormatRepairSummary:
    @pytest.mark.parametrize(
        "filename,expected_fence",
        [
            ("RunDetail.jsx", "```jsx"),
            ("backend/main.py", "```python"),
            ("qa_handoff.md", "```markdown"),
            ("config.yaml", "```yaml"),
            ("noext", "```"),
        ],
    )
    def test_renders_artifacts_with_language_fenced_blocks(self, filename, expected_fence):
        prior_outputs = {
            "dev": {
                "summary": "[dev] sample",
                "artifacts": [
                    {"name": filename, "content": "BODY", "type": "source"},
                ],
            },
        }
        rendered = QAValidateRepairHandler._format_repair_summary(prior_outputs)
        assert f"#### `{filename}`" in rendered
        assert expected_fence in rendered
        assert "BODY" in rendered
        assert "[dev] sample" in rendered

    def test_renders_multiple_artifacts_across_roles(self):
        prior_outputs = {
            "builder": {
                "summary": "[builder] s",
                "artifacts": [
                    {"name": "qa_handoff.md", "content": "## How to Test\nrun it"},
                    {"name": "backend/requirements.txt", "content": "fastapi==0.115.0"},
                ],
            },
        }
        rendered = QAValidateRepairHandler._format_repair_summary(prior_outputs)
        assert "qa_handoff.md" in rendered
        assert "backend/requirements.txt" in rendered
        assert "## How to Test" in rendered
        assert "fastapi==0.115.0" in rendered

    def test_returns_placeholder_when_no_prior_outputs(self):
        assert (
            QAValidateRepairHandler._format_repair_summary(None) == "(no repair output available)"
        )
        assert QAValidateRepairHandler._format_repair_summary({}) == "(no repair output available)"

    def test_returns_placeholder_when_no_repair_role_keys(self):
        # `qa` and `lead` are not repair roles — only dev/builder produce repairs.
        result = QAValidateRepairHandler._format_repair_summary(
            {"qa": {"summary": "noise"}, "lead": {"summary": "noise"}}
        )
        assert result == "(no repair output from dev or builder role)"

    def test_skips_artifacts_with_no_content(self):
        prior_outputs = {
            "dev": {
                "summary": "[dev] s",
                "artifacts": [
                    {"name": "ghost.py"},  # no content
                    {"name": "real.py", "content": "x = 1"},
                ],
            },
        }
        rendered = QAValidateRepairHandler._format_repair_summary(prior_outputs)
        assert "real.py" in rendered
        assert "x = 1" in rendered
        assert "ghost.py" not in rendered

    def test_falls_back_to_summary_when_artifacts_empty(self):
        prior_outputs = {"dev": {"summary": "narrative-only repair", "artifacts": []}}
        rendered = QAValidateRepairHandler._format_repair_summary(prior_outputs)
        assert "narrative-only repair" in rendered
        assert "```" not in rendered

    def test_handles_non_dict_block(self):
        # Defensive: if the executor ever stores a string instead of a dict we
        # surface it rather than crashing.
        rendered = QAValidateRepairHandler._format_repair_summary({"dev": "raw string"})
        assert "raw string" in rendered
