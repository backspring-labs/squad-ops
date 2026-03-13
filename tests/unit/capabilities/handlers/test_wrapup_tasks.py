"""Tests for wrap-up task handlers (SIP-0080 Phase 2).

Each test answers "what bug would this catch?" — see inline comments.
"""

from __future__ import annotations

import logging
from unittest.mock import AsyncMock, MagicMock

import pytest

from squadops.bootstrap.handlers import HANDLER_CONFIGS
from squadops.capabilities.handlers.wrapup_tasks import (
    DataClassifyUnresolvedHandler,
    DataGatherEvidenceHandler,
    GovernanceCloseoutDecisionHandler,
    GovernancePublishHandoffHandler,
    QAAssessOutcomesHandler,
    _parse_frontmatter,
)
from squadops.llm.exceptions import LLMError

pytestmark = [pytest.mark.domain_capabilities]

# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

WRAPUP_HANDLER_SPECS = [
    (DataGatherEvidenceHandler, "data.gather_evidence", "data", "evidence_inventory.md"),
    (QAAssessOutcomesHandler, "qa.assess_outcomes", "qa", "outcome_assessment.md"),
    (DataClassifyUnresolvedHandler, "data.classify_unresolved", "data", "unresolved_items.md"),
    (
        GovernanceCloseoutDecisionHandler,
        "governance.closeout_decision",
        "lead",
        "closeout_artifact.md",
    ),
    (GovernancePublishHandoffHandler, "governance.publish_handoff", "lead", "handoff_artifact.md"),
]


def _make_context(llm_response="LLM wrap-up output"):
    """Build a minimal ExecutionContext mock for wrap-up handler tests."""
    llm = AsyncMock()
    llm.chat.return_value = MagicMock(content=llm_response)
    llm.default_model = "test-model"

    prompt_service = MagicMock()
    assembled = MagicMock()
    assembled.content = "Assembled system prompt with task_type layer"
    prompt_service.assemble.return_value = assembled

    ports = MagicMock()
    ports.llm = llm
    ports.prompt_service = prompt_service
    ports.llm_observability = None
    ports.request_renderer = None

    ctx = MagicMock()
    ctx.ports = ports
    ctx.correlation_context = None
    return ctx


VALID_CLOSEOUT = """\
---
confidence: partial_completion
readiness_recommendation: harden
---

## Closeout Summary

Evidence review complete.
"""

VALID_HANDOFF = """\
---
next_cycle_type: implementation
---

## Handoff

Carry-forward items documented.
"""

VALID_INPUTS = {
    "prd": "Build a widget",
    "resolved_config": {"impl_run_id": "run_impl_001"},
}


# ---------------------------------------------------------------------------
# Handler execution: assemble() with task_type
# Bug caught: handler uses get_system_prompt() instead of assemble(),
# which would skip the task_type prompt layer entirely.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "cls,expected_cap_id,expected_role,_artifact",
    WRAPUP_HANDLER_SPECS,
    ids=[s[1] for s in WRAPUP_HANDLER_SPECS],
)
class TestAssembleCalledWithTaskType:
    async def test_assemble_called_with_task_type(
        self,
        cls,
        expected_cap_id,
        expected_role,
        _artifact,
    ):
        ctx = _make_context()
        h = cls()
        await h.handle(ctx, VALID_INPUTS)

        ctx.ports.prompt_service.assemble.assert_called_once_with(
            role=expected_role,
            hook="agent_start",
            task_type=expected_cap_id,
        )


# ---------------------------------------------------------------------------
# Handler execution: success path produces correct artifact
# Bug caught: wrong artifact name, missing content, wrong media_type.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "cls,_cap_id,expected_role,expected_artifact",
    WRAPUP_HANDLER_SPECS,
    ids=[s[1] for s in WRAPUP_HANDLER_SPECS],
)
class TestHandleSuccess:
    async def test_returns_success_with_artifact(
        self,
        cls,
        _cap_id,
        expected_role,
        expected_artifact,
    ):
        # Closeout and handoff handlers need valid frontmatter
        if cls is GovernanceCloseoutDecisionHandler:
            ctx = _make_context(VALID_CLOSEOUT)
        elif cls is GovernancePublishHandoffHandler:
            ctx = _make_context(VALID_HANDOFF)
        else:
            ctx = _make_context()

        h = cls()
        result = await h.handle(ctx, VALID_INPUTS)

        assert result.success is True
        assert result.outputs["role"] == expected_role
        artifacts = result.outputs["artifacts"]
        assert len(artifacts) == 1
        assert artifacts[0]["name"] == expected_artifact
        assert artifacts[0]["media_type"] == "text/markdown"
        assert len(artifacts[0]["content"]) > 0


