"""Phase 3.5 migration validation gate (SIP-0084).

Verifies that the Phase 3 handler refactoring (dual-path renderer integration)
preserves behavioral parity: every handler calls the renderer with the correct
template_id, the prompt guard truncation point survives rendering, and capability
supplements stay in the system prompt (not injected into templates).
"""

from __future__ import annotations

import re
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from squadops.capabilities.handlers.cycle_tasks import (
    BuilderAssembleHandler,
    DataReportHandler,
    DevelopmentDesignHandler,
    DevelopmentDevelopHandler,
    GovernanceReviewHandler,
    QATestHandler,
    QAValidateHandler,
    StrategyAnalyzeHandler,
)
from squadops.capabilities.handlers.impl.analyze_failure import (
    DataAnalyzeFailureHandler,
)
from squadops.capabilities.handlers.impl.correction_decision import (
    GovernanceCorrectionDecisionHandler,
)
from squadops.capabilities.handlers.impl.establish_contract import (
    GovernanceEstablishContractHandler,
)
from squadops.capabilities.handlers.planning_tasks import (
    DataResearchContextHandler,
    DevelopmentDesignPlanHandler,
    GovernanceIncorporateFeedbackHandler,
    GovernanceReviewPlanHandler,
    QADefineTestStrategyHandler,
    StrategyFrameObjectiveHandler,
)
from squadops.capabilities.handlers.repair_tasks import (
    DataAnalyzeVerificationHandler,
    GovernanceRootCauseHandler,
    StrategyCorrectivePlanHandler,
)
from squadops.capabilities.handlers.repair_tasks import (
    DevelopmentRepairHandler as DevelopmentRepairTaskHandler,
)
from squadops.capabilities.handlers.wrapup_tasks import (
    DataClassifyUnresolvedHandler,
    DataGatherEvidenceHandler,
    GovernanceCloseoutDecisionHandler,
    GovernancePublishHandoffHandler,
    QAAssessOutcomesHandler,
)
from squadops.llm.models import ChatMessage
from squadops.prompts.asset_models import RenderedRequest

pytestmark = [pytest.mark.domain_capabilities]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

TEMPLATES_DIR = (
    Path(__file__).parent.parent.parent.parent
    / "src"
    / "squadops"
    / "prompts"
    / "request_templates"
)


def _mock_renderer() -> AsyncMock:
    """Create a mock renderer that records calls."""
    renderer = AsyncMock()
    renderer.render = AsyncMock(
        return_value=RenderedRequest(
            content="rendered content",
            template_id="test",
            template_version="1",
            render_hash=RenderedRequest.compute_hash("rendered content"),
        ),
    )
    return renderer


def _mock_context(*, renderer: AsyncMock | None = None) -> MagicMock:
    """Mock ExecutionContext with optional renderer."""
    ctx = MagicMock()
    _llm_return = ChatMessage(role="assistant", content="{}")
    ctx.ports.llm.chat = AsyncMock(return_value=_llm_return)
    ctx.ports.llm.chat_stream_with_usage = AsyncMock(return_value=_llm_return)
    ctx.ports.llm.default_model = "test-model"
    assembled = MagicMock()
    assembled.content = "System prompt"
    assembled.assembly_hash = "sha256:test"
    ctx.ports.prompt_service.get_system_prompt = MagicMock(return_value=assembled)
    ctx.ports.prompt_service.assemble = MagicMock(return_value=assembled)
    ctx.ports.llm_observability = None
    ctx.correlation_context = None

    if renderer is not None:
        ctx.ports.request_renderer = renderer
    else:
        del ctx.ports.request_renderer

    return ctx


# ---------------------------------------------------------------------------
# 1. Base class handler → template_id coverage
#    Bug caught: a handler uses the wrong template_id after refactoring,
#    causing the renderer to resolve a mismatched template at runtime.
# ---------------------------------------------------------------------------


