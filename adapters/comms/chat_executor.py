"""Role-generic chat executor for A2A messaging (SIP-0085 Phase 2).

Implements the a2a-sdk AgentExecutor ABC. All SDK-specific types are
imported here (adapter-side). The executor is role-generic — identity
comes entirely from role_id → prompt_service.get_system_prompt(role_id).

Key design decisions (from plan runtime contracts):
- P2-RC1: Zero role-specific code. role_id drives identity via prompt_service.
- P2-RC4: Memory is best-effort and secondary to the chat loop.
- P2-RC5: History comes from the proxy (Phase 3), not A2A context.
"""

from __future__ import annotations

import logging
import time
import uuid
from typing import TYPE_CHECKING

from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue
from a2a.types import (
    TaskState,
    TaskStatus,
    TaskStatusUpdateEvent,
)
from a2a.utils import new_agent_text_message

from squadops.llm.models import ChatMessage

if TYPE_CHECKING:
    from squadops.agents.base import PortsBundle

logger = logging.getLogger(__name__)

# Maximum memory results per query (SIP-0085 v1 scope rule)
_MAX_MEMORY_RESULTS = 5

# Phrases that trigger explicit memory storage (case-insensitive substring match)
_MEMORY_TRIGGERS = ("remember this", "note that", "save this", "store this")


