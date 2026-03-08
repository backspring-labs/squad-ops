"""Tests for planning and refinement task handlers (SIP-0078).

Covers:
- 5 planning handlers + 2 refinement handlers: class attributes, capability_id, role
- _PlanningTaskHandler base: assemble() called with task_type (not get_system_prompt)
- validate_inputs: prd required, plan_artifact_refs for refinement
- handle(): LLM success/failure, artifact names, prior_outputs chaining
- GovernanceIncorporateFeedbackHandler: custom validation, dual artifacts
- Bootstrap registration: all 7 handlers in HANDLER_CONFIGS
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from squadops.bootstrap.handlers import HANDLER_CONFIGS
from squadops.capabilities.handlers.base import HandlerEvidence, HandlerResult
from squadops.capabilities.handlers.planning_tasks import (
    DataResearchContextHandler,
    DevelopmentDesignPlanHandler,
    GovernanceAssessReadinessHandler,
    GovernanceIncorporateFeedbackHandler,
    QADefineTestStrategyHandler,
    QAValidateRefinementHandler,
    StrategyFrameObjectiveHandler,
    _build_refinement_time_budget_section,
    _build_time_budget_section,
    _format_time_budget,
)
from squadops.llm.exceptions import LLMError

pytestmark = [pytest.mark.domain_capabilities]


# ---------------------------------------------------------------------------
# Parametrised data
# ---------------------------------------------------------------------------

PLANNING_HANDLER_SPECS = [
    (DataResearchContextHandler, "data.research_context", "data", "context_research.md"),
    (StrategyFrameObjectiveHandler, "strategy.frame_objective", "strat", "objective_frame.md"),
    (DevelopmentDesignPlanHandler, "development.design_plan", "dev", "technical_design.md"),
    (QADefineTestStrategyHandler, "qa.define_test_strategy", "qa", "test_strategy.md"),
    (
        GovernanceAssessReadinessHandler,
        "governance.assess_readiness",
        "lead",
        "planning_artifact.md",
    ),
]

REFINEMENT_HANDLER_SPECS = [
    (
        GovernanceIncorporateFeedbackHandler,
        "governance.incorporate_feedback",
        "lead",
        "planning_artifact_revised.md",
    ),
    (QAValidateRefinementHandler, "qa.validate_refinement", "qa", "refinement_validation.md"),
]

ALL_HANDLER_SPECS = PLANNING_HANDLER_SPECS + REFINEMENT_HANDLER_SPECS
ALL_HANDLER_CLASSES = [cls for cls, _, _, _ in ALL_HANDLER_SPECS]

# Handlers that work with generic "LLM planning output" and no special prior_outputs.
# GovernanceAssessReadinessHandler requires valid YAML frontmatter in LLM response.
# GovernanceIncorporateFeedbackHandler requires artifact_contents in prior_outputs (D17).
_SPECIAL_HANDLERS = (GovernanceAssessReadinessHandler, GovernanceIncorporateFeedbackHandler)
GENERIC_HANDLER_SPECS = [s for s in ALL_HANDLER_SPECS if s[0] not in _SPECIAL_HANDLERS]
GENERIC_HANDLER_CLASSES = [cls for cls, _, _, _ in GENERIC_HANDLER_SPECS]
# Handlers where LLM is always reached (GovernanceIncorporateFeedbackHandler may
# short-circuit at D17 before calling LLM).
LLM_REACHABLE_SPECS = [s for s in ALL_HANDLER_SPECS if s[0] != GovernanceIncorporateFeedbackHandler]
LLM_REACHABLE_CLASSES = [cls for cls, _, _, _ in LLM_REACHABLE_SPECS]

VALID_PLANNING_ARTIFACT = """\
---
readiness: go
sufficiency_score: 4
blocker_unknowns: 0
---

## Consolidated Planning Artifact