# ---------------------------------------------------------------------------
# LLM failure: handler gracefully returns success=False
# Bug caught: unhandled LLMError crashes the pipeline instead of
# returning a structured failure result.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "cls,_cap_id,_role,_artifact",
    WRAPUP_HANDLER_SPECS,
    ids=[s[1] for s in WRAPUP_HANDLER_SPECS],
)
class TestHandleLLMError:
    async def test_llm_error_returns_failure(self, cls, _cap_id, _role, _artifact):
        ctx = _make_context()
        ctx.ports.llm.chat.side_effect = LLMError("model timeout")

        h = cls()
        result = await h.handle(ctx, VALID_INPUTS)

        assert result.success is False
        assert "model timeout" in result.error


# ---------------------------------------------------------------------------
# DataGatherEvidenceHandler: validate_inputs requires impl_run_id
# Bug caught: wrap-up runs silently proceed without knowing which
# implementation run to evaluate, producing meaningless evidence.
# ---------------------------------------------------------------------------


class TestDataGatherEvidenceValidation:
    def test_missing_impl_run_id_is_error(self):
        h = DataGatherEvidenceHandler()
        errors = h.validate_inputs({"prd": "test", "resolved_config": {}})
        assert any("impl_run_id" in e for e in errors)

    def test_missing_resolved_config_entirely_is_error(self):
        h = DataGatherEvidenceHandler()
        errors = h.validate_inputs({"prd": "test"})
        assert any("impl_run_id" in e for e in errors)

    def test_valid_inputs_with_impl_run_id(self):
        h = DataGatherEvidenceHandler()
        errors = h.validate_inputs(VALID_INPUTS)
        assert errors == []

    def test_missing_prd_is_also_error(self):
        """impl_run_id check doesn't bypass the base prd requirement."""
        h = DataGatherEvidenceHandler()
        errors = h.validate_inputs({"resolved_config": {"impl_run_id": "run_001"}})
        assert any("prd" in e for e in errors)

    async def test_handles_empty_artifact_contents_degraded_mode(self):
        """Missing artifact_contents is degraded, not failure (D5)."""
        ctx = _make_context()
        inputs = {**VALID_INPUTS, "artifact_contents": {}}
        h = DataGatherEvidenceHandler()
        result = await h.handle(ctx, inputs)
        assert result.success is True


# ---------------------------------------------------------------------------
# GovernanceCloseoutDecisionHandler: YAML frontmatter validation
# Bug caught: LLM produces closeout artifact with invalid/missing
# confidence or readiness_recommendation, which would corrupt
# downstream closeout adjudication.
# ---------------------------------------------------------------------------


