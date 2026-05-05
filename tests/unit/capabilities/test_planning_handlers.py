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
    GovernanceIncorporateFeedbackHandler,
    GovernanceReviewPlanHandler,
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
        GovernanceReviewPlanHandler,
        "governance.review_plan",
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
# GovernanceReviewPlanHandler requires valid YAML frontmatter in LLM response.
# GovernanceIncorporateFeedbackHandler requires artifact_contents in prior_outputs (D17).
_SPECIAL_HANDLERS = (GovernanceReviewPlanHandler, GovernanceIncorporateFeedbackHandler)
GENERIC_HANDLER_SPECS = [s for s in ALL_HANDLER_SPECS if s[0] not in _SPECIAL_HANDLERS]
GENERIC_HANDLER_CLASSES = [cls for cls, _, _, _ in GENERIC_HANDLER_SPECS]
# Handlers where LLM is always reached (GovernanceIncorporateFeedbackHandler may
# short-circuit at D17 before calling LLM).
LLM_REACHABLE_SPECS = [s for s in ALL_HANDLER_SPECS if s[0] != GovernanceIncorporateFeedbackHandler]
LLM_REACHABLE_CLASSES = [cls for cls, _, _, _ in LLM_REACHABLE_SPECS]
# Issue #109: GovernanceReviewPlanHandler now retries the LLM call once when
# the response omits YAML frontmatter, so single-call assertions fail under
# the generic mock content. Exclude it from those parametrized checks; it
# has dedicated tests under TestGovernanceAssessReadinessValidation.
LLM_SINGLE_CALL_SPECS = [s for s in LLM_REACHABLE_SPECS if s[0] is not GovernanceReviewPlanHandler]
LLM_SINGLE_CALL_CLASSES = [cls for cls, _, _, _ in LLM_SINGLE_CALL_SPECS]

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


