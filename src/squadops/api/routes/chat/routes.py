"""Chat API routes for console messaging (SIP-0085 Phase 3).

P3-RC1: Proxy, not processor — routes forward to agent A2A endpoint.
P3-RC4: POST returns StreamingResponse with text/event-stream.
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

from squadops.api.routes.chat.dtos import (
    ChatMessageDTO,
    ChatMessageRequest,
    ChatSessionDTO,
    MessagingAgentDTO,
)
from squadops.api.routes.chat.errors import handle_chat_error
from squadops.comms.models import (
    AgentNotFoundError,
    AgentNotMessagingEnabledError,
    ChatError,
    ChatMessage,
    ChatSession,
    SessionNotFoundError,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/chat", tags=["chat"])
agents_router = APIRouter(prefix="/api/agents", tags=["chat"])


# =============================================================================
# Dependency accessors (module-level singletons, set at startup)
# =============================================================================

# These are set by set_chat_ports() in deps.py
_chat_repo = None
_chat_cache = None
_a2a_client = None
_all_agents: dict = {}  # agent_id → instance config dict (all agents)
_messaging_agents: dict = {}  # agent_id → instance config dict (messaging-enabled only)


def _get_chat_repo():
    if _chat_repo is None:
        raise RuntimeError("ChatRepository not configured")
    return _chat_repo


def _get_a2a_client():
    if _a2a_client is None:
        raise RuntimeError("A2AClientAdapter not configured")
    return _a2a_client


def _get_user_id(request: Request) -> str:
    """Extract user ID from auth context.

    Returns "anonymous" in dev mode when auth middleware is not attached.
    Logs a warning so this doesn't silently mask a misconfigured auth setup.
    """
    identity = getattr(request.state, "identity", None)
    if identity and hasattr(identity, "user_id"):
        return identity.user_id
    logger.debug("No auth identity on request — using anonymous user ID")
    return "anonymous"


def _resolve_agent(agent_id: str) -> dict:
    """Resolve agent config and validate messaging is enabled.

    Uses _all_agents for existence check and _messaging_agents for
    messaging-enabled validation, so 404 vs 400 are distinguishable.

    Raises:
        AgentNotFoundError: Agent not found in instances config.
        AgentNotMessagingEnabledError: Agent exists but messaging not enabled.
    """
    if agent_id not in _all_agents:
        raise AgentNotFoundError(f"Agent not found: {agent_id}")
    if agent_id not in _messaging_agents:
        raise AgentNotMessagingEnabledError(f"Agent '{agent_id}' does not have messaging enabled")
    return _messaging_agents[agent_id]


# =============================================================================
# Routes
# =============================================================================


@router.post("/{agent_id}")
async def send_chat_message(
    agent_id: str,
    body: ChatMessageRequest,
    request: Request,
):
    """Send a message to an agent and stream the response (P3-RC1, P3-RC4).

    1. Validates agent has a2a_messaging_enabled
    2. Resolves or creates session
    3. Persists user message (Postgres required, Redis best-effort)
    4. Forwards assembled message to agent via A2AClientAdapter
    5. Returns StreamingResponse relaying agent chunks
    6. On stream completion, persists agent response
    """
    try:
        agent_config = _resolve_agent(agent_id)
    except ChatError as e:
        raise handle_chat_error(e) from e

    user_id = _get_user_id(request)
    chat_repo = _get_chat_repo()
    a2a_client = _get_a2a_client()

    # Resolve or create session
    now = datetime.now(UTC)
    if body.session_id:
        session_id = body.session_id
        # Verify session exists — catch specific error, let DB errors propagate as 500
        try:
            await chat_repo.get_session(session_id)
        except SessionNotFoundError as e:
            raise handle_chat_error(e) from e
    else:
        session_id = str(uuid.uuid4())
        session = ChatSession(
            session_id=session_id,
            agent_id=agent_id,
            user_id=user_id,
            started_at=now,
        )
        await chat_repo.create_session(session)
        logger.info(
            "chat_session_created",
            extra={"agent_id": agent_id, "user_id": user_id, "session_id": session_id},
        )

    # Persist user message (Postgres required — P3-RC2)
    user_msg = ChatMessage(
        message_id=str(uuid.uuid4()),
        session_id=session_id,
        role="user",
        content=body.message,
        created_at=now,
    )
    await chat_repo.store_message(user_msg)

    # Best-effort Redis cache
    if _chat_cache is not None:
        await _chat_cache.cache_message(user_msg)

    # Build agent A2A URL — fields are required in validated instance config
    a2a_port = agent_config["a2a_port"]
    a2a_host = agent_config["a2a_host"]
    base_url = f"http://{a2a_host}:{a2a_port}"

    # Stream response from agent
    async def event_stream():
        """Relay agent SSE chunks, then persist assembled response."""
        collected_chunks = []
        try:
            async for chunk in a2a_client.send_message_stream(
                base_url,
                body.message,
                context_id=session_id,
            ):
                collected_chunks.append(chunk)
                # SSE format: data line + blank line
                yield f"data: {json.dumps({'text': chunk, 'session_id': session_id})}\n\n"

            # Stream complete — persist agent response (P3-RC2: Postgres required)
            full_response = "".join(collected_chunks)
            if full_response:
                assistant_msg = ChatMessage(
                    message_id=str(uuid.uuid4()),
                    session_id=session_id,
                    role="assistant",
                    content=full_response,
                    created_at=datetime.now(UTC),
                )
                try:
                    await chat_repo.store_message(assistant_msg)
                    if _chat_cache is not None:
                        await _chat_cache.cache_message(assistant_msg)
                except Exception:
                    logger.error(
                        "chat_persistence_failed",
                        extra={"session_id": session_id, "agent_id": agent_id},
                        exc_info=True,
                    )

            # Final event signals completion
            yield f"data: {json.dumps({'done': True, 'session_id': session_id})}\n\n"

        except Exception:
            logger.exception(
                "Agent stream error",
                extra={"agent_id": agent_id, "session_id": session_id},
            )
            yield f"data: {json.dumps({'error': 'Agent communication failed', 'session_id': session_id})}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Session-Id": session_id,
        },
    )


@router.get("/sessions/{session_id}/messages")
async def get_session_messages(session_id: str):
    """Get message history for a session, ordered chronologically."""
    chat_repo = _get_chat_repo()

    try:
        await chat_repo.get_session(session_id)
    except SessionNotFoundError as e:
        raise handle_chat_error(e) from e

    messages = await chat_repo.get_session_messages(session_id)
    return [
        ChatMessageDTO(
            message_id=m.message_id,
            session_id=m.session_id,
            role=m.role,
            content=m.content,
            created_at=m.created_at,
        )
        for m in messages
    ]


@router.get("/{agent_id}/sessions")
async def list_agent_sessions(agent_id: str, request: Request):
    """List chat sessions for an agent+user pair."""
    try:
        _resolve_agent(agent_id)
    except ChatError as e:
        raise handle_chat_error(e) from e

    user_id = _get_user_id(request)
    chat_repo = _get_chat_repo()
    sessions = await chat_repo.list_sessions(agent_id, user_id)

    return [
        ChatSessionDTO(
            session_id=s.session_id,
            agent_id=s.agent_id,
            user_id=s.user_id,
            started_at=s.started_at,
            ended_at=s.ended_at,
        )
        for s in sessions
    ]


@agents_router.get("/messaging")
async def list_messaging_agents():
    """List all agents with messaging enabled."""
    return [
        MessagingAgentDTO(
            agent_id=cfg["id"],
            display_name=cfg["display_name"],
            description=cfg["description"],
            a2a_port=cfg["a2a_port"],
        )
        for cfg in _messaging_agents.values()
    ]


# =============================================================================
# History assembly (P3-RC3)
# =============================================================================


async def _load_history(session_id: str) -> list[dict]:
    """Load conversation history: Redis first, Postgres fallback.

    Returns list of {role, content} dicts for context assembly.
    Also repopulates Redis cache on miss (best-effort).
    """
    # Try Redis cache first
    if _chat_cache is not None:
        cached = await _chat_cache.get_messages(session_id)
        if cached is not None:
            return [{"role": m["role"], "content": m["content"]} for m in cached]

    # Postgres fallback
    chat_repo = _get_chat_repo()
    messages = await chat_repo.get_session_messages(session_id)

    history = [{"role": m.role, "content": m.content} for m in messages]

    # Repopulate Redis cache (best-effort)
    if _chat_cache is not None and messages:
        for m in messages:
            await _chat_cache.cache_message(m)

    return history