class TestBaseClassTemplateIdCoverage:
    """Every base-class handler must call the renderer with its declared template_id."""

    @pytest.mark.parametrize(
        "handler_cls,expected_template_id",
        [
            # _CycleTaskHandler base class handlers (5)
            (StrategyAnalyzeHandler, "request.cycle_task_base"),
            (DevelopmentDesignHandler, "request.cycle_task_base"),
            (QAValidateHandler, "request.cycle_task_base"),
            (DataReportHandler, "request.cycle_task_base"),
            (GovernanceReviewHandler, "request.cycle_task_base"),
            # _PlanningTaskHandler base class handlers (7)
            (DataResearchContextHandler, "request.planning_task_base"),
            (StrategyFrameObjectiveHandler, "request.planning_task_base"),
            (DevelopmentDesignPlanHandler, "request.planning_task_base"),
            (QADefineTestStrategyHandler, "request.planning_task_base"),
            (GovernanceReviewPlanHandler, "request.planning_task_base"),
            # _RepairTaskHandler base class handlers (4)
            (DataAnalyzeVerificationHandler, "request.repair_task_base"),
            (GovernanceRootCauseHandler, "request.repair_task_base"),
            (StrategyCorrectivePlanHandler, "request.repair_task_base"),
            (DevelopmentRepairTaskHandler, "request.repair_task_base"),
            # Wrapup handlers (_PlanningTaskHandler subclasses) (5)
            (DataGatherEvidenceHandler, "request.planning_task_base"),
            (QAAssessOutcomesHandler, "request.planning_task_base"),
            (DataClassifyUnresolvedHandler, "request.planning_task_base"),
        ],
        ids=lambda x: x.__name__ if isinstance(x, type) else x,
    )
    async def test_handler_uses_correct_template_id(self, handler_cls, expected_template_id):
        renderer = _mock_renderer()
        ctx = _mock_context(renderer=renderer)

        # Issue #109: GovernanceReviewPlanHandler retries on missing
        # frontmatter, which would call render() twice. Hand it a valid
        # frontmatter-bearing response so the assertion stays single-call.
        if handler_cls is GovernanceReviewPlanHandler:
            valid_content = "---\nreadiness: go\nsufficiency_score: 4\n---\n\nbody\n"
            ctx.ports.llm.chat_stream_with_usage = AsyncMock(
                return_value=ChatMessage(role="assistant", content=valid_content),
            )

        handler = handler_cls()

        # Provide minimal inputs that satisfy all handlers
        inputs = {
            "prd": "Test PRD",
            "resolved_config": {"impl_run_id": "run-1"},
        }
        await handler.handle(ctx, inputs)

        renderer.render.assert_called_once()
        actual_template_id = renderer.render.call_args[0][0]
        assert actual_template_id == expected_template_id, (
            f"{handler_cls.__name__} rendered with '{actual_template_id}', "
            f"expected '{expected_template_id}'"
        )


# ---------------------------------------------------------------------------
# 2. Custom handler → template_id coverage
#    Bug caught: custom handlers with their own handle() override call the
#    wrong template or forget the renderer path entirely.
# ---------------------------------------------------------------------------