This is a valid planning artifact with proper YAML frontmatter.
"""


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_context(llm_response="LLM planning output"):
    """Build a minimal ExecutionContext mock for planning handler tests."""
    llm = AsyncMock()
    llm.chat.return_value = MagicMock(content=llm_response)
    llm.default_model = "test-model"

    # prompt_service must have assemble() (not just get_system_prompt)
    prompt_service = MagicMock()
    assembled = MagicMock()
    assembled.content = "Assembled system prompt with task_type layer"
    prompt_service.assemble.return_value = assembled
    prompt_service.get_system_prompt.return_value = assembled

    ports = MagicMock()
    ports.llm = llm
    ports.prompt_service = prompt_service
    ports.llm_observability = None

    ctx = MagicMock()
    ctx.ports = ports
    ctx.correlation_context = None
    return ctx


@pytest.fixture()
def mock_context():
    return _make_context()


# ---------------------------------------------------------------------------
# 1. Class attributes
# ---------------------------------------------------------------------------


class TestPlanningHandlerAttributes:
    @pytest.mark.parametrize(
        "cls, expected_cap_id, expected_role, expected_artifact",
        ALL_HANDLER_SPECS,
        ids=[c.__name__ for c, _, _, _ in ALL_HANDLER_SPECS],
    )
    def test_capability_id(self, cls, expected_cap_id, expected_role, expected_artifact):
        h = cls()
        assert h.capability_id == expected_cap_id

    @pytest.mark.parametrize(
        "cls, expected_cap_id, expected_role, expected_artifact",
        ALL_HANDLER_SPECS,
        ids=[c.__name__ for c, _, _, _ in ALL_HANDLER_SPECS],
    )
    def test_role(self, cls, expected_cap_id, expected_role, expected_artifact):
        h = cls()
        assert h._role == expected_role

    @pytest.mark.parametrize(
        "cls, expected_cap_id, expected_role, expected_artifact",
        ALL_HANDLER_SPECS,
        ids=[c.__name__ for c, _, _, _ in ALL_HANDLER_SPECS],
    )
    def test_artifact_name(self, cls, expected_cap_id, expected_role, expected_artifact):
        h = cls()
        assert h._artifact_name == expected_artifact

    @pytest.mark.parametrize(
        "cls",
        ALL_HANDLER_CLASSES,
        ids=[c.__name__ for c in ALL_HANDLER_CLASSES],
    )
    def test_name_non_empty(self, cls):
        h = cls()
        assert isinstance(h.name, str)
        assert len(h.name) > 0


# ---------------------------------------------------------------------------
# 2. validate_inputs
# ---------------------------------------------------------------------------


class TestValidateInputs:
    @pytest.mark.parametrize(
        "cls",
        ALL_HANDLER_CLASSES,
        ids=[c.__name__ for c in ALL_HANDLER_CLASSES],
    )
    def test_missing_prd(self, cls):
        h = cls()
        errors = h.validate_inputs({})
        assert "'prd' is required" in errors

    @pytest.mark.parametrize(
        "cls",
        [c for c in ALL_HANDLER_CLASSES if c != GovernanceIncorporateFeedbackHandler],
        ids=[c.__name__ for c in ALL_HANDLER_CLASSES if c != GovernanceIncorporateFeedbackHandler],
    )
    def test_valid_inputs_with_prd(self, cls):
        h = cls()
        errors = h.validate_inputs({"prd": "something"})
        assert errors == []


class TestRefinementValidation:
    """GovernanceIncorporateFeedbackHandler has additional validation (D17)."""

    def test_missing_plan_artifact_refs(self):
        h = GovernanceIncorporateFeedbackHandler()
        errors = h.validate_inputs({"prd": "test", "resolved_config": {}})
        assert any("plan_artifact_refs" in e for e in errors)

    def test_empty_plan_artifact_refs(self):
        h = GovernanceIncorporateFeedbackHandler()
        errors = h.validate_inputs(
            {
                "prd": "test",
                "resolved_config": {"plan_artifact_refs": []},
            }
        )
        assert any("plan_artifact_refs" in e for e in errors)

    def test_multiple_plan_artifact_refs_rejected(self):
        h = GovernanceIncorporateFeedbackHandler()
        errors = h.validate_inputs(
            {
                "prd": "test",
                "resolved_config": {"plan_artifact_refs": ["ref1", "ref2"]},
            }
        )
        assert any("exactly one" in e for e in errors)

    def test_valid_single_ref(self):
        h = GovernanceIncorporateFeedbackHandler()
        errors = h.validate_inputs(
            {
                "prd": "test",
                "resolved_config": {"plan_artifact_refs": ["ref1"]},
            }
        )
        assert errors == []

    def test_no_resolved_config_at_all(self):
        h = GovernanceIncorporateFeedbackHandler()
        errors = h.validate_inputs({"prd": "test"})
        assert any("plan_artifact_refs" in e for e in errors)


# ---------------------------------------------------------------------------
# 3. handle() — uses assemble() with task_type (key difference from _CycleTaskHandler)
# ---------------------------------------------------------------------------


class TestHandleUsesAssemble:
    """Planning handlers must call assemble(role, hook, task_type=capability_id)."""

    @pytest.mark.parametrize(
        "cls, expected_cap_id, expected_role, _artifact",
        LLM_REACHABLE_SPECS,
        ids=[c.__name__ for c, _, _, _ in LLM_REACHABLE_SPECS],
    )
    async def test_assemble_called_with_task_type(
        self, cls, expected_cap_id, expected_role, _artifact, mock_context
    ):
        h = cls()
        await h.handle(mock_context, {"prd": "Build a widget"})

        mock_context.ports.prompt_service.assemble.assert_called_once_with(
            role=expected_role,
            hook="agent_start",
            task_type=expected_cap_id,
        )

    @pytest.mark.parametrize(
        "cls",
        ALL_HANDLER_CLASSES,
        ids=[c.__name__ for c in ALL_HANDLER_CLASSES],
    )
    async def test_get_system_prompt_not_called(self, cls, mock_context):
        """Planning handlers should NOT call get_system_prompt (legacy path)."""
        h = cls()
        await h.handle(mock_context, {"prd": "Build a widget"})

        mock_context.ports.prompt_service.get_system_prompt.assert_not_called()


# ---------------------------------------------------------------------------
# 4. handle() — success path
# ---------------------------------------------------------------------------


class TestHandleSuccess:
    @pytest.mark.parametrize(
        "cls, _cap_id, expected_role, expected_artifact",
        GENERIC_HANDLER_SPECS,
        ids=[c.__name__ for c, _, _, _ in GENERIC_HANDLER_SPECS],
    )
    async def test_returns_success(
        self, cls, _cap_id, expected_role, expected_artifact, mock_context
    ):
        h = cls()
        result = await h.handle(mock_context, {"prd": "Build a widget"})

        assert isinstance(result, HandlerResult)
        assert result.success is True
        assert result.outputs["role"] == expected_role

    @pytest.mark.parametrize(
        "cls, _cap_id, _role, expected_artifact",
        [s for s in PLANNING_HANDLER_SPECS if s[0] != GovernanceAssessReadinessHandler],
        ids=[
            c.__name__
            for c, _, _, _ in PLANNING_HANDLER_SPECS
            if c != GovernanceAssessReadinessHandler
        ],
    )
    async def test_planning_artifact_name(
        self, cls, _cap_id, _role, expected_artifact, mock_context
    ):
        h = cls()
        result = await h.handle(mock_context, {"prd": "Build a widget"})

        artifacts = result.outputs["artifacts"]
        assert len(artifacts) == 1
        assert artifacts[0]["name"] == expected_artifact
        assert artifacts[0]["content"] == "LLM planning output"
        assert artifacts[0]["media_type"] == "text/markdown"

    @pytest.mark.parametrize(
        "cls",
        ALL_HANDLER_CLASSES,
        ids=[c.__name__ for c in ALL_HANDLER_CLASSES],
    )
    async def test_evidence_present(self, cls, mock_context):
        h = cls()
        result = await h.handle(mock_context, {"prd": "Build a widget"})

        assert result._evidence is not None
        assert isinstance(result._evidence, HandlerEvidence)
        assert result.evidence.capability_id == h.capability_id


# ---------------------------------------------------------------------------
# 5. handle() — LLM failure
# ---------------------------------------------------------------------------


class TestHandleLLMError:
    @pytest.mark.parametrize(
        "cls",
        LLM_REACHABLE_CLASSES,
        ids=[c.__name__ for c in LLM_REACHABLE_CLASSES],
    )
    async def test_llm_error_returns_failure(self, cls):
        ctx = _make_context()
        ctx.ports.llm.chat.side_effect = LLMError("model overloaded")
        h = cls()
        result = await h.handle(ctx, {"prd": "Build a widget"})

        assert result.success is False
        assert "model overloaded" in result.error


# ---------------------------------------------------------------------------
# 6. handle() — prior_outputs in prompt
# ---------------------------------------------------------------------------


class TestHandlePriorOutputs:
    @pytest.mark.parametrize(
        "cls",
        [c for c in ALL_HANDLER_CLASSES if c != GovernanceIncorporateFeedbackHandler],
        ids=[c.__name__ for c in ALL_HANDLER_CLASSES if c != GovernanceIncorporateFeedbackHandler],
    )
    async def test_prior_outputs_included_in_prompt(self, cls, mock_context):
        h = cls()
        inputs = {
            "prd": "Build a widget",
            "prior_outputs": {
                "data": "Research context summary",
                "strat": "Objective frame summary",
            },
        }
        await h.handle(mock_context, inputs)

        call_args = mock_context.ports.llm.chat.call_args
        user_msg = call_args[0][0][1].content
        assert "Prior Analysis from Upstream Roles" in user_msg
        assert "Research context summary" in user_msg

    @pytest.mark.parametrize(
        "cls",
        [c for c in ALL_HANDLER_CLASSES if c != GovernanceIncorporateFeedbackHandler],
        ids=[c.__name__ for c in ALL_HANDLER_CLASSES if c != GovernanceIncorporateFeedbackHandler],
    )
    async def test_no_prior_outputs_omits_section(self, cls, mock_context):
        h = cls()
        await h.handle(mock_context, {"prd": "Build a widget"})

        call_args = mock_context.ports.llm.chat.call_args
        user_msg = call_args[0][0][1].content
        assert "Prior Analysis" not in user_msg


# ---------------------------------------------------------------------------
# 7. LLM call verification
# ---------------------------------------------------------------------------


class TestLLMCallVerification:
    @pytest.mark.parametrize(
        "cls",
        LLM_REACHABLE_CLASSES,
        ids=[c.__name__ for c in LLM_REACHABLE_CLASSES],
    )
    async def test_llm_chat_called_once(self, cls, mock_context):
        h = cls()
        await h.handle(mock_context, {"prd": "Build a widget"})
        mock_context.ports.llm.chat.assert_awaited_once()

    @pytest.mark.parametrize(
        "cls",
        LLM_REACHABLE_CLASSES,
        ids=[c.__name__ for c in LLM_REACHABLE_CLASSES],
    )
    async def test_user_message_contains_prd(self, cls, mock_context):
        h = cls()
        await h.handle(mock_context, {"prd": "Build a fancy widget"})

        call_args = mock_context.ports.llm.chat.call_args
        user_msg = call_args[0][0][1].content
        assert "Build a fancy widget" in user_msg


# ---------------------------------------------------------------------------
# 8. GovernanceIncorporateFeedbackHandler — custom prompt and dual artifacts
# ---------------------------------------------------------------------------


class TestGovernanceIncorporateFeedback:
    """Tests for GovernanceIncorporateFeedbackHandler custom behavior.

    All tests provide artifact_contents to satisfy D17 precondition.
    """

    def _inputs_with_artifact(self, **extra_prior):
        """Build inputs with required artifact_contents for D17."""
        prior_outputs = {
            "artifact_contents": {
                "planning_artifact.md": "Original planning content",
            },
        }
        prior_outputs.update(extra_prior)
        return {"prd": "Build a widget", "prior_outputs": prior_outputs}

    async def test_produces_two_artifacts(self, mock_context):
        h = GovernanceIncorporateFeedbackHandler()
        result = await h.handle(mock_context, self._inputs_with_artifact())

        assert result.success is True
        artifacts = result.outputs["artifacts"]
        assert len(artifacts) == 2
        assert artifacts[0]["name"] == "planning_artifact_revised.md"
        assert artifacts[1]["name"] == "plan_refinement.md"

    async def test_companion_artifact_differs_from_primary(self, mock_context):
        h = GovernanceIncorporateFeedbackHandler()
        result = await h.handle(mock_context, self._inputs_with_artifact())

        artifacts = result.outputs["artifacts"]
        assert artifacts[0]["content"] != artifacts[1]["content"]

    async def test_companion_has_original_plan_ref(self, mock_context):
        h = GovernanceIncorporateFeedbackHandler()
        inputs = self._inputs_with_artifact()
        inputs["resolved_config"] = {"plan_artifact_refs": ["artifact-ref-123"]}
        result = await h.handle(mock_context, inputs)

        companion = result.outputs["artifacts"][1]["content"]
        assert "artifact-ref-123" in companion

    async def test_companion_has_refinement_instructions(self, mock_context):
        h = GovernanceIncorporateFeedbackHandler()
        inputs = self._inputs_with_artifact(refinement_instructions="Clarify the auth boundary")
        result = await h.handle(mock_context, inputs)

        companion = result.outputs["artifacts"][1]["content"]
        assert "Clarify the auth boundary" in companion

    async def test_companion_has_frontmatter(self, mock_context):
        h = GovernanceIncorporateFeedbackHandler()
        result = await h.handle(mock_context, self._inputs_with_artifact())

        companion = result.outputs["artifacts"][1]["content"]
        assert companion.startswith("---\n")
        assert "original_plan_ref:" in companion
        assert "refinement_source:" in companion

    async def test_refinement_instructions_in_prompt(self, mock_context):
        h = GovernanceIncorporateFeedbackHandler()
        inputs = self._inputs_with_artifact(refinement_instructions="Clarify the auth boundary")
        await h.handle(mock_context, inputs)

        call_args = mock_context.ports.llm.chat.call_args
        user_msg = call_args[0][0][1].content
        assert "Refinement Instructions" in user_msg
        assert "Clarify the auth boundary" in user_msg

    async def test_artifact_contents_in_prompt(self, mock_context):
        h = GovernanceIncorporateFeedbackHandler()
        inputs = {
            "prd": "Build a widget",
            "prior_outputs": {
                "artifact_contents": {
                    "planning_artifact.md": "Original planning content here",
                },
            },
        }
        await h.handle(mock_context, inputs)

        call_args = mock_context.ports.llm.chat.call_args
        user_msg = call_args[0][0][1].content
        assert "Original Planning Artifact" in user_msg
        assert "Original planning content here" in user_msg


# ---------------------------------------------------------------------------
# 9. Bootstrap registration
# ---------------------------------------------------------------------------


class TestBootstrapRegistration:
    @pytest.mark.parametrize(
        "cls, _cap_id, expected_role, _artifact",
        ALL_HANDLER_SPECS,
        ids=[c.__name__ for c, _, _, _ in ALL_HANDLER_SPECS],
    )
    def test_handler_in_bootstrap(self, cls, _cap_id, expected_role, _artifact):
        registered = {entry[0]: entry[1] for entry in HANDLER_CONFIGS}
        assert cls in registered, f"{cls.__name__} not found in HANDLER_CONFIGS"
        assert (expected_role,) == registered[cls], (
            f"{cls.__name__} expected roles ({expected_role},), got {registered[cls]}"
        )

    def test_all_seven_planning_handlers_registered(self):
        registered_classes = {entry[0] for entry in HANDLER_CONFIGS}
        for cls in ALL_HANDLER_CLASSES:
            assert cls in registered_classes, f"{cls.__name__} missing from HANDLER_CONFIGS"


# ---------------------------------------------------------------------------
# 10. GovernanceAssessReadinessHandler — structural validation (Fix B)
# ---------------------------------------------------------------------------


class TestGovernanceAssessReadinessValidation:
    """Validate YAML frontmatter in planning artifact (readiness, sufficiency_score)."""

    async def test_valid_frontmatter_passes(self):
        ctx = _make_context(VALID_PLANNING_ARTIFACT)
        h = GovernanceAssessReadinessHandler()
        result = await h.handle(ctx, {"prd": "Build a widget"})

        assert result.success is True
        assert result.outputs["artifacts"][0]["name"] == "planning_artifact.md"

    async def test_missing_frontmatter_synthesizes_default(self):
        ctx = _make_context("No frontmatter here, just plain text.")
        h = GovernanceAssessReadinessHandler()
        result = await h.handle(ctx, {"prd": "Build a widget"})

        assert result.success is True
        content = result.outputs["artifacts"][0]["content"]
        assert content.startswith("---\n")
        assert "readiness: revise" in content

    async def test_invalid_yaml_fails(self):
        ctx = _make_context("---\n[invalid: yaml: content\n---\n\nBody")
        h = GovernanceAssessReadinessHandler()
        result = await h.handle(ctx, {"prd": "Build a widget"})

        assert result.success is False
        assert "invalid YAML" in result.error

    async def test_missing_readiness_defaults_to_revise(self):
        content = "---\nsufficiency_score: 3\nblocker_unknowns: 0\n---\n\nBody"
        ctx = _make_context(content)
        h = GovernanceAssessReadinessHandler()
        result = await h.handle(ctx, {"prd": "Build a widget"})

        assert result.success is True

    async def test_invalid_readiness_value_defaults_to_revise(self):
        content = "---\nreadiness: maybe\nsufficiency_score: 3\n---\n\nBody"
        ctx = _make_context(content)
        h = GovernanceAssessReadinessHandler()
        result = await h.handle(ctx, {"prd": "Build a widget"})

        assert result.success is True

    async def test_missing_sufficiency_score_defaults_to_3(self):
        content = "---\nreadiness: go\nblocker_unknowns: 0\n---\n\nBody"
        ctx = _make_context(content)
        h = GovernanceAssessReadinessHandler()
        result = await h.handle(ctx, {"prd": "Build a widget"})

        assert result.success is True

    async def test_non_integer_sufficiency_score_defaults_to_3(self):
        content = "---\nreadiness: go\nsufficiency_score: high\n---\n\nBody"
        ctx = _make_context(content)
        h = GovernanceAssessReadinessHandler()
        result = await h.handle(ctx, {"prd": "Build a widget"})

        assert result.success is True

    async def test_sufficiency_score_out_of_range_defaults_to_3(self):
        content = "---\nreadiness: go\nsufficiency_score: 7\n---\n\nBody"
        ctx = _make_context(content)
        h = GovernanceAssessReadinessHandler()
        result = await h.handle(ctx, {"prd": "Build a widget"})

        assert result.success is True

    async def test_sufficiency_score_zero_valid(self):
        content = "---\nreadiness: no-go\nsufficiency_score: 0\n---\n\nBody"
        ctx = _make_context(content)
        h = GovernanceAssessReadinessHandler()
        result = await h.handle(ctx, {"prd": "Build a widget"})

        assert result.success is True

    @pytest.mark.parametrize("readiness", ["go", "revise", "no-go"])
    async def test_all_valid_readiness_values(self, readiness):
        content = f"---\nreadiness: {readiness}\nsufficiency_score: 3\n---\n\nBody"
        ctx = _make_context(content)
        h = GovernanceAssessReadinessHandler()
        result = await h.handle(ctx, {"prd": "Build a widget"})

        assert result.success is True

    async def test_evidence_preserved_on_frontmatter_synthesis(self):
        ctx = _make_context("No frontmatter")
        h = GovernanceAssessReadinessHandler()
        result = await h.handle(ctx, {"prd": "Build a widget"})

        assert result.success is True
        assert result._evidence is not None
        assert result._evidence.capability_id == "governance.assess_readiness"


# ---------------------------------------------------------------------------
# 11. D17 artifact content validation (Fix E)
# ---------------------------------------------------------------------------


class TestD17ArtifactContentValidation:
    """GovernanceIncorporateFeedbackHandler fails fast on missing/empty artifact content."""

    async def test_no_prior_outputs_fails(self):
        ctx = _make_context()
        h = GovernanceIncorporateFeedbackHandler()
        result = await h.handle(ctx, {"prd": "Build a widget"})

        assert result.success is False
        assert "D17" in result.error

    async def test_empty_artifact_contents_fails(self):
        ctx = _make_context()
        h = GovernanceIncorporateFeedbackHandler()
        inputs = {
            "prd": "Build a widget",
            "prior_outputs": {"artifact_contents": {}},
        }
        result = await h.handle(ctx, inputs)

        assert result.success is False
        assert "D17" in result.error

    async def test_blank_artifact_content_fails(self):
        ctx = _make_context()
        h = GovernanceIncorporateFeedbackHandler()
        inputs = {
            "prd": "Build a widget",
            "prior_outputs": {
                "artifact_contents": {"planning_artifact.md": "   "},
            },
        }
        result = await h.handle(ctx, inputs)

        assert result.success is False
        assert "D17" in result.error

    async def test_valid_artifact_content_proceeds(self):
        ctx = _make_context()
        h = GovernanceIncorporateFeedbackHandler()
        inputs = {
            "prd": "Build a widget",
            "prior_outputs": {
                "artifact_contents": {
                    "planning_artifact.md": "Real planning content",
                },
            },
        }
        result = await h.handle(ctx, inputs)

        assert result.success is True

    async def test_evidence_on_d17_failure(self):
        ctx = _make_context()
        h = GovernanceIncorporateFeedbackHandler()
        result = await h.handle(ctx, {"prd": "Build a widget"})

        assert result.success is False
        assert result._evidence is not None
        assert result._evidence.capability_id == "governance.incorporate_feedback"

    async def test_llm_not_called_on_d17_failure(self):
        ctx = _make_context()
        h = GovernanceIncorporateFeedbackHandler()
        await h.handle(ctx, {"prd": "Build a widget"})

        ctx.ports.llm.chat.assert_not_awaited()


# ---------------------------------------------------------------------------
# 12. Time budget awareness (SIP-0082)
# ---------------------------------------------------------------------------


class TestFormatTimeBudget:
    @pytest.mark.parametrize(
        "seconds, expected",
        [
            (1, "1 second"),
            (45, "45 seconds"),
            (60, "1 minute"),
            (1800, "30 minutes"),
            (3600, "1 hour"),
            (5400, "1 hour 30 minutes"),
            (7200, "2 hours"),
        ],
        ids=["1s", "45s", "1min", "30min", "1h", "1h30m", "2h"],
    )
    def test_format(self, seconds, expected):
        assert _format_time_budget(seconds) == expected


class TestBuildTimeBudgetSection:
    @pytest.mark.parametrize(
        "value",
        [None, 0, -100],
        ids=["none", "zero", "negative"],
    )
    def test_no_section_for_non_positive(self, value):
        assert _build_time_budget_section(value) == ""

    def test_positive_budget_produces_section(self):
        result = _build_time_budget_section(7200)
        assert "## Time Budget" in result
        assert "2 hours" in result
        assert "defer" in result

    @pytest.mark.parametrize(
        "value",
        [None, 0, -100],
        ids=["none", "zero", "negative"],
    )
    def test_refinement_no_section_for_non_positive(self, value):
        assert _build_refinement_time_budget_section(value) == ""

    def test_refinement_positive_budget_produces_section(self):
        result = _build_refinement_time_budget_section(1800)
        assert "## Time Budget" in result
        assert "30 minutes" in result
        assert "Preserve budget realism" in result


class TestTimeBudgetAwareness:
    """Verify time budget injection in real handle() calls across all handlers."""

    @pytest.mark.parametrize(
        "cls",
        [c for c in ALL_HANDLER_CLASSES if c != GovernanceIncorporateFeedbackHandler],
        ids=[c.__name__ for c in ALL_HANDLER_CLASSES if c != GovernanceIncorporateFeedbackHandler],
    )
    async def test_budget_injected_when_present(self, cls):
        ctx = _make_context()
        h = cls()
        inputs = {
            "prd": "Build a widget",
            "resolved_config": {"time_budget_seconds": 7200},
        }
        await h.handle(ctx, inputs)

        call_args = ctx.ports.llm.chat.call_args
        user_msg = call_args[0][0][1].content
        assert "Time Budget" in user_msg
        assert "2 hours" in user_msg

    async def test_budget_injected_in_refinement_handler(self):
        ctx = _make_context()
        h = GovernanceIncorporateFeedbackHandler()
        inputs = {
            "prd": "Build a widget",
            "resolved_config": {"time_budget_seconds": 1800},
            "prior_outputs": {
                "artifact_contents": {
                    "planning_artifact.md": "Original planning content",
                },
            },
        }
        await h.handle(ctx, inputs)

        call_args = ctx.ports.llm.chat.call_args
        user_msg = call_args[0][0][1].content
        assert "Time Budget" in user_msg
        assert "30 minutes" in user_msg
        assert "Preserve budget realism" in user_msg

    @pytest.mark.parametrize(
        "cls",
        [c for c in ALL_HANDLER_CLASSES if c != GovernanceIncorporateFeedbackHandler],
        ids=[c.__name__ for c in ALL_HANDLER_CLASSES if c != GovernanceIncorporateFeedbackHandler],
    )
    async def test_no_budget_section_when_absent(self, cls):
        ctx = _make_context()
        h = cls()
        await h.handle(ctx, {"prd": "Build a widget"})

        call_args = ctx.ports.llm.chat.call_args
        user_msg = call_args[0][0][1].content
        assert "Time Budget" not in user_msg

    async def test_no_budget_section_when_zero(self):
        ctx = _make_context()
        h = DataResearchContextHandler()
        inputs = {
            "prd": "Build a widget",
            "resolved_config": {"time_budget_seconds": 0},
        }
        await h.handle(ctx, inputs)

        call_args = ctx.ports.llm.chat.call_args
        user_msg = call_args[0][0][1].content
        assert "Time Budget" not in user_msg

    async def test_no_budget_section_when_none(self):
        ctx = _make_context()
        h = DataResearchContextHandler()
        inputs = {
            "prd": "Build a widget",
            "resolved_config": {"time_budget_seconds": None},
        }
        await h.handle(ctx, inputs)

        call_args = ctx.ports.llm.chat.call_args
        user_msg = call_args[0][0][1].content
        assert "Time Budget" not in user_msg

    async def test_budget_coerced_from_string(self):
        """CLI --set flags pass values as strings; handle() must coerce to int."""
        ctx = _make_context()
        h = DataResearchContextHandler()
        inputs = {
            "prd": "Build a widget",
            "resolved_config": {"time_budget_seconds": "1800"},
        }
        await h.handle(ctx, inputs)

        call_args = ctx.ports.llm.chat.call_args
        user_msg = call_args[0][0][1].content
        assert "Time Budget" in user_msg
        assert "30 minutes" in user_msg