class TestCloseoutFrontmatterValidation:
    async def test_valid_frontmatter_passes(self):
        ctx = _make_context(VALID_CLOSEOUT)
        h = GovernanceCloseoutDecisionHandler()
        result = await h.handle(ctx, VALID_INPUTS)
        assert result.success is True

    async def test_missing_frontmatter_fails(self):
        ctx = _make_context("No frontmatter here.")
        h = GovernanceCloseoutDecisionHandler()
        result = await h.handle(ctx, VALID_INPUTS)
        assert result.success is False
        assert "frontmatter" in result.error.lower()

    async def test_invalid_confidence_value_fails(self):
        content = "---\nconfidence: excellent\nreadiness_recommendation: proceed\n---\nBody"
        ctx = _make_context(content)
        h = GovernanceCloseoutDecisionHandler()
        result = await h.handle(ctx, VALID_INPUTS)
        assert result.success is False
        assert "confidence" in result.error
        assert "'excellent'" in result.error

    async def test_missing_confidence_field_fails(self):
        content = "---\nreadiness_recommendation: proceed\n---\nBody"
        ctx = _make_context(content)
        h = GovernanceCloseoutDecisionHandler()
        result = await h.handle(ctx, VALID_INPUTS)
        assert result.success is False
        assert "confidence" in result.error

    async def test_missing_readiness_recommendation_fails(self):
        content = "---\nconfidence: failed\n---\nBody"
        ctx = _make_context(content)
        h = GovernanceCloseoutDecisionHandler()
        result = await h.handle(ctx, VALID_INPUTS)
        assert result.success is False
        assert "readiness_recommendation" in result.error

    async def test_invalid_readiness_recommendation_fails(self):
        content = "---\nconfidence: failed\nreadiness_recommendation: maybe\n---\nBody"
        ctx = _make_context(content)
        h = GovernanceCloseoutDecisionHandler()
        result = await h.handle(ctx, VALID_INPUTS)
        assert result.success is False
        assert "'maybe'" in result.error

    async def test_all_six_confidence_values_accepted(self):
        """Every ConfidenceClassification value passes validation."""
        valid_values = [
            "verified_complete",
            "complete_with_caveats",
            "partial_completion",
            "not_sufficiently_verified",
            "inconclusive",
            "failed",
        ]
        for val in valid_values:
            content = f"---\nconfidence: {val}\nreadiness_recommendation: proceed\n---\nBody"
            ctx = _make_context(content)
            h = GovernanceCloseoutDecisionHandler()
            result = await h.handle(ctx, VALID_INPUTS)
            assert result.success is True, f"confidence={val} should pass"

    async def test_malformed_yaml_frontmatter_fails(self):
        content = "---\n[invalid yaml\n---\nBody"
        ctx = _make_context(content)
        h = GovernanceCloseoutDecisionHandler()
        result = await h.handle(ctx, VALID_INPUTS)
        assert result.success is False
        assert "invalid YAML" in result.error


# ---------------------------------------------------------------------------
# GovernancePublishHandoffHandler: YAML frontmatter validation
# Bug caught: LLM produces handoff artifact with invalid/missing
# next_cycle_type, which would break downstream cycle scheduling.
# ---------------------------------------------------------------------------


class TestHandoffFrontmatterValidation:
    async def test_valid_frontmatter_passes(self):
        ctx = _make_context(VALID_HANDOFF)
        h = GovernancePublishHandoffHandler()
        result = await h.handle(ctx, VALID_INPUTS)
        assert result.success is True

    async def test_missing_frontmatter_fails(self):
        ctx = _make_context("Plain text, no frontmatter.")
        h = GovernancePublishHandoffHandler()
        result = await h.handle(ctx, VALID_INPUTS)
        assert result.success is False
        assert "frontmatter" in result.error.lower()

    async def test_invalid_next_cycle_type_fails(self):
        content = "---\nnext_cycle_type: cleanup\n---\nBody"
        ctx = _make_context(content)
        h = GovernancePublishHandoffHandler()
        result = await h.handle(ctx, VALID_INPUTS)
        assert result.success is False
        assert "'cleanup'" in result.error

    async def test_missing_next_cycle_type_fails(self):
        content = "---\nother_field: value\n---\nBody"
        ctx = _make_context(content)
        h = GovernancePublishHandoffHandler()
        result = await h.handle(ctx, VALID_INPUTS)
        assert result.success is False
        assert "next_cycle_type" in result.error

    async def test_all_five_next_cycle_values_accepted(self):
        """Every NextCycleRecommendation value passes validation."""
        for val in ["planning", "implementation", "hardening", "research", "none"]:
            content = f"---\nnext_cycle_type: {val}\n---\nBody"
            ctx = _make_context(content)
            h = GovernancePublishHandoffHandler()
            result = await h.handle(ctx, VALID_INPUTS)
            assert result.success is True, f"next_cycle_type={val} should pass"


# ---------------------------------------------------------------------------
# DataClassifyUnresolvedHandler: suggested_owner warning
# Bug caught: unrecognized suggested_owner values slip through silently,
# causing downstream routing failures when assigning issue ownership.
# ---------------------------------------------------------------------------