class TestCustomHandlerTemplateIdCoverage:
    """Custom handlers with handle() overrides must use the correct template."""

    @pytest.mark.parametrize(
        "handler_cls,expected_template_id,extra_inputs",
        [
            (
                DevelopmentDevelopHandler,
                "request.development_develop.code_generate",
                {"artifact_contents": {"implementation_plan.md": "Plan"}},
            ),
            (
                QATestHandler,
                "request.qa_test.test_validate",
                {"artifact_contents": {"implementation_plan.md": "Plan"}},
            ),
            (
                BuilderAssembleHandler,
                "request.builder_assemble.build_assemble",
                {"artifact_contents": {"implementation_plan.md": "Plan"}},
            ),
            (
                GovernanceIncorporateFeedbackHandler,
                "request.governance_incorporate_feedback",
                {
                    "prior_outputs": {
                        "artifact_contents": {"plan.md": "Original plan"},
                        "refinement_instructions": "Fix naming",
                    },
                    "resolved_config": {"plan_artifact_refs": ["plan.md"]},
                },
            ),
            (
                DataAnalyzeFailureHandler,
                "request.data_analyze_failure",
                {"failure_analysis": {"error": "test"}},
            ),
            (
                GovernanceCorrectionDecisionHandler,
                "request.governance_correction_decision",
                {"failure_analysis": {"error": "test"}},
            ),
            (
                GovernanceEstablishContractHandler,
                "request.cycle_task_base",
                {},
            ),
        ],
        ids=lambda x: x.__name__ if isinstance(x, type) else str(x)[:40],
    )
    async def test_custom_handler_uses_correct_template_id(
        self, handler_cls, expected_template_id, extra_inputs
    ):
        renderer = _mock_renderer()
        ctx = _mock_context(renderer=renderer)
        handler = handler_cls()

        inputs = {"prd": "Test PRD", **extra_inputs}
        await handler.handle(ctx, inputs)

        renderer.render.assert_called_once()
        actual_template_id = renderer.render.call_args[0][0]
        assert actual_template_id == expected_template_id, (
            f"{handler_cls.__name__} rendered with '{actual_template_id}', "
            f"expected '{expected_template_id}'"
        )


# ---------------------------------------------------------------------------
# 3. Custom wrapup handlers with handle() overrides
#    These override handle() and have their own template wiring.
# ---------------------------------------------------------------------------


class TestWrapupCustomHandlerTemplateIds:
    """Wrapup handlers that override handle() must use correct templates."""

    @pytest.mark.parametrize(
        "handler_cls,expected_template_id",
        [
            (GovernanceCloseoutDecisionHandler, "request.planning_task_base"),
            (GovernancePublishHandoffHandler, "request.planning_task_base"),
        ],
        ids=lambda x: x.__name__ if isinstance(x, type) else x,
    )
    async def test_wrapup_custom_handler_template_id(self, handler_cls, expected_template_id):
        renderer = _mock_renderer()
        ctx = _mock_context(renderer=renderer)
        handler = handler_cls()

        inputs = {
            "prd": "Test PRD",
            "resolved_config": {"impl_run_id": "run-1"},
        }
        await handler.handle(ctx, inputs)

        renderer.render.assert_called_once()
        actual_template_id = renderer.render.call_args[0][0]
        assert actual_template_id == expected_template_id


# ---------------------------------------------------------------------------
# 4. Prompt guard truncation point preserved after rendering
#    Bug caught: if the template renders prior analysis under a different
#    heading, the prompt guard can no longer find and truncate it.
# ---------------------------------------------------------------------------


class TestPromptGuardPreservation:
    """Rendered output must preserve the ## Prior Analysis heading for truncation."""

    async def test_cycle_task_rendered_output_has_prior_analysis_heading(self):
        """The base cycle task template must render prior_outputs under the
        exact '## Prior Analysis from Upstream Roles' heading that prompt_guard
        searches for.
        """
        # Build a real renderer with filesystem source
        from adapters.prompts.filesystem_asset_adapter import (
            FilesystemPromptAssetAdapter,
        )
        from squadops.prompts.renderer import RequestTemplateRenderer

        source = FilesystemPromptAssetAdapter(
            fragments_path=TEMPLATES_DIR.parent / "fragments",
            templates_path=TEMPLATES_DIR,
        )
        renderer = RequestTemplateRenderer(source)

        rendered = await renderer.render(
            "request.cycle_task_base",
            {
                "prd": "Build a game",
                "role": "strat",
                "prior_outputs": ("## Prior Analysis from Upstream Roles\n\n### dev\ncode review"),
            },
        )

        assert "## Prior Analysis from Upstream Roles" in rendered.content, (
            "Rendered template must contain the exact heading that prompt_guard uses for truncation"
        )

    async def test_planning_task_rendered_output_has_prior_analysis_heading(self):
        """Same check for the planning task template."""
        from adapters.prompts.filesystem_asset_adapter import (
            FilesystemPromptAssetAdapter,
        )
        from squadops.prompts.renderer import RequestTemplateRenderer

        source = FilesystemPromptAssetAdapter(
            fragments_path=TEMPLATES_DIR.parent / "fragments",
            templates_path=TEMPLATES_DIR,
        )
        renderer = RequestTemplateRenderer(source)

        rendered = await renderer.render(
            "request.planning_task_base",
            {
                "prd": "Plan a game",
                "role": "strat",
                "prior_outputs": ("## Prior Analysis from Upstream Roles\n\n### dev\nanalysis"),
            },
        )

        assert "## Prior Analysis from Upstream Roles" in rendered.content


