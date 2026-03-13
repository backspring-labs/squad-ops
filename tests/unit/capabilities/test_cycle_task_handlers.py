"""Unit tests for cycle task handlers (SIP-0066).

Tests the 5 cycle task handlers in
``squadops.capabilities.handlers.cycle_tasks``:

- StrategyAnalyzeHandler  (strategy.analyze_prd / strat)
- DevelopmentDesignHandler (development.design / dev)
- QAValidateHandler       (qa.validate / qa)
- DataReportHandler       (data.report / data)
- GovernanceReviewHandler (governance.review / lead)

Covers: capability_id pinning, name/description properties,
validate_inputs, handle() outputs/evidence, LLM call verification,
prior_outputs prompt building, LLM error handling, artifact names,
and bootstrap registration.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from squadops.bootstrap.handlers import HANDLER_CONFIGS
from squadops.capabilities.handlers.base import HandlerEvidence, HandlerResult
from squadops.capabilities.handlers.cycle_tasks import (
    DataReportHandler,
    DevelopmentDesignHandler,
    GovernanceReviewHandler,
    QAValidateHandler,
    StrategyAnalyzeHandler,
)
from squadops.llm.exceptions import LLMConnectionError, LLMModelNotFoundError, LLMTimeoutError
from squadops.llm.models import ChatMessage

pytestmark = [pytest.mark.domain_capabilities]


# ---------------------------------------------------------------------------
# Parametrised data for the five handlers
# ---------------------------------------------------------------------------
HANDLER_SPECS = [
    (StrategyAnalyzeHandler, "strategy.analyze_prd", "strat"),
    (DevelopmentDesignHandler, "development.design", "dev"),
    (QAValidateHandler, "qa.validate", "qa"),
    (DataReportHandler, "data.report", "data"),
    (GovernanceReviewHandler, "governance.review", "lead"),
]

HANDLER_CLASSES = [cls for cls, _, _ in HANDLER_SPECS]

EXPECTED_ARTIFACT_NAMES = {
    StrategyAnalyzeHandler: "strategy_analysis.md",
    DevelopmentDesignHandler: "implementation_plan.md",
    QAValidateHandler: "validation_plan.md",
    DataReportHandler: "data_report.md",
    GovernanceReviewHandler: "governance_review.md",
}


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest.fixture(params=HANDLER_SPECS, ids=lambda s: s[0].__name__)
def handler_spec(request):
    """Yield (handler_instance, expected_capability_id, expected_role)."""
    cls, cap_id, role = request.param
    return cls(), cap_id, role


@pytest.fixture()
def mock_context():
    """Return a MagicMock with llm.chat and prompt_service stubbed."""
    ctx = MagicMock()
    ctx.ports.llm.chat = AsyncMock(
        return_value=ChatMessage(role="assistant", content="LLM generated output"),
    )
    # PromptService stub: get_system_prompt returns an object with .content
    assembled = MagicMock()
    assembled.content = "Assembled system prompt from PromptService"
    ctx.ports.prompt_service.get_system_prompt = MagicMock(return_value=assembled)
    # No request renderer by default (matches PortsBundle default)
    ctx.ports.request_renderer = None
    return ctx


# ---------------------------------------------------------------------------
# 1. capability_id matches the pinned value
# ---------------------------------------------------------------------------
class TestCapabilityId:
    @pytest.mark.parametrize(
        "cls, expected_id, _role",
        HANDLER_SPECS,
        ids=[c.__name__ for c, _, _ in HANDLER_SPECS],
    )
    def test_capability_id_matches(self, cls, expected_id, _role):
        handler = cls()
        assert handler.capability_id == expected_id


# ---------------------------------------------------------------------------
# 2. name returns a non-empty string
# ---------------------------------------------------------------------------
class TestName:
    @pytest.mark.parametrize(
        "cls",
        HANDLER_CLASSES,
        ids=[c.__name__ for c in HANDLER_CLASSES],
    )
    def test_name_non_empty(self, cls):
        handler = cls()
        assert isinstance(handler.name, str)
        assert len(handler.name) > 0


# ---------------------------------------------------------------------------
# 3. description returns a non-empty string
# ---------------------------------------------------------------------------
class TestDescription:
    @pytest.mark.parametrize(
        "cls",
        HANDLER_CLASSES,
        ids=[c.__name__ for c in HANDLER_CLASSES],
    )
    def test_description_non_empty(self, cls):
        handler = cls()
        assert isinstance(handler.description, str)
        assert len(handler.description) > 0


# ---------------------------------------------------------------------------
# 4. validate_inputs — missing prd
# ---------------------------------------------------------------------------
class TestValidateInputsMissingPrd:
    @pytest.mark.parametrize(
        "cls",
        HANDLER_CLASSES,
        ids=[c.__name__ for c in HANDLER_CLASSES],
    )
    def test_missing_prd(self, cls):
        handler = cls()
        errors = handler.validate_inputs({})
        assert errors == ["'prd' is required"]


# ---------------------------------------------------------------------------
# 5. validate_inputs — valid inputs
# ---------------------------------------------------------------------------
class TestValidateInputsValid:
    @pytest.mark.parametrize(
        "cls",
        HANDLER_CLASSES,
        ids=[c.__name__ for c in HANDLER_CLASSES],
    )
    def test_valid_inputs(self, cls):
        handler = cls()
        errors = handler.validate_inputs({"prd": "something"})
        assert errors == []


# ---------------------------------------------------------------------------
# 6. handle() returns success with expected output keys
# ---------------------------------------------------------------------------
class TestHandleSuccess:
    @pytest.mark.parametrize(
        "cls, _cap_id, expected_role",
        HANDLER_SPECS,
        ids=[c.__name__ for c, _, _ in HANDLER_SPECS],
    )
    async def test_handle_returns_success(self, cls, _cap_id, expected_role, mock_context):
        handler = cls()
        result = await handler.handle(mock_context, {"prd": "Build a widget"})

        assert isinstance(result, HandlerResult)
        assert result.success is True
        assert "summary" in result.outputs
        assert "role" in result.outputs
        assert "artifacts" in result.outputs
        assert result.outputs["role"] == expected_role


# ---------------------------------------------------------------------------
# 7. handle() outputs["artifacts"] is a non-empty list
# ---------------------------------------------------------------------------
class TestHandleArtifacts:
    @pytest.mark.parametrize(
        "cls",
        HANDLER_CLASSES,
        ids=[c.__name__ for c in HANDLER_CLASSES],
    )
    async def test_artifacts_non_empty_list(self, cls, mock_context):
        handler = cls()
        result = await handler.handle(mock_context, {"prd": "Build a widget"})

        artifacts = result.outputs["artifacts"]
        assert isinstance(artifacts, list)
        assert len(artifacts) > 0


# ---------------------------------------------------------------------------
# 8. handle() result has non-None _evidence (HandlerEvidence)
# ---------------------------------------------------------------------------
class TestHandleEvidence:
    @pytest.mark.parametrize(
        "cls",
        HANDLER_CLASSES,
        ids=[c.__name__ for c in HANDLER_CLASSES],
    )
    async def test_evidence_present(self, cls, mock_context):
        handler = cls()
        result = await handler.handle(mock_context, {"prd": "Build a widget"})

        assert result._evidence is not None
        assert isinstance(result._evidence, HandlerEvidence)
        assert result.evidence.capability_id == handler.capability_id
        assert result.evidence.handler_name == handler.name
        assert result.evidence.duration_ms >= 0


# ---------------------------------------------------------------------------
# 9. Bootstrap registration — all 5 handlers present in HANDLER_CONFIGS
# ---------------------------------------------------------------------------
class TestBootstrapRegistration:
    @pytest.mark.parametrize(
        "cls, _cap_id, expected_role",
        HANDLER_SPECS,
        ids=[c.__name__ for c, _, _ in HANDLER_SPECS],
    )
    def test_handler_in_bootstrap(self, cls, _cap_id, expected_role):
        registered = {entry[0]: entry[1] for entry in HANDLER_CONFIGS}
        assert cls in registered, f"{cls.__name__} not found in HANDLER_CONFIGS"
        assert (expected_role,) == registered[cls], (
            f"{cls.__name__} expected roles ({expected_role},), got {registered[cls]}"
        )

    def test_all_five_cycle_handlers_registered(self):
        registered_classes = {entry[0] for entry in HANDLER_CONFIGS}
        for cls in HANDLER_CLASSES:
            assert cls in registered_classes, f"{cls.__name__} missing from HANDLER_CONFIGS"


# ---------------------------------------------------------------------------
# 10. handle() calls context.ports.llm.chat with system + user messages
# ---------------------------------------------------------------------------
class TestHandleLLMCall:
    @pytest.mark.parametrize(
        "cls",
        HANDLER_CLASSES,
        ids=[c.__name__ for c in HANDLER_CLASSES],
    )
    async def test_llm_chat_called_once(self, cls, mock_context):
        handler = cls()
        await handler.handle(mock_context, {"prd": "Build a widget"})

        mock_context.ports.llm.chat.assert_awaited_once()

    @pytest.mark.parametrize(
        "cls",
        HANDLER_CLASSES,
        ids=[c.__name__ for c in HANDLER_CLASSES],
    )
    async def test_llm_chat_receives_system_and_user_messages(self, cls, mock_context):
        handler = cls()
        await handler.handle(mock_context, {"prd": "Build a widget"})

        call_args = mock_context.ports.llm.chat.call_args
        messages = call_args[0][0]
        assert len(messages) == 2
        assert messages[0].role == "system"
        assert messages[1].role == "user"

    @pytest.mark.parametrize(
        "cls",
        HANDLER_CLASSES,
        ids=[c.__name__ for c in HANDLER_CLASSES],
    )
    async def test_user_message_contains_prd(self, cls, mock_context):
        handler = cls()
        await handler.handle(mock_context, {"prd": "Build a fancy widget"})

        call_args = mock_context.ports.llm.chat.call_args
        messages = call_args[0][0]
        assert "Build a fancy widget" in messages[1].content

    @pytest.mark.parametrize(
        "cls",
        HANDLER_CLASSES,
        ids=[c.__name__ for c in HANDLER_CLASSES],
    )
    async def test_artifact_content_is_llm_response(self, cls, mock_context):
        handler = cls()
        result = await handler.handle(mock_context, {"prd": "Build a widget"})

        artifact = result.outputs["artifacts"][0]
        assert artifact["content"] == "LLM generated output"


# ---------------------------------------------------------------------------
# 11. handle() includes prior_outputs in user prompt when present
# ---------------------------------------------------------------------------
class TestHandlePriorOutputsInPrompt:
    @pytest.mark.parametrize(
        "cls",
        HANDLER_CLASSES,
        ids=[c.__name__ for c in HANDLER_CLASSES],
    )
    async def test_prior_outputs_included_in_prompt(self, cls, mock_context):
        handler = cls()
        inputs = {
            "prd": "Build a widget",
            "prior_outputs": {
                "strat": "Strategy analysis summary here",
                "dev": "Implementation plan summary here",
            },
        }
        await handler.handle(mock_context, inputs)

        call_args = mock_context.ports.llm.chat.call_args
        user_msg = call_args[0][0][1].content
        assert "Prior Analysis from Upstream Roles" in user_msg
        assert "Strategy analysis summary here" in user_msg
        assert "Implementation plan summary here" in user_msg

    @pytest.mark.parametrize(
        "cls",
        HANDLER_CLASSES,
        ids=[c.__name__ for c in HANDLER_CLASSES],
    )
    async def test_no_prior_outputs_section_when_empty(self, cls, mock_context):
        handler = cls()
        await handler.handle(mock_context, {"prd": "Build a widget"})

        call_args = mock_context.ports.llm.chat.call_args
        user_msg = call_args[0][0][1].content
        assert "Prior Analysis" not in user_msg

    @pytest.mark.parametrize(
        "cls",
        HANDLER_CLASSES,
        ids=[c.__name__ for c in HANDLER_CLASSES],
    )
    async def test_no_prior_outputs_section_when_none(self, cls, mock_context):
        handler = cls()
        await handler.handle(mock_context, {"prd": "Build a widget", "prior_outputs": None})

        call_args = mock_context.ports.llm.chat.call_args
        user_msg = call_args[0][0][1].content
        assert "Prior Analysis" not in user_msg


# ---------------------------------------------------------------------------
# 12. handle() returns failure on LLM errors
# ---------------------------------------------------------------------------
class TestHandleLLMError:
    @pytest.mark.parametrize(
        "exc_cls",
        [LLMConnectionError, LLMTimeoutError, LLMModelNotFoundError],
        ids=["connection", "timeout", "model_not_found"],
    )
    @pytest.mark.parametrize(
        "handler_cls",
        HANDLER_CLASSES,
        ids=[c.__name__ for c in HANDLER_CLASSES],
    )
    async def test_llm_error_returns_failure(self, handler_cls, exc_cls, mock_context):
        mock_context.ports.llm.chat = AsyncMock(side_effect=exc_cls("boom"))
        handler = handler_cls()
        result = await handler.handle(mock_context, {"prd": "Build a widget"})

        assert result.success is False
        assert result.outputs == {}
        assert "boom" in result.error


# ---------------------------------------------------------------------------
# 13. Each handler produces the correct artifact name
# ---------------------------------------------------------------------------
class TestHandleArtifactNames:
    @pytest.mark.parametrize(
        "cls, expected_name",
        list(EXPECTED_ARTIFACT_NAMES.items()),
        ids=[c.__name__ for c in EXPECTED_ARTIFACT_NAMES],
    )
    async def test_artifact_name(self, cls, expected_name, mock_context):
        handler = cls()
        result = await handler.handle(mock_context, {"prd": "Build a widget"})

        artifact = result.outputs["artifacts"][0]
        assert artifact["name"] == expected_name
        assert artifact["media_type"] == "text/markdown"
        assert artifact["type"] == "document"


# ---------------------------------------------------------------------------
# 14. handle() uses PromptService for system prompt (SIP-0057)
# ---------------------------------------------------------------------------
EXPECTED_ROLES = {
    StrategyAnalyzeHandler: "strat",
    DevelopmentDesignHandler: "dev",
    QAValidateHandler: "qa",
    DataReportHandler: "data",
    GovernanceReviewHandler: "lead",
}


class TestHandleUsesPromptService:
    @pytest.mark.parametrize(
        "cls, expected_role",
        list(EXPECTED_ROLES.items()),
        ids=[c.__name__ for c in EXPECTED_ROLES],
    )
    async def test_prompt_service_called_with_role(self, cls, expected_role, mock_context):
        handler = cls()
        await handler.handle(mock_context, {"prd": "Build a widget"})

        mock_context.ports.prompt_service.get_system_prompt.assert_called_once_with(expected_role)

    @pytest.mark.parametrize(
        "cls",
        HANDLER_CLASSES,
        ids=[c.__name__ for c in HANDLER_CLASSES],
    )
    async def test_system_message_uses_assembled_content(self, cls, mock_context):
        handler = cls()
        await handler.handle(mock_context, {"prd": "Build a widget"})

        call_args = mock_context.ports.llm.chat.call_args
        messages = call_args[0][0]
        assert messages[0].role == "system"
        assert messages[0].content == "Assembled system prompt from PromptService"


# ---------------------------------------------------------------------------
# 15. Config overrides flow to chat() kwargs (SIP-0075 §3.2)
# ---------------------------------------------------------------------------
class TestConfigOverridesFlow:
    @pytest.mark.parametrize(
        "cls",
        HANDLER_CLASSES,
        ids=[c.__name__ for c in HANDLER_CLASSES],
    )
    async def test_agent_model_passed_to_chat(self, cls, mock_context):
        handler = cls()
        inputs = {
            "prd": "Build a widget",
            "agent_model": "qwen2.5:7b",
            "agent_config_overrides": {},
        }
        await handler.handle(mock_context, inputs)

        call_kwargs = mock_context.ports.llm.chat.call_args[1]
        assert call_kwargs["model"] == "qwen2.5:7b"

    @pytest.mark.parametrize(
        "cls",
        HANDLER_CLASSES,
        ids=[c.__name__ for c in HANDLER_CLASSES],
    )
    async def test_temperature_override_passed_to_chat(self, cls, mock_context):
        handler = cls()
        inputs = {
            "prd": "Build a widget",
            "agent_model": "qwen2.5:7b",
            "agent_config_overrides": {"temperature": 0.3},
        }
        await handler.handle(mock_context, inputs)

        call_kwargs = mock_context.ports.llm.chat.call_args[1]
        assert call_kwargs["temperature"] == 0.3

    @pytest.mark.parametrize(
        "cls",
        HANDLER_CLASSES,
        ids=[c.__name__ for c in HANDLER_CLASSES],
    )
    async def test_max_tokens_override_passed_to_chat(self, cls, mock_context):
        handler = cls()
        inputs = {
            "prd": "Build a widget",
            "agent_model": "qwen2.5:7b",
            "agent_config_overrides": {"max_completion_tokens": 4096},
        }
        await handler.handle(mock_context, inputs)

        call_kwargs = mock_context.ports.llm.chat.call_args[1]
        assert call_kwargs["max_tokens"] == 4096

    @pytest.mark.parametrize(
        "cls",
        HANDLER_CLASSES,
        ids=[c.__name__ for c in HANDLER_CLASSES],
    )
    async def test_timeout_override_passed_to_chat(self, cls, mock_context):
        handler = cls()
        inputs = {
            "prd": "Build a widget",
            "agent_model": "qwen2.5:7b",
            "agent_config_overrides": {"timeout_seconds": 600},
        }
        await handler.handle(mock_context, inputs)

        call_kwargs = mock_context.ports.llm.chat.call_args[1]
        assert call_kwargs["timeout_seconds"] == 600

    @pytest.mark.parametrize(
        "cls",
        HANDLER_CLASSES,
        ids=[c.__name__ for c in HANDLER_CLASSES],
    )
    async def test_no_overrides_no_extra_kwargs(self, cls, mock_context):
        handler = cls()
        inputs = {"prd": "Build a widget"}
        await handler.handle(mock_context, inputs)

        call_kwargs = mock_context.ports.llm.chat.call_args[1]
        assert "model" not in call_kwargs
        assert "temperature" not in call_kwargs
        assert "max_tokens" not in call_kwargs
        assert "timeout_seconds" not in call_kwargs

    @pytest.mark.parametrize(
        "cls",
        HANDLER_CLASSES,
        ids=[c.__name__ for c in HANDLER_CLASSES],
    )
    async def test_empty_model_string_not_passed(self, cls, mock_context):
        handler = cls()
        inputs = {
            "prd": "Build a widget",
            "agent_model": "",
            "agent_config_overrides": {},
        }
        await handler.handle(mock_context, inputs)

        call_kwargs = mock_context.ports.llm.chat.call_args[1]
        assert "model" not in call_kwargs

    @pytest.mark.parametrize(
        "cls",
        HANDLER_CLASSES,
        ids=[c.__name__ for c in HANDLER_CLASSES],
    )
    async def test_all_overrides_combined(self, cls, mock_context):
        handler = cls()
        inputs = {
            "prd": "Build a widget",
            "agent_model": "deepseek-coder:6.7b",
            "agent_config_overrides": {
                "temperature": 0.1,
                "max_completion_tokens": 4096,
                "timeout_seconds": 300,
            },
        }
        await handler.handle(mock_context, inputs)

        call_kwargs = mock_context.ports.llm.chat.call_args[1]
        assert call_kwargs["model"] == "deepseek-coder:6.7b"
        assert call_kwargs["temperature"] == 0.1
        assert call_kwargs["max_tokens"] == 4096
        assert call_kwargs["timeout_seconds"] == 300