class TestClassifyUnresolvedOwnerValidation:
    async def test_valid_owners_no_warning(self, caplog):
        content = "| Issue | suggested_owner: lead |\n| Bug | suggested_owner: qa |"
        ctx = _make_context(content)
        h = DataClassifyUnresolvedHandler()
        with caplog.at_level(logging.WARNING):
            result = await h.handle(ctx, VALID_INPUTS)
        assert result.success is True
        assert "Unrecognized suggested_owner" not in caplog.text

    async def test_invalid_owner_logs_warning_but_succeeds(self, caplog):
        content = "| Issue | suggested_owner: batman |"
        ctx = _make_context(content)
        h = DataClassifyUnresolvedHandler()
        with caplog.at_level(logging.WARNING):
            result = await h.handle(ctx, VALID_INPUTS)
        assert result.success is True
        assert "batman" in caplog.text

    async def test_no_owners_in_content_is_fine(self, caplog):
        """Content without any suggested_owner mentions should not warn."""
        ctx = _make_context("Just a plain unresolved items list.")
        h = DataClassifyUnresolvedHandler()
        with caplog.at_level(logging.WARNING):
            result = await h.handle(ctx, VALID_INPUTS)
        assert result.success is True
        assert "Unrecognized suggested_owner" not in caplog.text


# ---------------------------------------------------------------------------
# Prior outputs chaining: upstream outputs appear in user prompt
# Bug caught: handler silently drops prior_outputs, breaking the
# sequential analysis chain where each handler builds on predecessors.
# ---------------------------------------------------------------------------


class TestPriorOutputsChaining:
    async def test_prior_outputs_in_llm_prompt(self):
        ctx = _make_context(VALID_CLOSEOUT)
        inputs = {
            **VALID_INPUTS,
            "prior_outputs": {"data": "Evidence inventory summary"},
        }
        h = GovernanceCloseoutDecisionHandler()
        await h.handle(ctx, inputs)

        call_args = ctx.ports.llm.chat.call_args
        user_msg = call_args[0][0][1].content
        assert "Evidence inventory summary" in user_msg


# ---------------------------------------------------------------------------
# Bootstrap registration: handlers are dispatchable
# Bug caught: handler class exists but is never registered in
# HANDLER_CONFIGS, so the executor cannot dispatch wrap-up tasks.
# ---------------------------------------------------------------------------


class TestBootstrapRegistration:
    @pytest.mark.parametrize(
        "cls,_cap_id,_role,_artifact",
        WRAPUP_HANDLER_SPECS,
        ids=[s[1] for s in WRAPUP_HANDLER_SPECS],
    )
    def test_handler_registered(self, cls, _cap_id, _role, _artifact):
        registered_classes = {config[0] for config in HANDLER_CONFIGS}
        assert cls in registered_classes

    @pytest.mark.parametrize(
        "cls,_cap_id,expected_role,_artifact",
        WRAPUP_HANDLER_SPECS,
        ids=[s[1] for s in WRAPUP_HANDLER_SPECS],
    )
    def test_handler_registered_with_correct_role(
        self,
        cls,
        _cap_id,
        expected_role,
        _artifact,
    ):
        """Handler registered with wrong role → dispatched to wrong agent."""
        for config_cls, roles in HANDLER_CONFIGS:
            if config_cls is cls:
                assert expected_role in roles
                break


# ---------------------------------------------------------------------------
# _parse_frontmatter: shared utility edge cases
# Bug caught: frontmatter parser silently accepts non-dict YAML (e.g.,
# a bare string or list), causing downstream KeyError on field access.
# ---------------------------------------------------------------------------


class TestParseFrontmatter:
    def test_valid_frontmatter(self):
        fm, err = _parse_frontmatter("---\nkey: value\n---\nBody")
        assert err is None
        assert fm == {"key": "value"}

    def test_missing_frontmatter(self):
        fm, err = _parse_frontmatter("No frontmatter")
        assert fm is None
        assert "missing" in err

    def test_non_dict_yaml(self):
        fm, err = _parse_frontmatter("---\n- item1\n- item2\n---\nBody")
        assert fm is None
        assert "not a mapping" in err

    def test_invalid_yaml(self):
        fm, err = _parse_frontmatter("---\n[broken\n---\nBody")
        assert fm is None
        assert "invalid YAML" in err