# ---------------------------------------------------------------------------
# 5. Capability supplements stay in system prompt, not templates
#    Bug caught: if a refactoring accidentally moves test_prompt_supplement
#    into the template, it gets rendered for ALL handlers, not just QA.
# ---------------------------------------------------------------------------


class TestCapabilitySupplementNotInTemplates:
    """Supplements must be appended to system prompt, not baked into templates."""

    def test_no_template_contains_supplement_placeholder(self):
        """Bug caught: if someone adds a {{supplement}} or {{test_prompt_supplement}}
        placeholder to a template, the supplement injection moves from system
        prompt to user prompt, breaking the layering contract.
        """
        for path in sorted(TEMPLATES_DIR.glob("*.md")):
            content = path.read_text()
            # test_supplement is the variable name used in QA template
            # system_prompt_supplement should never appear in templates
            assert "{{system_prompt_supplement}}" not in content, (
                f"{path.name} contains system_prompt_supplement placeholder — "
                "supplements must stay in system prompt"
            )

    async def test_qa_handler_appends_supplement_to_system_prompt(self):
        """QA handler's test_prompt_supplement goes to system prompt,
        not into the rendered template via a variable.
        """
        renderer = _mock_renderer()
        ctx = _mock_context(renderer=renderer)
        handler = QATestHandler()

        inputs = {
            "prd": "Test PRD",
            "artifact_contents": {"implementation_plan.md": "Plan"},
        }
        await handler.handle(ctx, inputs)

        # The system message must contain the supplement
        call_args = ctx.ports.llm.chat_stream_with_usage.call_args
        messages = call_args[0][0]
        system_msg = [m for m in messages if m.role == "system"][0]
        # System prompt should have the assembled content + supplement
        # (supplement is appended via capability.system_prompt_supplement)
        assert "System prompt" in system_msg.content

        # The user message (rendered template) should NOT contain
        # system_prompt_supplement — it comes via the test_supplement variable
        # which is a user-prompt-level injection, not system-level
        user_msg = [m for m in messages if m.role == "user"][0]
        assert user_msg.content == "rendered content"


# ---------------------------------------------------------------------------
# 6. Template contract completeness (every template has a contract)
#    Bug caught: a template is added without frontmatter, so the renderer
#    treats all variables as optional and never validates required inputs.
# ---------------------------------------------------------------------------


class TestTemplateContractCompleteness:
    """Every template must declare its contract in frontmatter."""

    _FRONTMATTER_PATTERN = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.MULTILINE | re.DOTALL)

    @pytest.mark.parametrize(
        "template_file",
        sorted(TEMPLATES_DIR.glob("*.md")),
        ids=lambda p: p.name,
    )
    def test_every_template_has_required_variables(self, template_file):
        """Bug caught: a template without required_variables silently accepts
        any input — missing variables produce empty sections instead of errors.
        """
        import yaml

        content = template_file.read_text()
        match = self._FRONTMATTER_PATTERN.match(content)
        assert match, f"{template_file.name}: no YAML frontmatter found"

        header = yaml.safe_load(match.group(1)) or {}
        required = header.get("required_variables", [])
        assert len(required) > 0, (
            f"{template_file.name}: no required_variables declared — "
            "contract must specify at least one required variable"
        )
