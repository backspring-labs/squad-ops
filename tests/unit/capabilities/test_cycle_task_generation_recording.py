"""Tests for LLM generation recording in cycle task handlers.

Verifies that _CycleTaskHandler.handle() calls record_generation()
on the LLM observability port after a successful LLM chat, and
gracefully skips when observability or correlation context is absent.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from squadops.capabilities.handlers.cycle_tasks import StrategyAnalyzeHandler
from squadops.llm.models import ChatMessage
from squadops.telemetry.models import MAX_OBSERVABILITY_TEXT_LENGTH, CorrelationContext

pytestmark = [pytest.mark.domain_capabilities]


@pytest.fixture
def mock_context_with_obs():
    """Context with llm_observability and correlation_context set."""
    ctx = MagicMock()
    ctx.ports.llm.chat = AsyncMock(
        return_value=ChatMessage(role="assistant", content="LLM output"),
    )
    ctx.ports.llm.chat_stream_with_usage = AsyncMock(
        return_value=ChatMessage(role="assistant", content="LLM output"),
    )
    ctx.ports.llm.default_model = "llama3.2"
    assembled = MagicMock()
    assembled.content = "System prompt"
    ctx.ports.prompt_service.get_system_prompt = MagicMock(return_value=assembled)

    # LLM observability mock
    mock_obs = MagicMock()
    ctx.ports.llm_observability = mock_obs

    # No request renderer by default (matches PortsBundle default)
    ctx.ports.request_renderer = None

    # Correlation context
    ctx.correlation_context = CorrelationContext(
        cycle_id="cyc_001",
        task_id="task_abc",
        trace_id="shared-trace",
        agent_id="nat",
        agent_role="strat",
    )

    return ctx, mock_obs


@pytest.fixture
def mock_context_no_obs():
    """Context without llm_observability."""
    ctx = MagicMock()
    ctx.ports.llm.chat = AsyncMock(
        return_value=ChatMessage(role="assistant", content="LLM output"),
    )
    ctx.ports.llm.chat_stream_with_usage = AsyncMock(
        return_value=ChatMessage(role="assistant", content="LLM output"),
    )
    assembled = MagicMock()
    assembled.content = "System prompt"
    ctx.ports.prompt_service.get_system_prompt = MagicMock(return_value=assembled)

    # No llm_observability attribute
    ctx.ports.llm_observability = None
    ctx.ports.request_renderer = None
    ctx.correlation_context = None

    return ctx


@pytest.fixture
def mock_context_no_correlation():
    """Context with llm_observability but no correlation_context."""
    ctx = MagicMock()
    ctx.ports.llm.chat = AsyncMock(
        return_value=ChatMessage(role="assistant", content="LLM output"),
    )
    ctx.ports.llm.chat_stream_with_usage = AsyncMock(
        return_value=ChatMessage(role="assistant", content="LLM output"),
    )
    assembled = MagicMock()
    assembled.content = "System prompt"
    ctx.ports.prompt_service.get_system_prompt = MagicMock(return_value=assembled)

    mock_obs = MagicMock()
    ctx.ports.llm_observability = mock_obs
    ctx.ports.request_renderer = None
    ctx.correlation_context = None

    return ctx, mock_obs


class TestHandlerRecordsGeneration:
    """Verify record_generation() called after LLM chat."""

    async def test_record_generation_called(self, mock_context_with_obs):
        ctx, mock_obs = mock_context_with_obs
        handler = StrategyAnalyzeHandler()

        result = await handler.handle(ctx, {"prd": "Build a widget"})

        assert result.success is True
        mock_obs.record_generation.assert_called_once()

        # Verify the correlation context was passed
        call_args = mock_obs.record_generation.call_args
        passed_ctx = call_args[0][0]
        assert passed_ctx.cycle_id == "cyc_001"
        assert passed_ctx.trace_id == "shared-trace"

    async def test_generation_record_has_expected_fields(self, mock_context_with_obs):
        ctx, mock_obs = mock_context_with_obs
        handler = StrategyAnalyzeHandler()

        await handler.handle(ctx, {"prd": "Build a widget"})

        call_args = mock_obs.record_generation.call_args
        gen_record = call_args[0][1]  # GenerationRecord
        assert gen_record.generation_id  # non-empty UUID
        assert gen_record.prompt_text  # non-empty
        assert gen_record.response_text == "LLM output"
        assert gen_record.latency_ms is not None
        assert gen_record.latency_ms >= 0

    async def test_generation_record_has_model_name(self, mock_context_with_obs):
        ctx, mock_obs = mock_context_with_obs
        handler = StrategyAnalyzeHandler()

        await handler.handle(ctx, {"prd": "Build a widget"})

        call_args = mock_obs.record_generation.call_args
        gen_record = call_args[0][1]
        assert gen_record.model == "llama3.2"

    async def test_prompt_layers_have_role(self, mock_context_with_obs):
        ctx, mock_obs = mock_context_with_obs
        handler = StrategyAnalyzeHandler()

        await handler.handle(ctx, {"prd": "Build a widget"})

        call_args = mock_obs.record_generation.call_args
        layers = call_args[0][2]  # PromptLayerMetadata
        assert layers.prompt_layer_set_id == "strat-cycle"
        assert len(layers.layers) == 2
        assert layers.layers[0].layer_type == "system"
        assert layers.layers[0].layer_id == "strat-system"

    async def test_prompt_text_truncated(self, mock_context_with_obs):
        ctx, mock_obs = mock_context_with_obs
        handler = StrategyAnalyzeHandler()

        # Use a very long PRD to test truncation
        long_prd = "x" * 5000
        await handler.handle(ctx, {"prd": long_prd})

        call_args = mock_obs.record_generation.call_args
        gen_record = call_args[0][1]
        assert len(gen_record.prompt_text) <= MAX_OBSERVABILITY_TEXT_LENGTH


class TestHandlerSkipsRecordingWhenNoObservability:
    """Graceful when llm_observability is None."""

    async def test_no_error(self, mock_context_no_obs):
        ctx = mock_context_no_obs
        handler = StrategyAnalyzeHandler()

        result = await handler.handle(ctx, {"prd": "Build a widget"})

        assert result.success is True


class TestHandlerSkipsRecordingWhenNoContext:
    """Graceful when correlation_context is None."""

    async def test_no_recording(self, mock_context_no_correlation):
        ctx, mock_obs = mock_context_no_correlation
        handler = StrategyAnalyzeHandler()

        result = await handler.handle(ctx, {"prd": "Build a widget"})

        assert result.success is True
        mock_obs.record_generation.assert_not_called()


class TestHandlerEmitsCallMetrics:
    """#2204, #2203: each model call's numbers reach the metrics port, not only a log line."""

    async def test_a_call_s_decode_rate_and_prefill_reach_the_metrics_port(
        self, mock_context_with_obs
    ):
        """Enters at ``handle()``, the call a live cycle makes. Bug caught: the decode rate kept
        only as the "LLM throughput" log line, so the host panel and the engine comparison had
        nothing to read over time."""
        from squadops.telemetry.llm_metrics import (
            LLM_DECODE_TOKENS_PER_SECOND,
            LLM_PREFILL_SECONDS,
        )

        ctx, _ = mock_context_with_obs
        ctx.ports.llm.chat_stream_with_usage = AsyncMock(
            return_value=ChatMessage(
                role="assistant",
                content="LLM output",
                prompt_tokens=9605,
                completion_tokens=4922,
                tokens_per_second=31.0,
                prompt_eval_seconds=4.2,
            )
        )
        ctx.ports.metrics = MagicMock()

        result = await StrategyAnalyzeHandler().handle(ctx, {"prd": "Build a widget"})

        assert result.success is True
        observed = {
            c.args[0]: (c.args[1], c.args[2]) for c in ctx.ports.metrics.histogram.call_args_list
        }
        assert observed[LLM_DECODE_TOKENS_PER_SECOND][0] == 31.0
        assert observed[LLM_PREFILL_SECONDS][0] == 4.2
        assert observed[LLM_DECODE_TOKENS_PER_SECOND][1]["role"] == "strat"
        assert observed[LLM_DECODE_TOKENS_PER_SECOND][1]["long"] == "true"