class ChatAgentExecutor(AgentExecutor):
    """Role-generic chat executor.

    Receives a PortsBundle and role_id at construction. On execute():
    1. Extracts user text from the A2A request context
    2. Assembles system prompt via prompt_service.get_system_prompt(role_id)
    3. Optionally retrieves relevant memories (best-effort, bounded)
    4. Streams response via ports.llm.chat_stream()
    5. Enqueues text chunks as A2A status update events
    """

    def __init__(self, *, ports: PortsBundle, role_id: str) -> None:
        self._ports = ports
        self._role_id = role_id

    async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:
        """Execute a chat request: stream LLM response as A2A events."""
        user_text = context.get_user_input()
        task_id = context.task_id
        context_id = context.context_id

        logger.info(
            "chat_message_received",
            extra={
                "role_id": self._role_id,
                "task_id": task_id,
                "user_text_len": len(user_text),
            },
        )

        try:
            # 1. Assemble system prompt from role identity
            system_content = self._get_system_prompt()

            # 2. Best-effort memory retrieval (non-blocking)
            memory_context = await self._retrieve_memories(user_text)

            # 3. Build message list for LLM
            messages = self._build_messages(system_content, memory_context, user_text)

            # 4. Stream response and enqueue chunks
            t0 = time.monotonic()
            full_response = await self._stream_response(
                messages,
                task_id,
                context_id,
                event_queue,
            )
            latency_ms = (time.monotonic() - t0) * 1000

            # 5. Best-effort memory write on explicit intent
            await self._maybe_store_memory(user_text, full_response)

            # 6. Record generation in LangFuse (SIP-0085 Phase 5)
            self._record_generation(
                context_id=context_id,
                task_id=task_id,
                prompt_text=system_content + memory_context + "\n\n" + user_text,
                response_text=full_response,
                latency_ms=latency_ms,
            )

            logger.info(
                "chat_response_complete",
                extra={
                    "role_id": self._role_id,
                    "task_id": task_id,
                    "response_len": len(full_response),
                    "latency_ms": round(latency_ms, 1),
                },
            )

        except Exception:
            logger.exception(
                "chat_execution_failed",
                extra={"role_id": self._role_id, "task_id": task_id},
            )
            # Send error as final status
            await event_queue.enqueue_event(
                TaskStatusUpdateEvent(
                    task_id=task_id,
                    context_id=context_id,
                    kind="status-update",
                    status=TaskStatus(
                        state=TaskState.failed,
                        message=new_agent_text_message(
                            "I encountered an error processing your request.",
                            context_id=context_id,
                            task_id=task_id,
                        ),
                    ),
                    final=True,
                )
            )

    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        """Handle cancellation request."""
        logger.info(
            "chat_cancelled",
            extra={"role_id": self._role_id, "task_id": context.task_id},
        )
        await event_queue.enqueue_event(
            TaskStatusUpdateEvent(
                task_id=context.task_id,
                context_id=context.context_id,
                kind="status-update",
                status=TaskStatus(state=TaskState.canceled),
                final=True,
            )
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_system_prompt(self) -> str:
        """Assemble system prompt for this role.

        Raises on failure — the outer execute() catches and sends a failed event.
        Per project rules: no hardcoded fallbacks that mask missing config.
        """
        assembled = self._ports.prompt_service.get_system_prompt(self._role_id)
        return assembled.content

    async def _retrieve_memories(self, query: str) -> str:
        """Best-effort memory retrieval, bounded to _MAX_MEMORY_RESULTS."""
        try:
            from squadops.memory.models import MemoryQuery

            results = await self._ports.memory.search(
                MemoryQuery(text=query, limit=_MAX_MEMORY_RESULTS),
            )
            if results:
                entries = [r.entry.content for r in results if r.entry.content]
                if entries:
                    return "\n\nRelevant context from memory:\n" + "\n---\n".join(entries)
        except Exception:
            logger.debug("Memory retrieval failed (best-effort), continuing without")
        return ""

    def _build_messages(
        self,
        system_content: str,
        memory_context: str,
        user_text: str,
    ) -> list[ChatMessage]:
        """Build the message list for the LLM."""
        system_text = system_content
        if memory_context:
            system_text += memory_context

        return [
            ChatMessage(role="system", content=system_text),
            ChatMessage(role="user", content=user_text),
        ]

    async def _stream_response(
        self,
        messages: list[ChatMessage],
        task_id: str,
        context_id: str,
        event_queue: EventQueue,
    ) -> str:
        """Stream LLM response and enqueue A2A events. Returns full text."""
        collected: list[str] = []

        async for chunk in self._ports.llm.chat_stream(messages):
            collected.append(chunk)
            # Emit working status with current chunk
            await event_queue.enqueue_event(
                TaskStatusUpdateEvent(
                    task_id=task_id,
                    context_id=context_id,
                    kind="status-update",
                    status=TaskStatus(
                        state=TaskState.working,
                        message=new_agent_text_message(
                            chunk,
                            context_id=context_id,
                            task_id=task_id,
                        ),
                    ),
                    final=False,
                )
            )

        full_response = "".join(collected)

        # Emit completed status with full response
        await event_queue.enqueue_event(
            TaskStatusUpdateEvent(
                task_id=task_id,
                context_id=context_id,
                kind="status-update",
                status=TaskStatus(
                    state=TaskState.completed,
                    message=new_agent_text_message(
                        full_response,
                        context_id=context_id,
                        task_id=task_id,
                    ),
                ),
                final=True,
            )
        )

        return full_response

    def _record_generation(
        self,
        *,
        context_id: str,
        task_id: str,
        prompt_text: str,
        response_text: str,
        latency_ms: float,
    ) -> None:
        """Record chat generation in LangFuse (best-effort, non-blocking)."""
        llm_obs = self._ports.llm_observability
        if llm_obs is None:
            return

        try:
            from squadops.telemetry.models import (
                CorrelationContext,
                GenerationRecord,
                PromptLayer,
                PromptLayerMetadata,
            )

            ctx = CorrelationContext(
                cycle_id=f"chat-{context_id}",
                task_id=f"chat-{task_id}",
                agent_id=self._role_id,
                agent_role=self._role_id,
            )
            record = GenerationRecord(
                generation_id=str(uuid.uuid4()),
                model=self._ports.llm.default_model,
                prompt_text=prompt_text,
                response_text=response_text,
                latency_ms=latency_ms,
            )
            layers = PromptLayerMetadata(
                prompt_layer_set_id=f"{self._role_id}-chat",
                layers=(
                    PromptLayer(layer_type="system", layer_id=f"{self._role_id}-system"),
                    PromptLayer(layer_type="user", layer_id="console-chat"),
                ),
            )
            llm_obs.start_cycle_trace(ctx)
            llm_obs.start_task_span(ctx)
            llm_obs.record_generation(ctx, record, layers)
            llm_obs.end_task_span(ctx)
            llm_obs.end_cycle_trace(ctx)
            llm_obs.flush()
        except Exception:
            logger.debug("LangFuse recording failed (best-effort)", exc_info=True)

    async def _maybe_store_memory(self, user_text: str, response: str) -> None:
        """Store memory only on explicit user intent."""
        lower = user_text.lower()
        if not any(trigger in lower for trigger in _MEMORY_TRIGGERS):
            return

        try:
            from squadops.memory.models import MemoryEntry

            entry = MemoryEntry(
                content=f"User: {user_text}\nAssistant: {response}",
                tags=("chat", self._role_id),
            )
            await self._ports.memory.store(entry)
            logger.info("Stored chat memory", extra={"role_id": self._role_id})
        except Exception:
            logger.debug("Memory store failed (best-effort), continuing")
