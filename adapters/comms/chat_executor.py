"""Role-generic chat executor for A2A messaging (SIP-0085 Phase 2).

Implements the a2a-sdk AgentExecutor ABC. All SDK-specific types are
imported here (adapter-side). The executor is role-generic — identity
comes entirely from role_id → prompt_service.get_system_prompt(role_id).

Key design decisions (from plan runtime contracts):
- P2-RC1: Zero role-specific code. role_id drives identity via prompt_service.
- P2-RC4, superseded: chat neither recalls nor stores. The legacy agent store is retired
  (SIP-0110 §A.4.3: dormant in #2174, removed in #2184). The runtime API assembles each turn's
  memory context from the records and sends it in the message's metadata (#2180); this executor
  renders it through a managed template and owns no memory. A capture is only ever proposed here: the person confirms it.
- P2-RC5: History comes from the proxy (Phase 3), not A2A context: the runtime API sends a
  session's earlier turns, bounded, in the message's metadata (#2175).
"""

from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING

from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue
from a2a.types import (
    TaskState,
    TaskStatus,
    TaskStatusUpdateEvent,
)
from a2a.utils import new_agent_text_message

from squadops.comms.chat_history import (
    HISTORY_DROPPED_KEY,
    HISTORY_KEY,
    HISTORY_ROLES,
    HISTORY_UNAVAILABLE_KEY,
    MEMORY_CONTEXT_KEY,
)
from squadops.llm.models import ChatMessage
from squadops.memory.chat import RENDER_FAILURE_NOTICE, memory_lines

if TYPE_CHECKING:
    from squadops.agents.base import PortsBundle

logger = logging.getLogger(__name__)


class ChatAgentExecutor(AgentExecutor):
    """Role-generic chat executor.

    Receives a PortsBundle and role_id at construction. On execute():
    1. Extracts user text from the A2A request context
    2. Assembles system prompt via prompt_service.get_system_prompt(role_id)
    3. Streams response via ports.llm.chat_stream()
    4. Enqueues text chunks as A2A status update events
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
            # 1. Assemble system prompt from role identity, then the turn's memory (#2180)
            system_content = self._get_system_prompt()
            memory, unshown = await self._memory_section(context)
            if memory:
                system_content = f"{system_content}\n\n{memory}"

            # 2. Build message list for LLM: the session's earlier turns, then this one
            messages = self._build_messages(system_content, self._history(context), user_text)

            # 3. Stream response and enqueue chunks
            t0 = time.monotonic()
            full_response = await self._stream_response(
                messages,
                task_id,
                context_id,
                event_queue,
                # A context it was handed and couldn't show is said in the reply (#2180).
                prefix=RENDER_FAILURE_NOTICE if unshown else "",
            )
            latency_ms = (time.monotonic() - t0) * 1000

            # 4. Record generation in LangFuse (SIP-0085 Phase 5)
            self._record_generation(
                context_id=context_id,
                task_id=task_id,
                prompt_text="\n\n".join(m.content for m in messages),
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

    async def _memory_section(self, context: RequestContext) -> tuple[str, bool]:
        """The turn's memory context, rendered through ``request.chat_memory_context``, and whether
        a context was handed and couldn't be shown. ``("", False)`` when the turn carried none (no
        records store on the runtime). A render that fails is logged at WARNING, and the reply says
        it was answered without the records."""
        metadata = getattr(context.message, "metadata", None)
        handed = metadata.get(MEMORY_CONTEXT_KEY) if isinstance(metadata, dict) else None
        if not isinstance(handed, dict):
            return "", False
        renderer = self._ports.request_renderer
        if renderer is None:
            logger.warning("chat_memory_not_rendered: no request renderer")
            return "", True
        try:
            rendered = await renderer.render(
                "request.chat_memory_context", {"memory_lines": memory_lines(handed)}
            )
        except Exception:
            logger.warning("chat_memory_not_rendered", exc_info=True)
            return "", True
        return rendered.content.strip("\n"), False

    def _history(self, context: RequestContext) -> list[ChatMessage]:
        """The earlier turns the proxy sent with this one (#2175), oldest first. A turn sent
        without them (no session yet) has none."""
        metadata = getattr(context.message, "metadata", None)
        if not isinstance(metadata, dict):
            return []
        turns = [
            ChatMessage(role=t["role"], content=t["content"])
            for t in metadata.get(HISTORY_KEY) or []
            if isinstance(t, dict)
            and t.get("role") in HISTORY_ROLES
            and isinstance(t.get("content"), str)
        ]
        logger.info(
            "chat_history_received",
            extra={
                "role_id": self._role_id,
                "turns": len(turns),
                "dropped": metadata.get(HISTORY_DROPPED_KEY, 0),
                "unavailable": bool(metadata.get(HISTORY_UNAVAILABLE_KEY)),
            },
        )
        return turns

    def _build_messages(
        self, system_content: str, history: list[ChatMessage], user_text: str
    ) -> list[ChatMessage]:
        """Build the message list for the LLM."""
        return [
            ChatMessage(role="system", content=system_content),
            *history,
            ChatMessage(role="user", content=user_text),
        ]

    async def _stream_response(
        self,
        messages: list[ChatMessage],
        task_id: str,
        context_id: str,
        event_queue: EventQueue,
        prefix: str = "",
    ) -> str:
        """Stream LLM response and enqueue A2A events, after ``prefix`` when one is given (a
        disclosure the reply opens with). Returns full text."""
        collected: list[str] = []

        async def chunks():
            if prefix:
                yield prefix
            async for chunk in self._ports.llm.chat_stream(messages):
                yield chunk

        async for chunk in chunks():
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
                PromptLayer,
                PromptLayerMetadata,
                build_generation_record,
            )

            ctx = CorrelationContext(
                cycle_id=f"chat-{context_id}",
                task_id=f"chat-{task_id}",
                agent_id=self._role_id,
                agent_role=self._role_id,
            )
            # usage=None: this recorder is handed text and a latency by its caller,
            # never the response object, so there are no token counts to report here.
            record = build_generation_record(
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
