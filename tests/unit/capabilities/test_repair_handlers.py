"""Tests for repair task handlers (SIP-0070 Phase 3).

Covers:
- 4 repair handlers: construction, capability_id, role, artifact_name
- _build_user_prompt(): verification context injection, upstream output filtering
- handle(): LLM success + failure paths (inherited from _CycleTaskHandler)
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from squadops.capabilities.handlers.repair_tasks import (
    DataAnalyzeVerificationHandler,
    DevelopmentRepairHandler,
    GovernanceRootCauseHandler,
    StrategyCorrectivePlanHandler,
    _RepairTaskHandler,
)

pytestmark = [pytest.mark.domain_pulse_checks]


# ---------------------------------------------------------------------------
# Construction + class attributes
# ---------------------------------------------------------------------------


class TestRepairHandlerAttributes:
    def test_data_analyze_verification_attrs(self):
        h = DataAnalyzeVerificationHandler()
        assert h.capability_id == "data.analyze_verification"
        assert h._role == "data"
        assert h._artifact_name == "verification_analysis.md"

    def test_governance_root_cause_attrs(self):
        h = GovernanceRootCauseHandler()
        assert h.capability_id == "governance.root_cause_analysis"
        assert h._role == "lead"
        assert h._artifact_name == "root_cause_analysis.md"

    def test_strategy_corrective_plan_attrs(self):
        h = StrategyCorrectivePlanHandler()
        assert h.capability_id == "strategy.corrective_plan"
        assert h._role == "strat"
        assert h._artifact_name == "corrective_plan.md"

    def test_development_repair_attrs(self):
        h = DevelopmentRepairHandler()
        assert h.capability_id == "development.repair"
        assert h._role == "dev"
        assert h._artifact_name == "repair_output.md"


# ---------------------------------------------------------------------------
# _build_user_prompt
# ---------------------------------------------------------------------------


class TestRepairBuildUserPrompt:
    def test_verification_context_injected(self):
        h = DataAnalyzeVerificationHandler()
        prompt = h._build_user_prompt(
            prd="Build a widget",
            prior_outputs={
                "verification_context": "Boundary: post_dev\nFailed suites: ['s1']",
            },
        )
        assert "## Verification Failure Context" in prompt
        assert "Boundary: post_dev" in prompt
        assert "Failed suites: ['s1']" in prompt

    def test_no_verification_context_omits_section(self):
        h = GovernanceRootCauseHandler()
        prompt = h._build_user_prompt(
            prd="Build a widget",
            prior_outputs={"data": {"summary": "analysis output"}},
        )
        assert "## Verification Failure Context" not in prompt
        assert "## Prior Analysis from Upstream Roles" in prompt

    def test_upstream_outputs_exclude_verification_context(self):
        h = StrategyCorrectivePlanHandler()
        prompt = h._build_user_prompt(
            prd="Build a widget",
            prior_outputs={
                "verification_context": "some context",
                "data": {"summary": "analysis"},
                "lead": {"summary": "root cause"},
            },
        )
        # verification_context should not appear in "Prior Analysis" section
        assert "## Prior Analysis from Upstream Roles" in prompt
        assert "### data" in prompt
        assert "### lead" in prompt
        # verification_context appears in its dedicated section, not upstream
        sections = prompt.split("## Prior Analysis from Upstream Roles")
        assert "verification_context" not in sections[1]

    def test_prd_always_present(self):
        h = DevelopmentRepairHandler()
        prompt = h._build_user_prompt(prd="Fix the bug", prior_outputs=None)
        assert "## Product Requirements Document" in prompt
        assert "Fix the bug" in prompt
        assert "dev" in prompt  # role reference

    def test_empty_prior_outputs(self):
        h = DataAnalyzeVerificationHandler()
        prompt = h._build_user_prompt(prd="PRD text", prior_outputs={})
        assert "## Product Requirements Document" in prompt
        assert "## Verification Failure Context" not in prompt
        assert "## Prior Analysis" not in prompt

    def test_none_prior_outputs(self):
        h = GovernanceRootCauseHandler()
        prompt = h._build_user_prompt(prd="PRD text", prior_outputs=None)
        assert "## Product Requirements Document" in prompt

    def test_only_verification_context_no_upstream_section(self):
        """When prior_outputs has only verification_context, no upstream section appears."""
        h = StrategyCorrectivePlanHandler()
        prompt = h._build_user_prompt(
            prd="Build it",
            prior_outputs={"verification_context": "boundary failed"},
        )
        assert "## Verification Failure Context" in prompt
        assert "## Prior Analysis from Upstream Roles" not in prompt

    def test_all_handlers_produce_distinct_prompts_with_role(self):
        """Each handler injects its own role name into the prompt."""
        for handler_cls, expected_role in [
            (DataAnalyzeVerificationHandler, "data"),
            (GovernanceRootCauseHandler, "lead"),
            (StrategyCorrectivePlanHandler, "strat"),
            (DevelopmentRepairHandler, "dev"),
        ]:
            h = handler_cls()
            prompt = h._build_user_prompt(prd="PRD", prior_outputs=None)
            assert f"your {expected_role} analysis" in prompt


# ---------------------------------------------------------------------------
# handle() — LLM success + failure
# ---------------------------------------------------------------------------


def _make_context(llm_response="Repair analysis content"):
    """Build a minimal ExecutionContext mock for handler tests."""
    llm = AsyncMock()
    llm.chat.return_value = MagicMock(content=llm_response)
    llm.default_model = "test-model"

    prompt_service = MagicMock()
    prompt_service.get_system_prompt.return_value = MagicMock(content="system prompt")

    ports = MagicMock()
    ports.llm = llm
    ports.prompt_service = prompt_service
    ports.llm_observability = None

    ctx = MagicMock()
    ctx.ports = ports
    ctx.correlation_context = None
    return ctx


class TestRepairHandlerHandle:
    async def test_llm_success_returns_artifact(self):
        h = DataAnalyzeVerificationHandler()
        ctx = _make_context(llm_response="Verification analysis: all good")
        result = await h.handle(
            ctx,
            {
                "prd": "Build a widget",
                "prior_outputs": {"verification_context": "failure context"},
            },
        )
        assert result.success is True
        artifacts = result.outputs["artifacts"]
        assert len(artifacts) == 1
        assert artifacts[0]["name"] == "verification_analysis.md"
        assert artifacts[0]["content"] == "Verification analysis: all good"

    async def test_llm_failure_returns_error(self):
        from squadops.llm.exceptions import LLMError

        h = GovernanceRootCauseHandler()
        ctx = _make_context()
        ctx.ports.llm.chat.side_effect = LLMError("model overloaded")
        result = await h.handle(ctx, {"prd": "Build a widget"})
        assert result.success is False
        assert "model overloaded" in result.error

    async def test_each_handler_uses_correct_artifact_name(self):
        ctx = _make_context(llm_response="output")
        for handler_cls, expected_name in [
            (DataAnalyzeVerificationHandler, "verification_analysis.md"),
            (GovernanceRootCauseHandler, "root_cause_analysis.md"),
            (StrategyCorrectivePlanHandler, "corrective_plan.md"),
            (DevelopmentRepairHandler, "repair_output.md"),
        ]:
            h = handler_cls()
            result = await h.handle(ctx, {"prd": "test"})
            assert result.success is True
            assert result.outputs["artifacts"][0]["name"] == expected_name

    async def test_handler_inherits_from_cycle_task_handler(self):
        """Repair handlers are subclasses of _RepairTaskHandler and _CycleTaskHandler."""
        for cls in [
            DataAnalyzeVerificationHandler,
            GovernanceRootCauseHandler,
            StrategyCorrectivePlanHandler,
            DevelopmentRepairHandler,
        ]:
            assert issubclass(cls, _RepairTaskHandler)
