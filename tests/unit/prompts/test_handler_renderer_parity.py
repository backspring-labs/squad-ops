"""Parity tests for Phase 3 handler refactoring (SIP-0084).

Verifies that when RequestTemplateRenderer is available on the PortsBundle,
handlers use it to build user prompts with correct template_id and variables.
Also verifies the fallback path is used when no renderer is available.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from squadops.capabilities.handlers.cycle_tasks import (
    DevelopmentDevelopHandler,
    GovernanceReviewHandler,
    StrategyAnalyzeHandler,
    _CycleTaskHandler,
)
from squadops.capabilities.handlers.planning_tasks import (
    StrategyFrameObjectiveHandler,
)
from squadops.capabilities.handlers.repair_tasks import (
    DataAnalyzeVerificationHandler,
)
from squadops.llm.models import ChatMessage
from squadops.prompts.asset_models import RenderedRequest

pytestmark = [pytest.mark.domain_capabilities]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _mock_renderer(rendered_content: str = "rendered template content") -> AsyncMock:
    """Create a mock RequestTemplateRenderer."""
    renderer = AsyncMock()
    renderer.render = AsyncMock(
        return_value=RenderedRequest(
            content=rendered_content,
            template_id="test",
            template_version="1",
            render_hash=RenderedRequest.compute_hash(rendered_content),
        ),
    )
    return renderer


def _mock_context(*, renderer: AsyncMock | None = None) -> MagicMock:
    """Create a mock ExecutionContext with optional renderer."""
    ctx = MagicMock()
    llm_response = ChatMessage(role="assistant", content="LLM output")
    ctx.ports.llm.chat = AsyncMock(return_value=llm_response)
    ctx.ports.llm.chat_stream_with_usage = AsyncMock(return_value=llm_response)
    ctx.ports.llm.default_model = "test-model"
    assembled = MagicMock()
    assembled.content = "System prompt"
    assembled.assembly_hash = "sha256:test_assembly"
    ctx.ports.prompt_service.get_system_prompt = MagicMock(return_value=assembled)

    if renderer is not None:
        ctx.ports.request_renderer = renderer
    else:
        # Simulate missing attribute (as in pre-SIP-0084 PortsBundle)
        del ctx.ports.request_renderer

    return ctx


# ---------------------------------------------------------------------------
# Wave 1: _CycleTaskHandler base class
# ---------------------------------------------------------------------------


class TestCycleTaskHandlerRendererPath:
    """Verify _CycleTaskHandler.handle() uses renderer when available."""

    async def test_calls_renderer_with_correct_template_id(self):
        renderer = _mock_renderer()
        ctx = _mock_context(renderer=renderer)
        handler = StrategyAnalyzeHandler()

        await handler.handle(ctx, {"prd": "Build a game"})

        renderer.render.assert_called_once()
        call_args = renderer.render.call_args
        assert call_args[0][0] == "request.cycle_task_base"

    async def test_passes_prd_and_role_variables(self):
        renderer = _mock_renderer()
        ctx = _mock_context(renderer=renderer)
        handler = GovernanceReviewHandler()  # role = "lead"

        await handler.handle(ctx, {"prd": "Build a widget"})

        call_args = renderer.render.call_args
        variables = call_args[0][1]
        assert variables["prd"] == "Build a widget"
        assert variables["role"] == "lead"

    async def test_formats_prior_outputs_into_variable(self):
        renderer = _mock_renderer()
        ctx = _mock_context(renderer=renderer)
        handler = StrategyAnalyzeHandler()

        prior = {"dev": "code analysis", "qa": "test plan"}
        await handler.handle(ctx, {"prd": "X", "prior_outputs": prior})

        variables = renderer.render.call_args[0][1]
        prior_text = variables["prior_outputs"]
        assert "## Prior Analysis from Upstream Roles" in prior_text
        assert "### dev" in prior_text
        assert "code analysis" in prior_text
        assert "### qa" in prior_text

    async def test_empty_prior_outputs_produces_empty_string(self):
        renderer = _mock_renderer()
        ctx = _mock_context(renderer=renderer)
        handler = StrategyAnalyzeHandler()

        await handler.handle(ctx, {"prd": "X"})

        variables = renderer.render.call_args[0][1]
        assert variables["prior_outputs"] == ""

    async def test_rendered_content_sent_to_llm(self):
        renderer = _mock_renderer("Custom rendered prompt")
        ctx = _mock_context(renderer=renderer)
        handler = StrategyAnalyzeHandler()

        await handler.handle(ctx, {"prd": "X"})

        # Verify the user message sent to LLM contains rendered content
        call_args = ctx.ports.llm.chat_stream_with_usage.call_args
        messages = call_args[0][0]
        user_msg = [m for m in messages if m.role == "user"][0]
        assert user_msg.content == "Custom rendered prompt"


class TestCycleTaskHandlerFallbackPath:
    """Verify _CycleTaskHandler.handle() falls back when no renderer."""

    async def test_no_renderer_uses_build_user_prompt(self):
        ctx = _mock_context(renderer=None)
        handler = StrategyAnalyzeHandler()

        await handler.handle(ctx, {"prd": "Build a game"})

        call_args = ctx.ports.llm.chat_stream_with_usage.call_args
        messages = call_args[0][0]
        user_msg = [m for m in messages if m.role == "user"][0]
        assert "## Product Requirements Document" in user_msg.content
        assert "Build a game" in user_msg.content
        assert "strat analysis and deliverables" in user_msg.content


# ---------------------------------------------------------------------------
# Wave 1: DevelopmentDevelopHandler
# ---------------------------------------------------------------------------


class TestDevelopmentDevelopRendererPath:
    """Verify DevelopmentDevelopHandler.handle() uses renderer when available."""

    async def test_calls_renderer_with_dev_template_id(self):
        renderer = _mock_renderer()
        ctx = _mock_context(renderer=renderer)
        handler = DevelopmentDevelopHandler()

        inputs = {
            "prd": "Build a game",
            "artifact_contents": {
                "implementation_plan.md": "Plan content",
                "strategy_analysis.md": "Strategy content",
            },
        }

        await handler.handle(ctx, inputs)

        renderer.render.assert_called_once()
        call_args = renderer.render.call_args
        assert call_args[0][0] == "request.development_develop.code_generate"

    async def test_passes_capability_and_artifact_variables(self):
        renderer = _mock_renderer()
        ctx = _mock_context(renderer=renderer)
        handler = DevelopmentDevelopHandler()

        inputs = {
            "prd": "Build a game",
            "artifact_contents": {
                "implementation_plan.md": "Plan content",
                "strategy_analysis.md": "Strategy content",
            },
        }

        await handler.handle(ctx, inputs)

        variables = renderer.render.call_args[0][1]
        assert variables["prd"] == "Build a game"
        assert "file_structure_guidance" in variables
        assert "example_structure" in variables
        assert "## Implementation Plan" in variables["impl_plan"]
        assert "Plan content" in variables["impl_plan"]
        assert "## Strategy Analysis" in variables["strategy"]

    async def test_omits_optional_plan_variables_when_absent(self):
        renderer = _mock_renderer()
        ctx = _mock_context(renderer=renderer)
        handler = DevelopmentDevelopHandler()

        inputs = {
            "prd": "Build a game",
            "artifact_contents": {},
        }

        await handler.handle(ctx, inputs)

        variables = renderer.render.call_args[0][1]
        assert "impl_plan" not in variables
        assert "strategy" not in variables

    async def test_prior_outputs_formatted_for_template(self):
        renderer = _mock_renderer()
        ctx = _mock_context(renderer=renderer)
        handler = DevelopmentDevelopHandler()

        inputs = {
            "prd": "X",
            "artifact_contents": {"implementation_plan.md": "Plan"},
            "prior_outputs": {"strat": "analysis"},
        }

        await handler.handle(ctx, inputs)

        variables = renderer.render.call_args[0][1]
        assert "## Prior Analysis" in variables["prior_outputs"]
        assert "### strat" in variables["prior_outputs"]


class TestDevelopmentDevelopFallbackPath:
    """Verify DevelopmentDevelopHandler falls back when no renderer."""

    async def test_no_renderer_uses_build_user_prompt(self):
        ctx = _mock_context(renderer=None)
        handler = DevelopmentDevelopHandler()

        inputs = {
            "prd": "Build a game",
            "artifact_contents": {
                "implementation_plan.md": "Plan content",
            },
        }

        await handler.handle(ctx, inputs)

        call_args = ctx.ports.llm.chat_stream_with_usage.call_args
        messages = call_args[0][0]
        user_msg = [m for m in messages if m.role == "user"][0]
        assert "## Product Requirements Document" in user_msg.content
        assert "Build a game" in user_msg.content


# ---------------------------------------------------------------------------
# Wave 2: _PlanningTaskHandler base class
# ---------------------------------------------------------------------------


def _mock_planning_context(*, renderer: AsyncMock | None = None) -> MagicMock:
    """Create a mock ExecutionContext for planning handlers (uses assemble())."""
    ctx = MagicMock()
    llm_response = MagicMock(content="LLM output")
    ctx.ports.llm.chat = AsyncMock(return_value=llm_response)
    ctx.ports.llm.chat_stream_with_usage = AsyncMock(return_value=llm_response)
    ctx.ports.llm.default_model = "test-model"
    assembled = MagicMock()
    assembled.content = "System prompt"
    assembled.assembly_hash = "sha256:test_planning_assembly"
    ctx.ports.prompt_service.assemble = MagicMock(return_value=assembled)
    ctx.ports.prompt_service.get_system_prompt = MagicMock(return_value=assembled)
    ctx.ports.llm_observability = None
    ctx.correlation_context = None

    if renderer is not None:
        ctx.ports.request_renderer = renderer
    else:
        ctx.ports.request_renderer = None

    return ctx


class TestPlanningTaskHandlerRendererPath:
    """Verify _PlanningTaskHandler.handle() uses renderer when available."""

    async def test_calls_renderer_with_planning_template_id(self):
        renderer = _mock_renderer()
        ctx = _mock_planning_context(renderer=renderer)
        handler = StrategyFrameObjectiveHandler()

        await handler.handle(ctx, {"prd": "Plan a game"})

        renderer.render.assert_called_once()
        assert renderer.render.call_args[0][0] == "request.planning_task_base"

    async def test_passes_time_budget_section_when_present(self):
        renderer = _mock_renderer()
        ctx = _mock_planning_context(renderer=renderer)
        handler = StrategyFrameObjectiveHandler()

        inputs = {
            "prd": "Plan a game",
            "resolved_config": {"time_budget_seconds": 3600},
        }
        await handler.handle(ctx, inputs)

        variables = renderer.render.call_args[0][1]
        assert "time_budget_section" in variables
        assert "1 hour" in variables["time_budget_section"]

    async def test_omits_time_budget_when_absent(self):
        renderer = _mock_renderer()
        ctx = _mock_planning_context(renderer=renderer)
        handler = StrategyFrameObjectiveHandler()

        await handler.handle(ctx, {"prd": "Plan a game"})

        variables = renderer.render.call_args[0][1]
        assert "time_budget_section" not in variables

    async def test_passes_role_variable(self):
        renderer = _mock_renderer()
        ctx = _mock_planning_context(renderer=renderer)
        handler = StrategyFrameObjectiveHandler()  # role = "strat"

        await handler.handle(ctx, {"prd": "X"})

        variables = renderer.render.call_args[0][1]
        assert variables["role"] == "strat"


class TestPlanningTaskHandlerFallbackPath:
    async def test_no_renderer_uses_build_user_prompt(self):
        ctx = _mock_planning_context(renderer=None)
        handler = StrategyFrameObjectiveHandler()

        await handler.handle(ctx, {"prd": "Plan a game"})

        call_args = ctx.ports.llm.chat_stream_with_usage.call_args
        messages = call_args[0][0]
        user_msg = [m for m in messages if m.role == "user"][0]
        assert "## Product Requirements Document" in user_msg.content
        assert "Plan a game" in user_msg.content


# ---------------------------------------------------------------------------
# Wave 2: _RepairTaskHandler base class
# ---------------------------------------------------------------------------


class TestRepairTaskHandlerRendererPath:
    """Verify _RepairTaskHandler uses repair template with verification context."""

    async def test_calls_renderer_with_repair_template_id(self):
        renderer = _mock_renderer()
        ctx = _mock_context(renderer=renderer)
        handler = DataAnalyzeVerificationHandler()

        await handler.handle(ctx, {"prd": "Fix the bug"})

        renderer.render.assert_called_once()
        assert renderer.render.call_args[0][0] == "request.repair_task_base"

    async def test_extracts_verification_context_from_prior_outputs(self):
        renderer = _mock_renderer()
        ctx = _mock_context(renderer=renderer)
        handler = DataAnalyzeVerificationHandler()

        inputs = {
            "prd": "Fix it",
            "prior_outputs": {
                "verification_context": "Tests failed: 3 errors",
                "data": "upstream analysis",
            },
        }
        await handler.handle(ctx, inputs)

        variables = renderer.render.call_args[0][1]
        assert "Verification Failure Context" in variables["verification_context"]
        assert "Tests failed: 3 errors" in variables["verification_context"]
        # Upstream outputs should NOT include verification_context key
        assert "### data" in variables["prior_outputs"]
        assert "verification_context" not in variables["prior_outputs"]

    async def test_empty_verification_context_gives_empty_string(self):
        renderer = _mock_renderer()
        ctx = _mock_context(renderer=renderer)
        handler = DataAnalyzeVerificationHandler()

        await handler.handle(ctx, {"prd": "Fix it"})

        variables = renderer.render.call_args[0][1]
        assert variables["verification_context"] == ""


class TestRepairTaskHandlerFallbackPath:
    async def test_no_renderer_uses_build_user_prompt(self):
        ctx = _mock_context(renderer=None)
        handler = DataAnalyzeVerificationHandler()

        await handler.handle(ctx, {"prd": "Fix it"})

        call_args = ctx.ports.llm.chat_stream_with_usage.call_args
        messages = call_args[0][0]
        user_msg = [m for m in messages if m.role == "user"][0]
        assert "## Product Requirements Document" in user_msg.content


# ---------------------------------------------------------------------------
# _format_prior_outputs helper
# ---------------------------------------------------------------------------


class TestFormatPriorOutputs:
    """Verify the static helper formats prior outputs consistently."""

    def test_none_returns_empty(self):
        assert _CycleTaskHandler._format_prior_outputs(None) == ""

    def test_empty_dict_returns_empty(self):
        assert _CycleTaskHandler._format_prior_outputs({}) == ""

    def test_single_role_formatted(self):
        result = _CycleTaskHandler._format_prior_outputs({"dev": "analysis"})
        assert "## Prior Analysis from Upstream Roles" in result
        assert "### dev" in result
        assert "analysis" in result

    def test_multiple_roles_all_present(self):
        result = _CycleTaskHandler._format_prior_outputs(
            {"dev": "code review", "qa": "test plan", "strat": "strategy"}
        )
        assert "### dev" in result
        assert "### qa" in result
        assert "### strat" in result


# ---------------------------------------------------------------------------
# Phase 5: Prompt provenance recording
# ---------------------------------------------------------------------------


class TestProvenanceRecording:
    """Verify handlers include prompt_provenance in outputs."""

    async def test_base_handler_records_stage1_provenance(self):
        ctx = _mock_context(renderer=None)
        handler = StrategyAnalyzeHandler()

        result = await handler.handle(ctx, {"prd": "Build a game"})

        prov = result.outputs.get("prompt_provenance", {})
        assert prov["system_prompt_bundle_hash"] == "sha256:test_assembly"
        # No renderer → no Stage 2 provenance
        assert "request_template_id" not in prov

    async def test_base_handler_records_stage2_when_renderer_used(self):
        renderer = _mock_renderer("rendered content")
        ctx = _mock_context(renderer=renderer)
        handler = StrategyAnalyzeHandler()

        result = await handler.handle(ctx, {"prd": "Build a game"})

        prov = result.outputs["prompt_provenance"]
        assert prov["system_prompt_bundle_hash"] == "sha256:test_assembly"
        assert prov["request_template_id"] == "test"
        assert prov["request_template_version"] == "1"
        assert prov["request_render_hash"] == RenderedRequest.compute_hash("rendered content")
        assert prov["prompt_environment"] == "production"

    async def test_planning_handler_records_provenance(self):
        renderer = _mock_renderer("planning output")
        ctx = _mock_planning_context(renderer=renderer)
        handler = StrategyFrameObjectiveHandler()

        result = await handler.handle(ctx, {"prd": "Plan it"})

        prov = result.outputs["prompt_provenance"]
        assert prov["system_prompt_bundle_hash"] == "sha256:test_planning_assembly"
        assert prov["request_template_id"] == "test"

    async def test_planning_handler_no_renderer_stage1_only(self):
        ctx = _mock_planning_context(renderer=None)
        handler = StrategyFrameObjectiveHandler()

        result = await handler.handle(ctx, {"prd": "Plan it"})

        prov = result.outputs["prompt_provenance"]
        assert prov["system_prompt_bundle_hash"] == "sha256:test_planning_assembly"
        assert "request_template_id" not in prov
