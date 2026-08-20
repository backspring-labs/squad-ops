"""Tests for SIP-0079 implementation handlers.

Covers GovernanceDefineDoneHandler, DataAnalyzeFailureHandler,
GovernanceCorrectionDecisionHandler, DevelopmentCorrectionRepairHandler,
BuilderAssembleRepairHandler.
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
from squadops.capabilities.handlers.impl.define_done import (
    GovernanceDefineDoneHandler,
)
from squadops.capabilities.handlers.impl.repair_handlers import (
    BuilderAssembleRepairHandler,
    DevelopmentCorrectionRepairHandler,
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
    assembled.assembly_hash = "sha256:test"
    ctx.ports.prompt_service.get_system_prompt = MagicMock(return_value=assembled)
    # Externalized impl-handler system prompts (correction_decision /
    # analyze_failure / define_done) call assemble_task_only(role,
    # task_type) — the task_type fragment with NO role-identity prepend.
    # Mock both forms so the auto-attribute MagicMock doesn't return a
    # non-string.
    ctx.ports.prompt_service.assemble = MagicMock(return_value=assembled)
    ctx.ports.prompt_service.assemble_task_only = MagicMock(return_value=assembled)
    ctx.ports.request_renderer = None
    ctx.correlation_context = None
    return ctx


# ---------------------------------------------------------------------------
# GovernanceDefineDoneHandler
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

        h = GovernanceDefineDoneHandler()
        result = await h.handle(mock_context, {"prd": "Build a CLI tool"})

        assert result.success is True
        assert result.outputs["contract"]["objective"] == "Build CLI tool"
        assert result.outputs["contract"]["acceptance_criteria"] == ["Passes tests"]
        assert result.outputs["contract"]["time_budget_seconds"] == 3600
        assert result.outputs["artifacts"][0]["type"] == "definition_of_done"
        assert result.outputs["artifacts"][0]["name"] == "definition_of_done.json"

    async def test_parse_failure_returns_needs_replan(self, mock_context):
        _set_llm_mock(
            mock_context,
            return_value=ChatMessage(role="assistant", content="not valid json"),
        )

        h = GovernanceDefineDoneHandler()
        result = await h.handle(mock_context, {"prd": "test"})

        assert result.success is False
        assert result.outputs["outcome_class"] == TaskOutcome.NEEDS_REPLAN

    async def test_llm_error_returns_needs_replan(self, mock_context):
        _set_llm_mock(
            mock_context,
            side_effect=LLMConnectionError("timeout"),
        )

        h = GovernanceDefineDoneHandler()
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

        h = GovernanceDefineDoneHandler()
        result = await h.handle(mock_context, {"prd": "test"})

        assert result.success is True
        assert result.outputs["contract"]["objective"] == "Test"

    async def test_handles_think_block_then_json(self, mock_context):
        """Regression: cyc_a4e6dc3afe7a (2026-05-05) failed at this
        handler with `Expecting value: line 1 column 1 (char 0)` on
        what was likely a Qwen3 <think> block followed by valid JSON.
        The strict-from-start parser couldn't see past the thinking
        block. Tolerant extraction must recover."""
        contract = {
            "objective": "Build runs app",
            "acceptance_criteria": ["passes pytest"],
            "non_goals": [],
            "time_budget_seconds": 1800,
            "stop_conditions": [],
            "required_artifacts": ["main.py"],
        }
        thinking_response = (
            "<think>\n"
            "The user wants a contract for a runs app. Let me consider...\n"
            "Acceptance should cover the join/leave endpoints.\n"
            "</think>\n\n"
            f"{json.dumps(contract)}"
        )
        _set_llm_mock(
            mock_context,
            return_value=ChatMessage(role="assistant", content=thinking_response),
        )

        h = GovernanceDefineDoneHandler()
        result = await h.handle(mock_context, {"prd": "test"})

        assert result.success is True
        assert result.outputs["contract"]["objective"] == "Build runs app"

    async def test_handles_prose_preamble_before_fenced_json(self, mock_context):
        """Same shape as the cyc_a4e6dc failure but with prose preamble
        instead of a thinking block — plausible under the new
        role-identity-prepended assembly path from PR #126."""
        contract = {"objective": "Ship it", "acceptance_criteria": ["green CI"]}
        response = (
            "Here is the run contract you requested:\n\n"
            "```json\n"
            f"{json.dumps(contract)}\n"
            "```\n"
            "Let me know if any field needs adjustment."
        )
        _set_llm_mock(
            mock_context,
            return_value=ChatMessage(role="assistant", content=response),
        )

        h = GovernanceDefineDoneHandler()
        result = await h.handle(mock_context, {"prd": "test"})

        assert result.success is True
        assert result.outputs["contract"]["objective"] == "Ship it"


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

    async def test_truncated_json_recovers_via_one_reask(self, mock_context):
        """#1008 (V38 shakedown): the model stopped mid-object once and the whole
        correction chain ran decisionless. A truncated first response followed by
        a complete retry must succeed — and with exactly two calls, because the
        re-ask is bounded."""
        truncated = '{"classification": "work_product", "analysis_summary": "The check'
        complete = json.dumps(
            {
                "classification": FailureClassification.WORK_PRODUCT,
                "analysis_summary": "Named import of a default export",
                "contributing_factors": ["TS2614"],
            }
        )
        mock = AsyncMock(
            side_effect=[
                ChatMessage(role="assistant", content=truncated),
                ChatMessage(role="assistant", content=complete),
            ]
        )
        mock_context.ports.llm.chat = mock
        mock_context.ports.llm.chat_stream_with_usage = mock

        h = DataAnalyzeFailureHandler()
        result = await h.handle(mock_context, {"prd": "test", "failure_evidence": {"e": "x"}})

        assert result.success is True
        assert result.outputs["analysis_summary"] == "Named import of a default export"
        assert mock.await_count == 2

    async def test_double_extraction_failure_is_bounded_and_rejects(self, mock_context):
        """The re-ask is ONE re-ask: two truncated responses reject to
        NEEDS_REPLAN with exactly two LLM calls — a retry loop here would hide a
        systematic model failure behind unbounded spend."""
        truncated = '{"classification": "work_product", "analysis_summary": "The'
        mock = AsyncMock(
            side_effect=[
                ChatMessage(role="assistant", content=truncated),
                ChatMessage(role="assistant", content=truncated),
            ]
        )
        mock_context.ports.llm.chat = mock
        mock_context.ports.llm.chat_stream_with_usage = mock

        h = DataAnalyzeFailureHandler()
        result = await h.handle(mock_context, {"prd": "test"})

        assert result.success is False
        assert result.outputs["outcome_class"] == TaskOutcome.NEEDS_REPLAN
        assert mock.await_count == 2

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
# Externalized system prompts — pattern alignment with planning_tasks.py
# ---------------------------------------------------------------------------