def _make_context(
    llm_response="LLM planning output",
    project_id: str = "test_proj",
    cycle_id: str = "test_cyc",
):
    """Build a minimal ExecutionContext mock for planning handler tests."""
    llm = AsyncMock()
    llm.chat.return_value = MagicMock(content=llm_response)
    llm.chat_stream_with_usage.return_value = MagicMock(content=llm_response)
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
    ports.request_renderer = None

    ctx = MagicMock()
    ctx.ports = ports
    ctx.correlation_context = None
    # Issue #109: cycle_id / project_id need to be real strings so the
    # manifest identifier rewrite can substitute them; MagicMock auto-attrs
    # would stringify to <MagicMock ...> and corrupt the YAML.
    ctx.project_id = project_id
    ctx.cycle_id = cycle_id
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
        LLM_SINGLE_CALL_SPECS,
        ids=[c.__name__ for c, _, _, _ in LLM_SINGLE_CALL_SPECS],
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
        [s for s in PLANNING_HANDLER_SPECS if s[0] != GovernanceReviewPlanHandler],
        ids=[
            c.__name__ for c, _, _, _ in PLANNING_HANDLER_SPECS if c != GovernanceReviewPlanHandler
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
        ctx.ports.llm.chat_stream_with_usage.side_effect = LLMError("model overloaded")
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

        call_args = mock_context.ports.llm.chat_stream_with_usage.call_args
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

        call_args = mock_context.ports.llm.chat_stream_with_usage.call_args
        user_msg = call_args[0][0][1].content
        assert "Prior Analysis" not in user_msg


# ---------------------------------------------------------------------------
# 7. LLM call verification
# ---------------------------------------------------------------------------


class TestLLMCallVerification:
    @pytest.mark.parametrize(
        "cls",
        LLM_SINGLE_CALL_CLASSES,
        ids=[c.__name__ for c in LLM_SINGLE_CALL_CLASSES],
    )
    async def test_llm_chat_called_once(self, cls, mock_context):
        h = cls()
        await h.handle(mock_context, {"prd": "Build a widget"})
        mock_context.ports.llm.chat_stream_with_usage.assert_awaited_once()

    @pytest.mark.parametrize(
        "cls",
        LLM_REACHABLE_CLASSES,
        ids=[c.__name__ for c in LLM_REACHABLE_CLASSES],
    )
    async def test_user_message_contains_prd(self, cls, mock_context):
        h = cls()
        await h.handle(mock_context, {"prd": "Build a fancy widget"})

        call_args = mock_context.ports.llm.chat_stream_with_usage.call_args
        user_msg = call_args[0][0][1].content
        assert "Build a fancy widget" in user_msg


# ---------------------------------------------------------------------------
# Issue #112 (real fix): PRD-coverage discipline must be wired into the
# framing-time manifest prompt — the LLM call inside _produce_plan,
# which is the actual prompt that produces implementation_plan.yaml.
# Cycle 5 (cyc_7febd710e565) proved that patching only
# cycle_tasks.py:_MANIFEST_PROMPT_EXTENSION leaves this prompt untouched.
# ---------------------------------------------------------------------------


class TestPRDCoverageDisciplineReachesManifestPrompt:
    _MANIFEST_BLOCK = (
        "```yaml:implementation_plan.yaml\n"
        "version: 1\n"
        "project_id: test\n"
        "cycle_id: cyc_test\n"
        "prd_hash: abc\n"
        "tasks:\n"
        "  - task_index: 0\n"
        "    task_type: development.develop\n"
        "    role: dev\n"
        '    focus: "f"\n'
        '    description: "d"\n'
        '    expected_artifacts: ["x.py"]\n'
        "    acceptance_criteria: []\n"
        "    depends_on: []\n"
        "  - task_index: 1\n"
        "    task_type: development.develop\n"
        "    role: dev\n"
        '    focus: "f"\n'
        '    description: "d"\n'
        '    expected_artifacts: ["y.py"]\n'
        "    acceptance_criteria: []\n"
        "    depends_on: [0]\n"
        "  - task_index: 2\n"
        "    task_type: qa.test\n"
        "    role: qa\n"
        '    focus: "f"\n'
        '    description: "d"\n'
        '    expected_artifacts: ["z.py"]\n'
        "    acceptance_criteria: []\n"
        "    depends_on: [0, 1]\n"
        "summary:\n"
        "  total_dev_tasks: 2\n"
        "  total_qa_tasks: 1\n"
        "  total_tasks: 3\n"
        "  estimated_layers: [a]\n"
        "```\n"
    )

    def test_planning_tasks_imports_shared_constant(self):
        """Defense against a future refactor that drops the import."""
        from squadops.capabilities.handlers import planning_tasks

        assert hasattr(planning_tasks, "_PRD_COVERAGE_DISCIPLINE_SECTION"), (
            "planning_tasks must import _PRD_COVERAGE_DISCIPLINE_SECTION — without "
            "it the framing-time manifest prompt loses PRD-coverage discipline and "
            "regresses to the cycle-5 defect (cyc_7febd710e565)"
        )

    async def test_manifest_prompt_includes_coverage_discipline(self):
        """End-to-end: when GovernanceReviewPlanHandler runs with
        implementation_plan enabled, the SECOND LLM call (the manifest
        producer) must include the discipline text. The first call
        (planning artifact) does not."""
        ctx = _make_context()
        # Two responses: first is planning artifact, second is the manifest.
        ctx.ports.llm.chat_stream_with_usage.side_effect = [
            MagicMock(content=VALID_PLANNING_ARTIFACT),
            MagicMock(content=self._MANIFEST_BLOCK),
        ]

        h = GovernanceReviewPlanHandler()
        await h.handle(
            ctx,
            {
                "prd": "Build app. qa_handoff.md must contain ## Expected Behavior.",
                "resolved_config": {"implementation_plan": True},
                "profile_roles": ["lead", "dev", "qa"],
            },
        )

        calls = ctx.ports.llm.chat_stream_with_usage.call_args_list
        assert len(calls) == 2, f"expected 2 LLM calls, got {len(calls)}"

        # First call = planning artifact prompt; should NOT mention coverage discipline
        first_user = calls[0][0][0][1].content
        assert "PRD Coverage Discipline" not in first_user

        # Second call = manifest prompt; MUST mention coverage discipline
        second_user = calls[1][0][0][1].content
        assert "PRD Coverage Discipline" in second_user, (
            "manifest prompt missing PRD coverage discipline — issue #112 regression"
        )
        # And the worked example case the discipline cites — pinning the
        # specific defect class so a future prompt rewrite that strips
        # the qa_handoff example fails loudly.
        assert "## Expected Behavior" in second_user
        assert "qa_handoff.md" in second_user

    async def test_manifest_prompt_omits_discipline_when_implementation_plan_disabled(self):
        """Defensive: when implementation_plan is off, _produce_plan
        is not called — only one LLM call (planning artifact), and the
        discipline text shouldn't appear (it would be misleading without
        a manifest to author)."""
        ctx = _make_context(llm_response=VALID_PLANNING_ARTIFACT)

        h = GovernanceReviewPlanHandler()
        await h.handle(
            ctx,
            {
                "prd": "Build app",
                "resolved_config": {"implementation_plan": False},
                "profile_roles": ["lead", "dev", "qa"],
            },
        )

        calls = ctx.ports.llm.chat_stream_with_usage.call_args_list
        assert len(calls) == 1
        user_msg = calls[0][0][0][1].content
        assert "PRD Coverage Discipline" not in user_msg


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

        call_args = mock_context.ports.llm.chat_stream_with_usage.call_args
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

        call_args = mock_context.ports.llm.chat_stream_with_usage.call_args
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
# 10. GovernanceReviewPlanHandler — structural validation (Fix B)
# ---------------------------------------------------------------------------


class TestGovernanceAssessReadinessValidation:
    """Validate YAML frontmatter in planning artifact (readiness, sufficiency_score)."""

    async def test_valid_frontmatter_passes(self):
        ctx = _make_context(VALID_PLANNING_ARTIFACT)
        h = GovernanceReviewPlanHandler()
        result = await h.handle(ctx, {"prd": "Build a widget"})

        assert result.success is True
        assert result.outputs["artifacts"][0]["name"] == "planning_artifact.md"

    async def test_missing_frontmatter_retries_then_fails(self):
        """Issue #109: silent default-synthesis used to mask Max's omission.

        New contract: the handler retries Max once with a corrective
        instruction; if the retry still omits frontmatter, the task fails
        so the cycle's correction loop can fire instead of papering over
        a defaulted readiness/sufficiency_score that Max never authored.
        """
        ctx = _make_context("No frontmatter here, just plain text.")
        h = GovernanceReviewPlanHandler()
        result = await h.handle(ctx, {"prd": "Build a widget"})

        assert result.success is False
        assert "frontmatter" in result.error.lower()
        # Both LLM call and retry call should have happened.
        assert ctx.ports.llm.chat_stream_with_usage.await_count == 2

    async def test_missing_frontmatter_retry_recovers_when_llm_complies(self):
        """Retry succeeds → handler proceeds with the recovered content."""
        recovered = "---\nreadiness: go\nsufficiency_score: 4\n---\n\n## Body\n"
        ctx = _make_context()
        # First call returns no-frontmatter; retry returns valid frontmatter.
        ctx.ports.llm.chat_stream_with_usage.side_effect = [
            MagicMock(content="No frontmatter on first response"),
            MagicMock(content=recovered),
        ]
        h = GovernanceReviewPlanHandler()
        result = await h.handle(ctx, {"prd": "Build a widget"})

        assert result.success is True
        content = result.outputs["artifacts"][0]["content"]
        assert content.startswith("---\n")
        assert "readiness: go" in content
        assert ctx.ports.llm.chat_stream_with_usage.await_count == 2

    async def test_retry_corrective_message_targets_frontmatter(self):
        """The retry's corrective message must call out the missing
        frontmatter explicitly so Max can fix the specific gap rather
        than re-running the whole prompt blind."""
        ctx = _make_context("No frontmatter on first response either")
        h = GovernanceReviewPlanHandler()
        await h.handle(ctx, {"prd": "Build a widget"})

        # Inspect the second LLM call's messages for the corrective text.
        calls = ctx.ports.llm.chat_stream_with_usage.await_args_list
        assert len(calls) == 2
        retry_messages = calls[1].args[0]
        assert any("YAML frontmatter" in m.content for m in retry_messages if m.role == "user")
        # And it must include the prior failed assistant turn so Max sees
        # what came back wrong.
        assert any(m.role == "assistant" for m in retry_messages)

    async def test_invalid_yaml_fails(self):
        ctx = _make_context("---\n[invalid: yaml: content\n---\n\nBody")
        h = GovernanceReviewPlanHandler()
        result = await h.handle(ctx, {"prd": "Build a widget"})

        assert result.success is False
        assert "invalid YAML" in result.error

    async def test_missing_readiness_defaults_to_revise(self):
        content = "---\nsufficiency_score: 3\nblocker_unknowns: 0\n---\n\nBody"
        ctx = _make_context(content)
        h = GovernanceReviewPlanHandler()
        result = await h.handle(ctx, {"prd": "Build a widget"})

        assert result.success is True

    async def test_invalid_readiness_value_defaults_to_revise(self):
        content = "---\nreadiness: maybe\nsufficiency_score: 3\n---\n\nBody"
        ctx = _make_context(content)
        h = GovernanceReviewPlanHandler()
        result = await h.handle(ctx, {"prd": "Build a widget"})

        assert result.success is True

    async def test_missing_sufficiency_score_defaults_to_3(self):
        content = "---\nreadiness: go\nblocker_unknowns: 0\n---\n\nBody"
        ctx = _make_context(content)
        h = GovernanceReviewPlanHandler()
        result = await h.handle(ctx, {"prd": "Build a widget"})

        assert result.success is True

    async def test_non_integer_sufficiency_score_defaults_to_3(self):
        content = "---\nreadiness: go\nsufficiency_score: high\n---\n\nBody"
        ctx = _make_context(content)
        h = GovernanceReviewPlanHandler()
        result = await h.handle(ctx, {"prd": "Build a widget"})

        assert result.success is True

    async def test_sufficiency_score_out_of_range_defaults_to_3(self):
        content = "---\nreadiness: go\nsufficiency_score: 7\n---\n\nBody"
        ctx = _make_context(content)
        h = GovernanceReviewPlanHandler()
        result = await h.handle(ctx, {"prd": "Build a widget"})

        assert result.success is True

    async def test_sufficiency_score_zero_valid(self):
        content = "---\nreadiness: no-go\nsufficiency_score: 0\n---\n\nBody"
        ctx = _make_context(content)
        h = GovernanceReviewPlanHandler()
        result = await h.handle(ctx, {"prd": "Build a widget"})

        assert result.success is True

    @pytest.mark.parametrize("readiness", ["go", "revise", "no-go"])
    async def test_all_valid_readiness_values(self, readiness):
        content = f"---\nreadiness: {readiness}\nsufficiency_score: 3\n---\n\nBody"
        ctx = _make_context(content)
        h = GovernanceReviewPlanHandler()
        result = await h.handle(ctx, {"prd": "Build a widget"})

        assert result.success is True

    async def test_evidence_preserved_when_frontmatter_retry_fails(self):
        """Issue #109: even when the retry can't recover, the evidence
        from the first LLM call must travel with the failure result so
        triage can attribute the failure to the right capability."""
        ctx = _make_context("No frontmatter")
        h = GovernanceReviewPlanHandler()
        result = await h.handle(ctx, {"prd": "Build a widget"})

        assert result.success is False
        assert result._evidence is not None
        assert result._evidence.capability_id == "governance.review_plan"


# ---------------------------------------------------------------------------
# 10b. _produce_plan retry-on-error (SIP-0086 robustness)
# ---------------------------------------------------------------------------


_VALID_MANIFEST_YAML = """\
```yaml:implementation_plan.yaml
version: 1
project_id: test_proj
cycle_id: test_cyc
prd_hash: abc
tasks:
  - task_index: 0
    task_type: development.develop
    role: dev
    focus: "Backend"
    description: |
      Build backend
    expected_artifacts:
      - "backend/app.py"
    acceptance_criteria:
      - "Backend runs"
    depends_on: []
  - task_index: 1
    task_type: development.develop
    role: dev
    focus: "Frontend"
    description: |
      Build frontend
    expected_artifacts:
      - "frontend/app.js"
    acceptance_criteria:
      - "Frontend renders"
    depends_on: [0]
  - task_index: 2
    task_type: qa.test
    role: qa
    focus: "Tests"
    description: |
      Add tests
    expected_artifacts:
      - "tests/test_app.py"
    acceptance_criteria:
      - "Tests pass"
    depends_on: [0, 1]
summary:
  total_dev_tasks: 2
  total_qa_tasks: 1
  total_tasks: 3
  estimated_layers: [backend, frontend, test]
```
"""

_MALFORMED_MANIFEST_YAML = """\
```yaml:implementation_plan.yaml
version: 1
project_id: test_proj
cycle_id: test_cyc
prd_hash: abc
tasks:
  - task_index: 0
    task_type: development.develop
    role: dev
    focus: "Backend"
    description: |
      Build backend
    expected_artifacts:
      - "backend/app.py" (the main app file)
      - "backend/models.py"
    depends_on: []
summary:
  total_dev_tasks: 1
  total_qa_tasks: 0
  total_tasks: 1
```
"""


class TestProduceManifestIdentifierRewrite:
    """Issue #109: framing-time _produce_plan must overwrite fabricated
    project_id / cycle_id / prd_hash with the cycle's authoritative
    values, and pre-fill the prompt with the same so Max doesn't have
    to invent them."""

    async def _call(self, ctx, prd: str = "Build a widget") -> dict | None:
        h = GovernanceReviewPlanHandler()
        return await h._produce_plan(
            ctx,
            inputs={"prd": prd},
            planning_content="plan",
            resolved_config={},
        )

    async def test_rewrites_fabricated_identifiers(self):
        import hashlib

        fabricated = (
            _VALID_MANIFEST_YAML.replace("project_id: test_proj", "project_id: group_run_mvp")
            .replace("cycle_id: test_cyc", "cycle_id: cycle_v03")
            .replace("prd_hash: abc", "prd_hash: a1b2c3d4e5f6")
        )
        ctx = _make_context(fabricated, project_id="group_run", cycle_id="cyc_real")

        result = await self._call(ctx, prd="Build a widget")

        assert result is not None
        manifest_yaml = result["content"]
        expected_hash = hashlib.sha256(b"Build a widget").hexdigest()
        assert "project_id: group_run\n" in manifest_yaml
        assert "cycle_id: cyc_real\n" in manifest_yaml
        assert f"prd_hash: {expected_hash}\n" in manifest_yaml
        assert "group_run_mvp" not in manifest_yaml
        assert "cycle_v03" not in manifest_yaml

    async def test_prompt_pre_fills_authoritative_identifiers(self):
        """The manifest prompt sent to Max must contain real values, not
        the literal `<project_id>` / `<cycle_id>` / `<hash>` placeholders
        that triggered fabrication in the first place."""
        import hashlib

        ctx = _make_context(_VALID_MANIFEST_YAML, project_id="group_run", cycle_id="cyc_real")

        await self._call(ctx, prd="Build a widget")

        sent = ctx.ports.llm.chat_stream_with_usage.call_args.args[0]
        user_prompt = next(m for m in sent if m.role == "user").content
        expected_hash = hashlib.sha256(b"Build a widget").hexdigest()
        assert "project_id: group_run\n" in user_prompt
        assert "cycle_id: cyc_real\n" in user_prompt
        assert f"prd_hash: {expected_hash}\n" in user_prompt
        assert "<project_id>" not in user_prompt
        assert "<cycle_id>" not in user_prompt
        assert "<hash>" not in user_prompt


class TestProduceManifestRetry:
    """SIP-0086 robustness: retry LLM once with error feedback before fallback."""

    async def _call_produce(
        self,
        ctx,
        resolved_config: dict | None = None,
        profile_roles: list[str] | None = None,
    ) -> dict | None:
        h = GovernanceReviewPlanHandler()
        inputs: dict = {"prd": "Build a widget"}
        if profile_roles is not None:
            inputs["profile_roles"] = profile_roles
        return await h._produce_plan(
            ctx,
            inputs=inputs,
            planning_content="plan",
            resolved_config=resolved_config or {},
        )

    async def test_valid_manifest_on_first_attempt_no_retry(self):
        ctx = _make_context(_VALID_MANIFEST_YAML)
        result = await self._call_produce(ctx)

        assert result is not None
        assert result["name"] == "implementation_plan.yaml"
        assert result["type"] == "control_implementation_plan"
        assert ctx.ports.llm.chat_stream_with_usage.await_count == 1

    async def test_malformed_yaml_retries_then_succeeds(self):
        """First call returns bad YAML, second returns valid — manifest is produced."""
        ctx = _make_context()
        ctx.ports.llm.chat_stream_with_usage.side_effect = [
            MagicMock(content=_MALFORMED_MANIFEST_YAML),
            MagicMock(content=_VALID_MANIFEST_YAML),
        ]
        result = await self._call_produce(ctx)

        assert result is not None
        assert result["name"] == "implementation_plan.yaml"
        assert ctx.ports.llm.chat_stream_with_usage.await_count == 2

    async def test_retry_prompt_includes_parse_error(self):
        """Second LLM call must be given the specific error so it can correct."""
        ctx = _make_context()
        ctx.ports.llm.chat_stream_with_usage.side_effect = [
            MagicMock(content=_MALFORMED_MANIFEST_YAML),
            MagicMock(content=_VALID_MANIFEST_YAML),
        ]
        await self._call_produce(ctx)

        second_call_messages = ctx.ports.llm.chat_stream_with_usage.await_args_list[1].args[0]
        retry_user_msg = second_call_messages[-1].content
        assert "failed validation" in retry_user_msg
        assert "parenthetical" in retry_user_msg or "Quote every file path" in retry_user_msg

    async def test_both_attempts_fail_returns_none(self):
        """Two malformed responses → fall back to static steps (None)."""
        ctx = _make_context()
        ctx.ports.llm.chat_stream_with_usage.side_effect = [
            MagicMock(content=_MALFORMED_MANIFEST_YAML),
            MagicMock(content=_MALFORMED_MANIFEST_YAML),
        ]
        result = await self._call_produce(ctx)

        assert result is None
        assert ctx.ports.llm.chat_stream_with_usage.await_count == 2

    async def test_out_of_bounds_retries_with_specific_error(self):
        """Manifest with too few subtasks triggers retry with bounds feedback."""
        ctx = _make_context()
        ctx.ports.llm.chat_stream_with_usage.side_effect = [
            MagicMock(content=_VALID_MANIFEST_YAML),  # has 3 tasks
            MagicMock(content=_VALID_MANIFEST_YAML),
        ]
        # Set min to 5 so the 3-task manifest is out of bounds
        await self._call_produce(ctx, resolved_config={"min_build_subtasks": 5})

        second_call_messages = ctx.ports.llm.chat_stream_with_usage.await_args_list[1].args[0]
        retry_user_msg = second_call_messages[-1].content
        assert "3 subtasks" in retry_user_msg
        assert "5" in retry_user_msg  # min bound echoed

    async def test_max_attempts_configurable(self):
        """manifest_max_attempts=1 disables retry; first failure returns None."""
        ctx = _make_context(_MALFORMED_MANIFEST_YAML)
        result = await self._call_produce(ctx, resolved_config={"manifest_max_attempts": 1})

        assert result is None
        assert ctx.ports.llm.chat_stream_with_usage.await_count == 1

    async def test_profile_roles_injected_into_prompt(self):
        """profile_roles from inputs appear in the user prompt so the LLM is constrained."""
        ctx = _make_context(_VALID_MANIFEST_YAML)
        await self._call_produce(ctx, profile_roles=["dev", "qa", "lead"])

        messages = ctx.ports.llm.chat_stream_with_usage.await_args_list[0].args[0]
        user_prompt = messages[1].content
        assert "Available roles" in user_prompt
        assert "dev" in user_prompt and "qa" in user_prompt and "lead" in user_prompt

    async def test_allowed_task_types_injected_into_prompt(self):
        """Known build task_types appear in the prompt so the LLM doesn't invent them."""
        ctx = _make_context(_VALID_MANIFEST_YAML)
        await self._call_produce(ctx)

        messages = ctx.ports.llm.chat_stream_with_usage.await_args_list[0].args[0]
        user_prompt = messages[1].content
        assert "Available task_types" in user_prompt
        assert "development.develop" in user_prompt
        assert "qa.test" in user_prompt
        assert "builder.assemble" in user_prompt

    async def test_invented_role_triggers_retry_with_role_list(self):
        """Manifest with role outside profile_roles must retry with a specific error."""
        # _VALID_MANIFEST_YAML uses roles "dev" and "qa" — pass profile_roles
        # that EXCLUDE them to simulate an invented-role scenario.
        ctx = _make_context()
        ctx.ports.llm.chat_stream_with_usage.side_effect = [
            MagicMock(content=_VALID_MANIFEST_YAML),
            MagicMock(content=_VALID_MANIFEST_YAML),
        ]
        await self._call_produce(ctx, profile_roles=["lead", "builder"])

        second_messages = ctx.ports.llm.chat_stream_with_usage.await_args_list[1].args[0]
        retry_msg = second_messages[-1].content
        assert "not in the squad profile" in retry_msg
        assert "dev" in retry_msg or "qa" in retry_msg  # bad role echoed

    async def test_valid_roles_pass_without_retry(self):
        """Roles matching profile_roles produce manifest on first attempt."""
        ctx = _make_context(_VALID_MANIFEST_YAML)
        result = await self._call_produce(ctx, profile_roles=["dev", "qa"])

        assert result is not None
        assert ctx.ports.llm.chat_stream_with_usage.await_count == 1

    async def test_builder_guidance_added_when_builder_role_present(self):
        """When profile includes builder, prompt directs Max to use builder.assemble."""
        ctx = _make_context(_VALID_MANIFEST_YAML)
        await self._call_produce(ctx, profile_roles=["dev", "qa", "lead", "builder"])

        user_prompt = ctx.ports.llm.chat_stream_with_usage.await_args_list[0].args[0][1].content
        assert "`builder.assemble`" in user_prompt
        assert "AFTER all `development.develop`" in user_prompt
        assert "BEFORE any `qa.test`" in user_prompt
        # Example template includes a builder.assemble row
        assert "task_type: builder.assemble" in user_prompt
        assert "role: builder" in user_prompt
        # Summary template includes total_builder_tasks
        assert "total_builder_tasks: P" in user_prompt
        assert "total_tasks: N+M+P" in user_prompt
        # "Put QA handoff last" is removed since builder owns handoff now
        assert "Put QA handoff last" not in user_prompt

    async def test_builder_guidance_absent_when_builder_role_missing(self):
        """Squads without a builder role get the legacy QA-handoff-last guideline."""
        ctx = _make_context(_VALID_MANIFEST_YAML)
        await self._call_produce(ctx, profile_roles=["dev", "qa", "lead"])

        user_prompt = ctx.ports.llm.chat_stream_with_usage.await_args_list[0].args[0][1].content
        assert "task_type: builder.assemble" not in user_prompt
        assert "total_builder_tasks" not in user_prompt
        assert "total_tasks: N+M" in user_prompt
        assert "Put QA handoff last" in user_prompt


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

        ctx.ports.llm.chat_stream_with_usage.assert_not_awaited()


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

        call_args = ctx.ports.llm.chat_stream_with_usage.call_args
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

        call_args = ctx.ports.llm.chat_stream_with_usage.call_args
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

        call_args = ctx.ports.llm.chat_stream_with_usage.call_args
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

        call_args = ctx.ports.llm.chat_stream_with_usage.call_args
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

        call_args = ctx.ports.llm.chat_stream_with_usage.call_args
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

        call_args = ctx.ports.llm.chat_stream_with_usage.call_args
        user_msg = call_args[0][0][1].content
        assert "Time Budget" in user_msg
        assert "30 minutes" in user_msg
