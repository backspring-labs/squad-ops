"""Tests for ChatAgentExecutor (SIP-0085 Phase 2)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_ports_bundle(
    *,
    stream_chunks: list[str] | None = None,
    system_prompt: str = "You are a test agent.",
    memory_results: list | None = None,
):
    """Build a mock PortsBundle for executor tests."""
    from squadops.prompts.models import AssembledPrompt

    bundle = MagicMock()

    # LLM — mock chat_stream as an async generator
    chunks = stream_chunks if stream_chunks is not None else ["hello", " world"]

    async def fake_chat_stream(messages, **kwargs):
        for c in chunks:
            yield c

    bundle.llm = MagicMock()
    bundle.llm.chat_stream = fake_chat_stream

    # Prompt service
    bundle.prompt_service = MagicMock()
    bundle.prompt_service.get_system_prompt.return_value = AssembledPrompt(
        content=system_prompt,
        fragment_hashes=(),
        assembly_hash="test",
        role="test",
        hook="agent_start",
        version="1",
    )

    # Memory — async mock
    bundle.memory = AsyncMock()
    bundle.memory.search = AsyncMock(return_value=memory_results or [])
    bundle.memory.store = AsyncMock()

    return bundle


def _make_context(user_text: str = "hi", task_id: str = "t1", context_id: str = "ctx1"):
    """Build a mock RequestContext."""
    ctx = MagicMock()
    ctx.get_user_input.return_value = user_text
    ctx.task_id = task_id
    ctx.context_id = context_id
    return ctx


def _make_event_queue():
    """Build a mock EventQueue that records enqueued events."""
    eq = MagicMock()
    eq.events = []

    async def capture(event):
        eq.events.append(event)

    eq.enqueue_event = capture
    return eq


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestChatAgentExecutorStreaming:
    """Executor streams LLM chunks as A2A events."""

    async def test_streams_chunks_then_completes(self):
        """Each LLM chunk becomes a working event; final event is completed."""
        from adapters.comms.chat_executor import ChatAgentExecutor

        ports = _make_ports_bundle(stream_chunks=["one", "two", "three"])
        executor = ChatAgentExecutor(ports=ports, role_id="comms")
        ctx = _make_context(user_text="hello")
        eq = _make_event_queue()

        await executor.execute(ctx, eq)

        # 3 working chunks + 1 completed = 4 events
        assert len(eq.events) == 4

        # First 3 are working
        for i in range(3):
            assert eq.events[i].status.state == "working"
            assert eq.events[i].final is False

        # Last is completed
        assert eq.events[3].status.state == "completed"
        assert eq.events[3].final is True

    async def test_completed_event_contains_full_response(self):
        """The final completed event has the full concatenated response."""
        from adapters.comms.chat_executor import ChatAgentExecutor

        ports = _make_ports_bundle(stream_chunks=["hello", " ", "world"])
        executor = ChatAgentExecutor(ports=ports, role_id="dev")
        ctx = _make_context()
        eq = _make_event_queue()

        await executor.execute(ctx, eq)

        final_event = eq.events[-1]
        # Extract text from the A2A message
        text = final_event.status.message.parts[0].root.text
        assert text == "hello world"

    async def test_empty_stream_sends_completed_with_empty_text(self):
        """Zero chunks from LLM still produces a completed event with empty text."""
        from adapters.comms.chat_executor import ChatAgentExecutor

        ports = _make_ports_bundle(stream_chunks=[])
        executor = ChatAgentExecutor(ports=ports, role_id="comms")
        ctx = _make_context()
        eq = _make_event_queue()

        await executor.execute(ctx, eq)

        # Only the completed event (no working events)
        assert len(eq.events) == 1
        assert eq.events[0].status.state == "completed"
        assert eq.events[0].final is True
        text = eq.events[0].status.message.parts[0].root.text
        assert text == ""


class TestChatAgentExecutorRoleGeneric:
    """Executor is role-generic (P2-RC1) — identity from prompt_service."""

    @pytest.mark.parametrize("role_id", ["comms", "dev", "qa"])
    async def test_system_prompt_uses_role_id_and_injects_content(self, role_id):
        """get_system_prompt() called with role_id and content appears in LLM messages."""
        from adapters.comms.chat_executor import ChatAgentExecutor

        prompt_text = f"You are the {role_id} agent."
        ports = _make_ports_bundle(system_prompt=prompt_text)

        # Capture messages sent to LLM
        captured_messages: list = []

        async def capturing_stream(messages, **kwargs):
            captured_messages.extend(messages)
            yield "ok"

        ports.llm.chat_stream = capturing_stream

        executor = ChatAgentExecutor(ports=ports, role_id=role_id)
        ctx = _make_context()
        eq = _make_event_queue()

        await executor.execute(ctx, eq)

        ports.prompt_service.get_system_prompt.assert_called_once_with(role_id)
        # System prompt content injected into first message
        assert prompt_text in captured_messages[0].content
        assert eq.events[-1].status.state == "completed"


class TestChatAgentExecutorErrorHandling:
    """Error paths in executor."""

    async def test_llm_error_sends_failed_event(self):
        """If LLM streaming raises, a failed event is emitted."""
        from adapters.comms.chat_executor import ChatAgentExecutor

        ports = _make_ports_bundle()

        async def exploding_stream(messages, **kwargs):
            raise RuntimeError("LLM exploded")
            yield  # pragma: no cover

        ports.llm.chat_stream = exploding_stream

        executor = ChatAgentExecutor(ports=ports, role_id="comms")
        ctx = _make_context()
        eq = _make_event_queue()

        await executor.execute(ctx, eq)

        assert len(eq.events) == 1
        assert eq.events[0].status.state == "failed"
        assert eq.events[0].final is True

    async def test_prompt_service_failure_sends_failed_event(self):
        """If prompt assembly fails, a failed event is emitted (no silent fallback)."""
        from adapters.comms.chat_executor import ChatAgentExecutor

        ports = _make_ports_bundle()
        ports.prompt_service.get_system_prompt.side_effect = RuntimeError("no fragments")

        executor = ChatAgentExecutor(ports=ports, role_id="comms")
        ctx = _make_context()
        eq = _make_event_queue()

        await executor.execute(ctx, eq)

        # Should fail — no hardcoded fallback masking missing config
        assert len(eq.events) == 1
        assert eq.events[0].status.state == "failed"
        assert eq.events[0].final is True

    async def test_cancel_sends_canceled_event(self):
        """cancel() emits a canceled event."""
        from adapters.comms.chat_executor import ChatAgentExecutor

        ports = _make_ports_bundle()
        executor = ChatAgentExecutor(ports=ports, role_id="comms")
        ctx = _make_context(task_id="t-cancel")
        eq = _make_event_queue()

        await executor.cancel(ctx, eq)

        assert len(eq.events) == 1
        assert eq.events[0].status.state == "canceled"
        assert eq.events[0].final is True


class TestChatAgentExecutorMemory:
    """Memory integration (best-effort, P2-RC4)."""

    async def test_memory_search_failure_does_not_crash(self):
        """Memory search failure is swallowed (best-effort)."""
        from adapters.comms.chat_executor import ChatAgentExecutor

        ports = _make_ports_bundle()
        ports.memory.search = AsyncMock(side_effect=RuntimeError("memory down"))

        executor = ChatAgentExecutor(ports=ports, role_id="comms")
        ctx = _make_context()
        eq = _make_event_queue()

        await executor.execute(ctx, eq)

        # Should still complete despite memory failure
        assert eq.events[-1].status.state == "completed"

    async def test_memory_store_failure_does_not_crash(self):
        """Memory store failure is swallowed (best-effort)."""
        from adapters.comms.chat_executor import ChatAgentExecutor

        ports = _make_ports_bundle()
        ports.memory.store = AsyncMock(side_effect=RuntimeError("memory write failed"))

        executor = ChatAgentExecutor(ports=ports, role_id="comms")
        ctx = _make_context(user_text="Please remember this: deploy on Friday")
        eq = _make_event_queue()

        await executor.execute(ctx, eq)

        # Should still complete despite store failure
        assert eq.events[-1].status.state == "completed"

    @pytest.mark.parametrize(
        "user_text",
        [
            "Please remember this: the deploy is on Friday",
            "Note that the API changed",
            "Save this for later: new endpoint /v2",
            "Store this: credentials rotated",
        ],
    )
    async def test_memory_store_on_explicit_intent(self, user_text):
        """Memory.store() called with correct content when user triggers storage."""
        from adapters.comms.chat_executor import ChatAgentExecutor

        ports = _make_ports_bundle()
        executor = ChatAgentExecutor(ports=ports, role_id="comms")
        ctx = _make_context(user_text=user_text)
        eq = _make_event_queue()

        await executor.execute(ctx, eq)

        ports.memory.store.assert_called_once()
        stored_entry = ports.memory.store.call_args[0][0]
        assert user_text in stored_entry.content
        assert "chat" in stored_entry.tags
        assert "comms" in stored_entry.tags

    @pytest.mark.parametrize(
        "user_text",
        [
            "What is the status of the current cycle?",
            "I remember that meeting",  # contains "remember" but not "remember this"
        ],
    )
    async def test_no_memory_store_without_trigger(self, user_text):
        """Memory.store() NOT called for regular conversation or partial matches."""
        from adapters.comms.chat_executor import ChatAgentExecutor

        ports = _make_ports_bundle()
        executor = ChatAgentExecutor(ports=ports, role_id="comms")
        ctx = _make_context(user_text=user_text)
        eq = _make_event_queue()

        await executor.execute(ctx, eq)

        ports.memory.store.assert_not_called()

    async def test_memory_trigger_is_case_insensitive(self):
        """Trigger matching ignores case: 'REMEMBER THIS' works."""
        from adapters.comms.chat_executor import ChatAgentExecutor

        ports = _make_ports_bundle()
        executor = ChatAgentExecutor(ports=ports, role_id="comms")
        ctx = _make_context(user_text="REMEMBER THIS: deploy is Monday")
        eq = _make_event_queue()

        await executor.execute(ctx, eq)

        ports.memory.store.assert_called_once()

    async def test_memory_results_included_in_context(self):
        """When memory returns results, they are injected into the LLM messages."""
        from adapters.comms.chat_executor import ChatAgentExecutor
        from squadops.memory.models import MemoryEntry, MemoryResult

        memory_results = [
            MemoryResult(
                entry=MemoryEntry(content="Deploy is scheduled for Friday"),
                memory_id="m1",
                score=0.9,
            ),
        ]
        ports = _make_ports_bundle(memory_results=memory_results)

        # Capture LLM messages to verify memory injection
        captured_messages: list = []

        async def capturing_stream(messages, **kwargs):
            captured_messages.extend(messages)
            yield "ok"

        ports.llm.chat_stream = capturing_stream

        executor = ChatAgentExecutor(ports=ports, role_id="comms")
        ctx = _make_context(user_text="When is the deploy?")
        eq = _make_event_queue()

        await executor.execute(ctx, eq)

        # System message should contain memory context
        system_msg = captured_messages[0]
        assert "Deploy is scheduled for Friday" in system_msg.content