class TestImplHandlerSystemPromptExternalization:
    """The three SIP-0079 impl handlers (analyze_failure,
    correction_decision, define_done) used to hardcode their
    system prompts as Python string constants, bypassing PromptService
    and missing LangFuse version tracking.

    Cycle cyc_a867cbf02205 (2026-05-05) caught a regression in the
    initial externalization: composing role identity + task_type
    fragments via assemble() primed spark-squad models to write
    role-play "Initialization Verification" markdown narratives
    instead of the requested JSON. Updated contract: handlers call
    assemble_task_only(role, task_type) — the task_type fragment
    only, no identity / constraints / lifecycle prepend. The
    externalized fragment remains the single source of truth for
    prompt content; LangFuse versioning still applies; identity
    no longer triggers role-play."""

    @pytest.mark.parametrize(
        "handler_cls,role,capability_id",
        [
            (
                DataAnalyzeFailureHandler,
                "data",
                "data.analyze_failure",
            ),
            (
                GovernanceCorrectionDecisionHandler,
                "lead",
                "governance.correction_decision",
            ),
            (
                GovernanceDefineDoneHandler,
                "lead",
                "governance.define_done",
            ),
        ],
        ids=lambda x: x.__name__ if isinstance(x, type) else x,
    )
    async def test_handler_uses_task_only_assembly(
        self, mock_context, handler_cls, role, capability_id
    ):
        # Drive the handler with a minimal-shaped LLM response so the
        # success path runs and reaches the assemble_task_only() call
        # before any parse-validation logic.
        if handler_cls is DataAnalyzeFailureHandler:
            payload = json.dumps(
                {
                    "classification": FailureClassification.EXECUTION,
                    "analysis_summary": "Plenty long enough to pass the gate.",
                    "contributing_factors": ["concrete factor"],
                }
            )
        elif handler_cls is GovernanceCorrectionDecisionHandler:
            payload = json.dumps(
                {
                    "correction_path": "patch",
                    "decision_rationale": "Localized fix",
                    "affected_task_types": [],
                }
            )
        else:  # GovernanceDefineDoneHandler
            payload = json.dumps(
                {
                    "objective": "Build a thing",
                    "acceptance_criteria": ["passes tests"],
                    "non_goals": [],
                    "time_budget_seconds": 600,
                    "stop_conditions": [],
                    "required_artifacts": ["main.py"],
                }
            )
        _set_llm_mock(mock_context, return_value=ChatMessage(role="assistant", content=payload))

        h = handler_cls()
        await h.handle(mock_context, {"prd": "test"})

        # New contract: task_type fragment ONLY — no role identity
        # prepend that primes role-play responses on small models.
        mock_context.ports.prompt_service.assemble_task_only.assert_called_once_with(
            role=role,
            task_type=capability_id,
        )
        # And the legacy full-assembly path must NOT be called for
        # these JSON-emitting handlers.
        mock_context.ports.prompt_service.assemble.assert_not_called()

    async def test_decision_constant_removed(self):
        """Defense against future drift back to a hardcoded string —
        if someone re-introduces a `_DECISION_SYSTEM_PROMPT`-shaped
        constant the import here will start succeeding and surface
        the violation in CI."""
        from squadops.capabilities.handlers.impl import correction_decision as _mod

        assert not hasattr(_mod, "_DECISION_SYSTEM_PROMPT")
        assert not hasattr(_mod, "_ANALYSIS_SYSTEM_PROMPT")
        assert not hasattr(_mod, "_CONTRACT_SYSTEM_PROMPT")

    async def test_analysis_constant_removed(self):
        from squadops.capabilities.handlers.impl import analyze_failure as _mod

        assert not hasattr(_mod, "_ANALYSIS_SYSTEM_PROMPT")

    async def test_contract_constant_removed(self):
        from squadops.capabilities.handlers.impl import define_done as _mod

        assert not hasattr(_mod, "_CONTRACT_SYSTEM_PROMPT")


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


