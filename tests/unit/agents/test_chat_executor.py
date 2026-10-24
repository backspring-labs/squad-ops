"""Tests for ChatAgentExecutor (SIP-0085 Phase 2)."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_ports_bundle(
    *,
    stream_chunks: list[str] | None = None,
    system_prompt: str = "You are a test agent.",
):
    """Build a mock PortsBundle for executor tests, shaped by the bundle itself: a port the bundle
    doesn't carry (a memory store, since #2184) is an ``AttributeError``, not a fresh mock."""
    from squadops.agents.base import PortsBundle
    from squadops.prompts.models import AssembledPrompt

    bundle = MagicMock(spec=PortsBundle)

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


class TestChatHoldsNoStore:
    """SIP-0110 §A.4.3: the legacy agent store is retired (dormant in #2174, removed in #2184).
    Chat neither recalls nor stores: the runtime API sends each turn's memory context (#2180)."""

    @pytest.mark.parametrize(
        "user_text", ["Please remember this: the deploy is on Friday", "When is the deploy?"]
    )
    async def test_chat_answers_without_reaching_a_store(self, user_text):
        """Entered at ``execute``, with a bundle shaped as the agents' ``PortsBundle``, which has
        no memory port. Bugs caught: a "remember this" trigger or a recall reaching for a store
        the agents no longer hold (an ``AttributeError`` on the bundle, which fails the turn); or
        the turn's messages carrying anything beside the identity and the user's text."""
        from adapters.comms.chat_executor import ChatAgentExecutor

        captured: list = []

        async def capturing_stream(messages, **kwargs):
            captured.extend(messages)
            yield "ok"

        ports = _make_ports_bundle()
        ports.llm.chat_stream = capturing_stream
        executor = ChatAgentExecutor(ports=ports, role_id="comms")
        eq = _make_event_queue()

        await executor.execute(_make_context(user_text=user_text), eq)

        assert eq.events[-1].status.state == "completed"
        assert [(m.role, m.content) for m in captured] == [
            ("system", "You are a test agent."),
            ("user", user_text),
        ]


class TestTheTurnsHistory:
    """P2-RC5 (#2175): the proxy sends a session's earlier turns in the message's metadata, and
    the agent answers inside that conversation."""

    async def test_the_sent_turns_come_between_the_identity_and_this_turn(self):
        """Entered at ``execute``. Bugs caught: the history ignored, so every turn is a first; the
        turns reordered; or something that is not conversation replayed as a turn."""
        from adapters.comms.chat_executor import ChatAgentExecutor

        captured: list = []

        async def capturing_stream(messages, **kwargs):
            captured.extend(messages)
            yield "ok"

        ports = _make_ports_bundle()
        ports.llm.chat_stream = capturing_stream
        ctx = _make_context(user_text="third")
        ctx.message.metadata = {
            "history": [
                {"role": "user", "content": "first"},
                {"role": "system", "content": "not a turn"},
                {"role": "assistant", "content": "second"},
            ],
            "history_dropped": 0,
            "history_unavailable": False,
        }

        await ChatAgentExecutor(ports=ports, role_id="comms").execute(ctx, _make_event_queue())

        assert [(m.role, m.content) for m in captured] == [
            ("system", "You are a test agent."),
            ("user", "first"),
            ("assistant", "second"),
            ("user", "third"),
        ]


class TestTheTurnsMemory:
    """#2180: the runtime API sends each turn's memory context in the message's metadata, and the
    agent renders it through ``request.chat_memory_context``, owning no memory itself."""

    async def test_the_memory_context_is_rendered_after_the_identity_through_the_shipped_template(
        self,
    ):
        """Entered at ``execute`` with the filesystem renderer and the shipped asset. Bugs caught:
        the context sent and never shown, a failed section shown as none, or the capture protocol
        missing, so a "remember this" is answered as saved when nothing was."""
        from adapters.comms.chat_executor import ChatAgentExecutor
        from adapters.prompts.factory import create_prompt_asset_source
        from squadops.prompts.renderer import RequestTemplateRenderer

        captured: list = []

        async def capturing_stream(messages, **kwargs):
            captured.extend(messages)
            yield "ok"

        ports = _make_ports_bundle()
        ports.llm.chat_stream = capturing_stream
        ports.request_renderer = RequestTemplateRenderer(
            create_prompt_asset_source(provider="filesystem")
        )
        ctx = _make_context(user_text="what do we know?")
        ctx.message.metadata = {
            "history": [],
            "memory_context": {
                "project_id": "group_run",
                "sections": [
                    {
                        "kind": "notes",
                        "entries": [{"record_id": "m", "revision": 1, "scope": "project",
                                     "text": "the join returns 409 when full"}],
                        "omitted": 1,
                    }
                ],
                "unavailable": ["preferences"],
            },
        }  # fmt: skip

        await ChatAgentExecutor(ports=ports, role_id="comms").execute(ctx, _make_event_queue())

        system = captured[0].content
        assert system.startswith("You are a test agent.\n\n## WHAT THIS CONVERSATION REMEMBERS")
        assert "1. (project) the join returns 409 when full" in system
        assert "(1 more left out for space.)" in system
        assert "Couldn't be read for this turn: preferences" in system
        assert "<memory-capture>" in system

    async def test_a_turn_without_a_memory_context_keeps_the_identity_alone(self):
        """Bug caught: a runtime with no records store still getting the capture protocol, so the
        agent proposes captures that can't be saved."""
        from adapters.comms.chat_executor import ChatAgentExecutor

        captured: list = []

        async def capturing_stream(messages, **kwargs):
            captured.extend(messages)
            yield "ok"

        ports = _make_ports_bundle()
        ports.llm.chat_stream = capturing_stream
        ctx = _make_context()
        ctx.message.metadata = {"history": []}

        await ChatAgentExecutor(ports=ports, role_id="comms").execute(ctx, _make_event_queue())

        assert captured[0].content == "You are a test agent."

    async def test_a_context_the_agent_couldnt_render_is_said_in_the_reply(self):
        """The second read of PR #2517. Bug caught: a render failure answered silently, while the
        runtime's exposure says the records were supplied."""
        from adapters.comms.chat_executor import ChatAgentExecutor
        from squadops.memory.chat import RENDER_FAILURE_NOTICE

        class Broken:
            async def render(self, template_id, variables):
                raise RuntimeError("asset missing")

        ports = _make_ports_bundle(stream_chunks=["the answer"])
        ports.request_renderer = Broken()
        ctx = _make_context()
        ctx.message.metadata = {"memory_context": {"project_id": None, "sections": []}}
        queue = _make_event_queue()

        await ChatAgentExecutor(ports=ports, role_id="comms").execute(ctx, queue)

        final = queue.events[-1].status.message.parts[0].root.text
        assert final == RENDER_FAILURE_NOTICE + "the answer"
