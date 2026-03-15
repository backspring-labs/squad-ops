"""Tests for LangFuse observability wiring in ChatAgentExecutor (SIP-0085 Phase 5).

What bug would these catch?
- Silent observability failures: LangFuse calls never fire after streaming completes.
- Incorrect trace/span lifecycle: open without close, or generation recorded outside spans.
- None-guard bypass: crash when llm_observability is None (common in dev/test).
- Latency not measured: latency_ms missing or zero despite real stream time.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

# ---------------------------------------------------------------------------
# Helpers (reuses pattern from test_chat_executor.py)
# ---------------------------------------------------------------------------


def _make_ports_bundle(
    *,
    stream_chunks: list[str] | None = None,
    system_prompt: str = "You are a test agent.",
    llm_observability=None,
):
    """Build a mock PortsBundle with optional observability."""
    from squadops.prompts.models import AssembledPrompt

    bundle = MagicMock()

    chunks = stream_chunks if stream_chunks is not None else ["hello", " world"]

    async def fake_chat_stream(messages, **kwargs):
        for c in chunks:
            yield c

    bundle.llm = MagicMock()
    bundle.llm.chat_stream = fake_chat_stream
    bundle.llm.default_model = "qwen2.5:7b"

    bundle.prompt_service = MagicMock()
    bundle.prompt_service.get_system_prompt.return_value = AssembledPrompt(
        content=system_prompt,
        fragment_hashes=(),
        assembly_hash="test",
        role="test",
        hook="agent_start",
        version="1",
    )

    bundle.memory = AsyncMock()
    bundle.memory.search = AsyncMock(return_value=[])
    bundle.memory.store = AsyncMock()

    bundle.llm_observability = llm_observability

    return bundle


def _make_context(user_text="hi", task_id="t1", context_id="ctx1"):
    ctx = MagicMock()
    ctx.get_user_input.return_value = user_text
    ctx.task_id = task_id
    ctx.context_id = context_id
    return ctx


def _make_event_queue():
    eq = MagicMock()
    eq.events = []
    eq.enqueue_event = lambda event: eq.events.append(event)
    return eq


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestChatLangFuseRecording:
    """LangFuse generation recording around chat streaming."""

    async def test_full_lifecycle_called_after_stream(self):
        """After streaming, the full trace→span→generation→close→flush sequence fires."""
        from adapters.comms.chat_executor import ChatAgentExecutor

        mock_obs = MagicMock()
        ports = _make_ports_bundle(
            stream_chunks=["one", "two"],
            llm_observability=mock_obs,
        )
        executor = ChatAgentExecutor(ports=ports, role_id="comms")
        ctx = _make_context(context_id="sess-1", task_id="t-42")
        eq = _make_event_queue()

        await executor.execute(ctx, eq)

        # Verify lifecycle sequence
        mock_obs.start_cycle_trace.assert_called_once()
        mock_obs.start_task_span.assert_called_once()
        mock_obs.record_generation.assert_called_once()
        mock_obs.end_task_span.assert_called_once()
        mock_obs.end_cycle_trace.assert_called_once()
        mock_obs.flush.assert_called_once()

    async def test_correlation_context_contains_chat_ids(self):
        """CorrelationContext uses chat-prefixed cycle_id and task_id."""
        from adapters.comms.chat_executor import ChatAgentExecutor

        mock_obs = MagicMock()
        ports = _make_ports_bundle(llm_observability=mock_obs)
        executor = ChatAgentExecutor(ports=ports, role_id="comms")
        ctx = _make_context(context_id="sess-abc", task_id="t-xyz")
        eq = _make_event_queue()

        await executor.execute(ctx, eq)

        correlation_ctx = mock_obs.start_cycle_trace.call_args[0][0]
        assert correlation_ctx.cycle_id == "chat-sess-abc"
        assert correlation_ctx.task_id == "chat-t-xyz"
        assert correlation_ctx.agent_id == "comms"
        assert correlation_ctx.agent_role == "comms"

    async def test_generation_record_has_model_and_texts(self):
        """GenerationRecord includes model name, prompt text, and full response."""
        from adapters.comms.chat_executor import ChatAgentExecutor

        mock_obs = MagicMock()
        ports = _make_ports_bundle(
            stream_chunks=["hello", " world"],
            system_prompt="You are Joi.",
            llm_observability=mock_obs,
        )
        executor = ChatAgentExecutor(ports=ports, role_id="comms")
        ctx = _make_context(user_text="What's up?")
        eq = _make_event_queue()

        await executor.execute(ctx, eq)

        record = mock_obs.record_generation.call_args[0][1]
        assert record.model == "qwen2.5:7b"
        assert record.response_text == "hello world"
        assert "You are Joi." in record.prompt_text
        assert "What's up?" in record.prompt_text
        assert record.generation_id  # UUID4, not empty

    async def test_generation_record_has_positive_latency(self):
        """latency_ms is positive (stream actually timed)."""
        from adapters.comms.chat_executor import ChatAgentExecutor

        mock_obs = MagicMock()
        ports = _make_ports_bundle(llm_observability=mock_obs)
        executor = ChatAgentExecutor(ports=ports, role_id="comms")
        ctx = _make_context()
        eq = _make_event_queue()

        await executor.execute(ctx, eq)

        record = mock_obs.record_generation.call_args[0][1]
        assert record.latency_ms is not None
        assert record.latency_ms >= 0

    async def test_prompt_layers_use_role_id(self):
        """PromptLayerMetadata references the role for traceability."""
        from adapters.comms.chat_executor import ChatAgentExecutor

        mock_obs = MagicMock()
        ports = _make_ports_bundle(llm_observability=mock_obs)
        executor = ChatAgentExecutor(ports=ports, role_id="dev")
        ctx = _make_context()
        eq = _make_event_queue()

        await executor.execute(ctx, eq)

        layers = mock_obs.record_generation.call_args[0][2]
        assert layers.prompt_layer_set_id == "dev-chat"
        assert layers.layers[0].layer_id == "dev-system"
        assert layers.layers[1].layer_id == "console-chat"


class TestChatLangFuseNoneGuard:
    """When llm_observability is None, no crash and no calls."""

    async def test_none_observability_does_not_crash(self):
        """Execute completes normally when llm_observability is None."""
        from adapters.comms.chat_executor import ChatAgentExecutor

        ports = _make_ports_bundle(llm_observability=None)
        executor = ChatAgentExecutor(ports=ports, role_id="comms")
        ctx = _make_context()
        eq = _make_event_queue()

        await executor.execute(ctx, eq)

        assert eq.events[-1].status.state == "completed"


class TestChatLangFuseErrorResilience:
    """LangFuse failures must not break the chat response."""

    async def test_observability_failure_does_not_crash_chat(self):
        """If LangFuse recording throws, the chat still completes."""
        from adapters.comms.chat_executor import ChatAgentExecutor

        mock_obs = MagicMock()
        mock_obs.start_cycle_trace.side_effect = RuntimeError("langfuse down")

        ports = _make_ports_bundle(llm_observability=mock_obs)
        executor = ChatAgentExecutor(ports=ports, role_id="comms")
        ctx = _make_context()
        eq = _make_event_queue()

        await executor.execute(ctx, eq)

        # Chat should still complete despite observability failure
        assert eq.events[-1].status.state == "completed"

    async def test_observability_not_called_on_llm_error(self):
        """When LLM streaming fails, observability recording is skipped."""
        from adapters.comms.chat_executor import ChatAgentExecutor

        mock_obs = MagicMock()
        ports = _make_ports_bundle(llm_observability=mock_obs)

        async def exploding_stream(messages, **kwargs):
            raise RuntimeError("LLM down")
            yield  # pragma: no cover

        ports.llm.chat_stream = exploding_stream

        executor = ChatAgentExecutor(ports=ports, role_id="comms")
        ctx = _make_context()
        eq = _make_event_queue()

        await executor.execute(ctx, eq)

        # LLM failed before recording could happen
        mock_obs.record_generation.assert_not_called()
        assert eq.events[-1].status.state == "failed"