# ---------------------------------------------------------------------------
# _format_failure_summary — deterministic authoritative-instruction blocks
# ---------------------------------------------------------------------------


class TestFailureSummaryEnforcementBlock:
    def test_scaffold_enforcement_rendered_as_authoritative_block(self):
        """SIP-0100 3.4b: frozen-restore instructions carried from a prior attempt
        must reach the repair prompt as an authoritative block — without this the
        repair silently fights the restore (pf-30: three attempts re-emitting
        frozen files against a correct diagnosis)."""
        from squadops.capabilities.handlers.impl.repair_handlers import (
            _format_failure_summary,
        )

        evidence = {
            "scaffold_enforcement": [
                "`backend/main.py` is scaffold-frozen and canonical; do not re-emit it."
            ],
            "validation_result": {"summary": "tests_pass failed"},
        }
        rendered = _format_failure_summary(evidence, None)
        assert "FROZEN OWNERSHIP (authoritative" in rendered
        assert "backend/main.py" in rendered
        # The rest of the evidence still renders alongside it.
        assert "tests_pass failed" in rendered

    def test_no_enforcement_key_renders_no_block(self):
        """Absent/empty scaffold_enforcement must not inject the block."""
        from squadops.capabilities.handlers.impl.repair_handlers import (
            _format_failure_summary,
        )

        assert "FROZEN OWNERSHIP" not in _format_failure_summary(
            {"validation_result": {"summary": "x"}}, None
        )
        assert "FROZEN OWNERSHIP" not in _format_failure_summary({"scaffold_enforcement": []}, None)
