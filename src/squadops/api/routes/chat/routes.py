"""Chat API routes for console messaging (SIP-0085 Phase 3).

P3-RC1: Proxy, not processor — routes forward to agent A2A endpoint.
P3-RC4: POST returns StreamingResponse with text/event-stream.

Chat on the memory substrate (SIP-0110 Appendix A §3.3–§3.6; #2180 stage A): a session is bound to a
project when it opens, server-side, and each turn carries the context this runtime assembles from the
records (``squadops.memory.chat``), with one exposure per turn. A capture the agent proposes is stored
only when the person confirms it (``POST /sessions/{id}/captures``), as one of the choices their
permissions allow. A person deletes their own sessions (Q29).
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException, Request, Response
from fastapi.responses import StreamingResponse

from squadops.api.errors import http_error, server_error
from squadops.api.routes.chat.context import ChatContextAssembly
from squadops.api.routes.chat.dtos import (
    CaptureChoiceDTO,
    CaptureRequest,
    CaptureResponse,
    ChatMessageDTO,
    ChatMessageRequest,
    ChatSessionDTO,
    MessagingAgentDTO,
)
from squadops.api.routes.chat.errors import handle_chat_error
from squadops.api.routes.memory.applicability import refuse_unmatched
from squadops.api.routes.memory.interventions import (
    dispatch_turn,
    log_intervention,
    of_campaign,
    refuse_dispatched,
    refuse_lesson_for_control,
    target_cycle,
    turn_of,
)
from squadops.api.runtime.deps import get_memory_records, get_memory_store, get_project_registry
from squadops.auth.models import Scope, scopes_for_roles
from squadops.comms.chat_history import (
    MEMORY_CONTEXT_KEY,
    BoundedHistory,
    bound_history,
    turn_metadata,
)
from squadops.comms.models import (
    AgentNotFoundError,
    AgentNotMessagingEnabledError,
    ChatMessage,
    ChatSession,
    SessionNotFoundError,
)
from squadops.cycles.models import ProjectNotFoundError
from squadops.memory.chat import (
    CaptureChoice,
    ChatLimits,
    ProposedCapture,
    capture_choices,
    failure_notice,
    offered_target,
    proposed_capture,
    used_line,
)
from squadops.memory.context import ChatTurn, ContextRequest, ProjectBound, Unbound
from squadops.memory.records import (
    InstructionApplicability,
    NotPermitted,
    RecordKind,
    RecordRefused,
    RecordScope,
    Revision,
    Source,
    SourceKind,
    TaskTarget,
    authorize_write,
    new_record,
)
from squadops.memory.task_instructions import LESSON_CITED

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/chat", tags=["chat"])
agents_router = APIRouter(prefix="/api/v1/agents", tags=["chat"])


# =============================================================================
# Dependency accessors — the app's own ports (#1448), assigned at startup
# =============================================================================


def _get_chat_repo(request: Request):
    chat_repo = request.app.state.chat_repo
    if chat_repo is None:
        raise RuntimeError("ChatRepository not configured")
    return chat_repo


def _get_a2a_client(request: Request):
    a2a_client = request.app.state.a2a_client
    if a2a_client is None:
        raise RuntimeError("A2AClientAdapter not configured")
    return a2a_client


def _chat_cache_of(request: Request):
    """The best-effort Redis cache, or None."""
    return request.app.state.chat_cache


def _all_agents(request: Request) -> dict:
    """agent_id → instance config dict, for every agent."""
    return request.app.state.all_agents or {}


def _messaging_agents(request: Request) -> dict:
    """agent_id → instance config dict, messaging-enabled agents only."""
    return request.app.state.messaging_agents or {}


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


def _viewer(request: Request) -> tuple[str, frozenset[str]]:
    """The signed-in person and their scopes, as the records' routes read them (§3.3: the same
    permissions through chat and through the API). Unauthenticated dev mode holds none."""
    identity = getattr(request.state, "identity", None)
    if identity is None or not hasattr(identity, "user_id"):
        return _get_user_id(request), frozenset()
    return identity.user_id, frozenset(identity.scopes) | scopes_for_roles(identity.roles)


def _resolve_agent(request: Request, agent_id: str) -> dict:
    """Resolve agent config and validate messaging is enabled.

    Uses _all_agents for existence check and _messaging_agents for
    messaging-enabled validation, so 404 vs 400 are distinguishable.

    Raises:
        AgentNotFoundError: Agent not found in instances config.
        AgentNotMessagingEnabledError: Agent exists but messaging not enabled.
    """
    messaging_agents = _messaging_agents(request)
    if agent_id not in _all_agents(request):
        raise AgentNotFoundError(f"Agent not found: {agent_id}")
    if agent_id not in messaging_agents:
        raise AgentNotMessagingEnabledError(f"Agent '{agent_id}' does not have messaging enabled")
    return messaging_agents[agent_id]


# =============================================================================
# Routes
# =============================================================================


@router.post("/{agent_id}", response_class=StreamingResponse)
async def send_chat_message(
    agent_id: str,
    body: ChatMessageRequest,
    request: Request,
) -> StreamingResponse:
    """Send a message to an agent and stream the response (P3-RC1, P3-RC4).

    1. Validates agent has a2a_messaging_enabled
    2. Resolves or creates session
    3. Persists user message (Postgres required, Redis best-effort)
    4. Forwards assembled message to agent via A2AClientAdapter
    5. Returns StreamingResponse relaying agent chunks
    6. On stream completion, persists agent response
    """
    agent_config = _resolve_agent(request, agent_id)

    user_id, scopes = _viewer(request)
    chat_repo = _get_chat_repo(request)
    a2a_client = _get_a2a_client(request)
    chat_cache = _chat_cache_of(request)

    # Resolve or create session
    now = datetime.now(UTC)
    session, history, history_unavailable = await _turn_session(
        request, body, agent_id=agent_id, user_id=user_id, scopes=scopes, now=now
    )
    session_id = session.session_id

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
    if chat_cache is not None:
        await chat_cache.cache_message(user_msg)

    # §3.5: the turn's memory context, assembled here, which owns the store; the agent renders it.
    memory = await _turn_memory(request, session, user_msg, scopes)
    unavailable = list((memory or {}).get("unavailable") or [])
    metadata = turn_metadata(history, unavailable=history_unavailable)
    if memory is not None:
        metadata[MEMORY_CONTEXT_KEY] = memory

    # Build agent A2A URL — fields are required in validated instance config
    a2a_port = agent_config["a2a_port"]
    a2a_host = agent_config["a2a_host"]
    base_url = f"http://{a2a_host}:{a2a_port}"

    # Stream response from agent
    async def event_stream():
        """Relay agent SSE chunks, then persist assembled response."""
        collected_chunks = []
        try:
            if unavailable:
                # §3.5: a part of the context that failed is said in the reply, and logged.
                logger.warning(
                    "chat_context_unavailable",
                    extra={"session_id": session_id, "sections": unavailable},
                )
                notice = failure_notice(unavailable)
                collected_chunks.append(notice)
                yield f"data: {json.dumps({'text': notice, 'session_id': session_id})}\n\n"
            async for chunk in a2a_client.send_message_stream(
                base_url,
                body.message,
                context_id=session_id,
                metadata=metadata,
            ):
                collected_chunks.append(chunk)
                # SSE format: data line + blank line
                yield f"data: {json.dumps({'text': chunk, 'session_id': session_id})}\n\n"
            used = used_line(memory) if memory is not None else ""
            if used:
                # §A.3.11: the reply names the records its context supplied.
                collected_chunks.append(used)
                yield f"data: {json.dumps({'text': used, 'session_id': session_id})}\n\n"

            # Stream complete — persist agent response (P3-RC2: Postgres required). A capture the
            # agent proposed is kept off the stored text and offered to the person; nothing is
            # stored as a record until they confirm it (§3.5).
            proposal, full_response = proposed_capture("".join(collected_chunks))
            capture = _offered(proposal, source=user_msg, session=session, scopes=scopes)
            if full_response:
                assistant_msg = ChatMessage(
                    message_id=str(uuid.uuid4()),
                    session_id=session_id,
                    role="assistant",
                    content=full_response,
                    created_at=datetime.now(UTC),
                    metadata={"capture_proposal": capture} if capture else {},
                )
                try:
                    await chat_repo.store_message(assistant_msg)
                    if chat_cache is not None:
                        await chat_cache.cache_message(assistant_msg)
                except Exception:
                    logger.error(
                        "chat_persistence_failed",
                        extra={"session_id": session_id, "agent_id": agent_id},
                        exc_info=True,
                    )

            if capture is not None:
                yield f"data: {json.dumps({'capture': capture, 'session_id': session_id})}\n\n"
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
async def get_session_messages(session_id: str, request: Request) -> list[ChatMessageDTO]:
    """Get message history for a session, ordered chronologically. Only its owner reads it."""
    chat_repo = _get_chat_repo(request)

    try:
        await _owned_session(chat_repo, session_id, _get_user_id(request))
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
async def list_agent_sessions(agent_id: str, request: Request) -> list[ChatSessionDTO]:
    """List chat sessions for an agent+user pair."""
    _resolve_agent(request, agent_id)

    user_id = _get_user_id(request)
    chat_repo = _get_chat_repo(request)
    sessions = await chat_repo.list_sessions(agent_id, user_id)

    return [
        ChatSessionDTO(
            session_id=s.session_id,
            agent_id=s.agent_id,
            user_id=s.user_id,
            started_at=s.started_at,
            ended_at=s.ended_at,
            project_id=s.project_id,
        )
        for s in sessions
    ]


@router.delete("/sessions/{session_id}", status_code=204, response_class=Response)
async def delete_chat_session(session_id: str, request: Request) -> Response:
    """Delete one of your sessions (SIP-0110 §A.8 Q29): its messages go, and a memory record already
    confirmed from it stays, marked as coming from a deleted session. Another person's session, or
    one already deleted, is refused as a missing one."""
    chat_repo = _get_chat_repo(request)
    try:
        await _owned_session(chat_repo, session_id, _get_user_id(request))
        await chat_repo.delete_session(session_id, datetime.now(UTC))
    except SessionNotFoundError as e:
        raise handle_chat_error(e) from e
    chat_cache = _chat_cache_of(request)
    if chat_cache is not None:
        await chat_cache.invalidate_session(session_id)
    logger.info("chat_session_deleted", extra={"session_id": session_id})
    return Response(status_code=204)


@router.get("/sessions/{session_id}/capture-choices")
async def list_capture_choices(session_id: str, request: Request) -> list[CaptureChoiceDTO]:
    """What a confirmation card may offer you in this session: the kinds and scopes you may write
    (§3.3). A card offers nothing else, and a capture of anything else is refused."""
    user_id, scopes = _viewer(request)
    try:
        session = await _owned_session(_get_chat_repo(request), session_id, user_id)
    except SessionNotFoundError as e:
        raise handle_chat_error(e) from e
    return [_choice_dto(c) for c in capture_choices(scopes=scopes, project_id=session.project_id)]


@router.post("/sessions/{session_id}/captures", status_code=201)
async def confirm_capture(
    session_id: str, body: CaptureRequest, request: Request
) -> CaptureResponse:
    """Store what you confirmed on a capture card (§3.5), as a record whose source is the turn it
    came from. Refused (403) for a kind or scope this session doesn't offer you; a save that fails
    is said in the reply, answered as an error and logged at WARNING, never swallowed."""
    user_id, scopes = _viewer(request)
    chat_repo = _get_chat_repo(request)
    try:
        session = await _owned_session(chat_repo, session_id, user_id)
    except SessionNotFoundError as e:
        raise handle_chat_error(e) from e
    turn = await chat_repo.get_message(body.message_id)
    if turn is None or turn.session_id != session_id:
        raise http_error(404, "NOT_FOUND", f"no message {body.message_id} in this session")
    offered = capture_choices(scopes=scopes, project_id=session.project_id)
    choice = next((c for c in offered if (c.kind, c.scope) == (body.kind, body.scope)), None)
    if choice is None:
        raise http_error(
            403,
            "FORBIDDEN",
            f"this session offers you no {body.scope} {body.kind}: "
            + ", ".join(f"{c.scope} {c.kind}" for c in offered),
        )
    applicability = _capture_applicability(choice, body)
    target = _capture_target(choice, body)
    # #2180: a task instruction captured in chat names an admitted cycle, so it is an
    # intervention, judged by the records API's own rules (§3.5).
    cycle = await target_cycle(request, choice.scope, choice.project_id, target)
    records = get_memory_records(request)
    now = datetime.now(UTC)
    try:
        if records is None:
            raise RuntimeError("the memory records' store is not configured")
        authorize_write(
            choice.kind, choice.scope, actor_id=user_id, actor_scopes=scopes, owner_id=user_id,
            campaign_cycle=of_campaign(cycle),
        )  # fmt: skip
        record = new_record(
            record_id=f"mrec_{uuid.uuid4().hex[:16]}",
            kind=choice.kind,
            scope=choice.scope,
            project_id=choice.project_id,
            owner_id=user_id,
            revision=Revision(
                number=1,
                body=body.text.strip(),
                author=user_id,
                created_at=now,
                source=Source(
                    SourceKind.CHAT_MESSAGE,
                    {
                        "session_id": session_id,
                        "message_id": body.message_id,
                        **({LESSON_CITED: body.lesson_revision} if body.lesson_revision else {}),
                    },
                ),
                confirmed_by=user_id,
                suggestion=body.suggestion,
                applicability=applicability,
                target=target,
            ),
        )
        # #2545: from the dispatched check to the write, no dispatch of the cycle composes.
        async with dispatch_turn(request, turn_of(cycle)):
            if cycle is not None:
                await refuse_lesson_for_control(request, cycle, record.current)
                await refuse_dispatched(request, cycle, target)
            await records.create(record)
    except NotPermitted as e:
        raise http_error(403, "FORBIDDEN", str(e)) from e
    except RecordRefused as e:
        raise http_error(422, "VALIDATION_ERROR", str(e)) from e
    except HTTPException:
        raise  # a refusal the rules gave, said as itself
    except Exception as e:
        # #1976: a server failure answers with the request id, never the exception's text, and the
        # transcript keeps only what failed.
        logger.warning("chat_capture_failed", extra={"session_id": session_id, "kind": choice.kind})
        request_id = getattr(request.state, "request_id", None)
        await _reply(
            request,
            session_id,
            f"Not saved: the {choice.kind} could not be stored (request {request_id}).",
        )
        raise server_error(
            request,
            f"the {choice.kind} was not saved",
            e,
            logger,
            status=503,
            code="MEMORY_SAVE_FAILED",
        ) from e
    entry = None
    if target is not None:
        entry = await log_intervention(
            request, getattr(request.state, "identity", None), cycle, record, "add"
        )
        where = f"{target.cycle_id}'s {', '.join(target.task_types)}"
    else:
        where = f"project {choice.project_id}" if choice.project_id else "yours only"
    reply = await _reply(
        request,
        session_id,
        f"Saved {choice.kind} {record.record_id} ({where}). It takes effect {choice.takes_effect}."
        + (
            " The campaign's control log couldn't record it, so the intervention ledger can't see "
            "it: declare it there."
            if of_campaign(cycle) and entry is None
            else ""
        ),
        metadata={"capture": record.record_id},
    )
    logger.info(
        "chat_capture_saved",
        extra={"session_id": session_id, "record_id": record.record_id, "scope": choice.scope},
    )
    return CaptureResponse(
        record_id=record.record_id,
        kind=choice.kind,
        scope=choice.scope,
        project_id=choice.project_id,
        takes_effect=choice.takes_effect,
        control_log_entry_id=entry,
        reply=ChatMessageDTO(
            message_id=reply.message_id,
            session_id=reply.session_id,
            role=reply.role,
            content=reply.content,
            created_at=reply.created_at,
        ),
    )


@agents_router.get("/messaging")
async def list_messaging_agents(request: Request) -> list[MessagingAgentDTO]:
    """List all agents with messaging enabled."""
    return [
        MessagingAgentDTO(
            agent_id=cfg["id"],
            display_name=cfg["display_name"],
            description=cfg["description"],
            a2a_port=cfg["a2a_port"],
        )
        for cfg in _messaging_agents(request).values()
    ]


# =============================================================================
# Session ownership and history assembly (P3-RC3, #2175)
# =============================================================================


async def _owned_session(
    chat_repo, session_id: str, user_id: str, agent_id: str | None = None
) -> ChatSession:
    """The session, when ``user_id`` owns it and, given an agent, it is that agent's.

    A session id is not authorization (#2175). Another user's session, one bound to another
    agent, or one its owner deleted (Q29), is refused exactly as a session that does not exist,
    so the refusal does not say which it was.
    """
    session = await chat_repo.get_session(session_id)
    if (
        session.user_id != user_id
        or (agent_id is not None and session.agent_id != agent_id)
        or session.deleted_at is not None
    ):
        logger.warning(
            "chat_session_refused",
            extra={"session_id": session_id, "user_id": user_id, "agent_id": agent_id},
        )
        raise SessionNotFoundError(f"Session not found: {session_id}")
    return session


async def _turn_session(
    request: Request,
    body: ChatMessageRequest,
    *,
    agent_id: str,
    user_id: str,
    scopes: frozenset[str],
    now: datetime,
) -> tuple[ChatSession, BoundedHistory, bool]:
    """The turn's session, with its earlier turns and whether they could be read: the person's own
    with this agent (#2175), or a new one bound server-side to the project the request names (§3.3)."""
    chat_repo = _get_chat_repo(request)
    if body.session_id:
        # #2175: the session must be this user's, with this agent, before anything of it is
        # replayed. Catch the specific error; DB errors propagate as 500.
        try:
            session = await _owned_session(chat_repo, body.session_id, user_id, agent_id)
        except SessionNotFoundError as e:
            raise handle_chat_error(e) from e
        if body.project_id is not None and body.project_id != session.project_id:
            # T14: every turn reads the stored binding; a client's claim is never read.
            logger.info(
                "chat_project_claim_ignored",
                extra={"session_id": session.session_id, "claimed": body.project_id},
            )
        # Its earlier turns, read before this turn's message is stored.
        history, unavailable = await _history_for_turn(request, session.session_id)
        return session, history, unavailable
    session = ChatSession(
        session_id=str(uuid.uuid4()),
        agent_id=agent_id,
        user_id=user_id,
        started_at=now,
        project_id=await _bindable_project(request, body.project_id, scopes),
    )
    await chat_repo.create_session(session)
    logger.info(
        "chat_session_created",
        extra={
            "agent_id": agent_id,
            "user_id": user_id,
            "session_id": session.session_id,
            "project_id": session.project_id,
        },
    )
    return session, BoundedHistory(turns=(), dropped=0), False


def _offered(
    proposal: ProposedCapture | None,
    *,
    source: ChatMessage,
    session: ChatSession,
    scopes: frozenset[str],
) -> dict | None:
    """The capture card a proposal becomes: the agent's text and suggested kind and scope, the turn it
    came from, and the choices this person may confirm, which are theirs, never the agent's (§3.3)."""
    if proposal is None:
        return None
    return {
        "text": proposal.text,
        "kind": proposal.kind,
        "scope": proposal.scope,
        "suggestion": proposal.suggestion,
        "applicability": (
            {name: list(values) for name, values in proposal.applicability.items()}
            if proposal.applicability is not None
            else None
        ),
        "target": (
            offered_target(proposal.target, source.content) if proposal.target is not None else None
        ),
        "lesson_revision": proposal.lesson_revision,
        "source_message_id": source.message_id,
        "choices": [
            _choice_dto(c).model_dump()
            for c in capture_choices(scopes=scopes, project_id=session.project_id)
        ],
    }


async def _bindable_project(
    request: Request, project_id: str | None, scopes: frozenset[str]
) -> str | None:
    """The project a new session is bound to, checked server-side (§3.3): it exists, and the person
    holds ``memory:read``. ``None`` opens an unbound session."""
    if project_id is None:
        return None
    if Scope.MEMORY_READ not in scopes:
        raise http_error(
            403, "FORBIDDEN", f"binding a chat to {project_id} needs {Scope.MEMORY_READ}"
        )
    try:
        await get_project_registry(request).get_project(project_id)
    except ProjectNotFoundError as e:
        raise http_error(422, "VALIDATION_ERROR", f"no project {project_id}") from e
    return project_id


async def _turn_memory(
    request: Request, session: ChatSession, message: ChatMessage, scopes: frozenset[str]
) -> dict | None:
    """The turn's memory context, from the session's stored binding (T14), and its exposure. ``None``
    when no records store is configured. Never raises: a section that fails is in the context's
    ``unavailable``, and the reply says so."""
    chat = request.app.state.config.comms.chat
    assembly = ChatContextAssembly(
        get_memory_records(request),
        get_memory_store(request),
        limits=ChatLimits(max_notes=chat.memory_max_notes, max_tokens=chat.memory_max_tokens),
        now=datetime.now(UTC),
    )
    binding = ProjectBound(session.project_id) if session.project_id else Unbound()
    turn = ChatTurn(
        session_id=session.session_id,
        message_id=message.message_id,
        user_id=session.user_id,
        agent_id=session.agent_id,
        text=message.content,
        viewer_scopes=scopes,
    )
    bundle = await assembly.assemble(ContextRequest(binding, turn))
    await assembly.disclose(bundle)
    return dict(bundle.chat) if bundle.chat is not None else None


def _capture_applicability(
    choice: CaptureChoice, body: CaptureRequest
) -> InstructionApplicability | None:
    """A project instruction's applicability as the card confirmed it (stage B): every field
    explicit, and only what a dispatch carries (the records API's check, one rule). Refused (422)
    for an instruction without one, and for anything else that carries one."""
    if choice.kind != RecordKind.INSTRUCTION or choice.scope == RecordScope.TASK:
        if body.applicability is not None:
            what = "task instruction" if choice.scope == RecordScope.TASK else choice.kind
            raise http_error(422, "VALIDATION_ERROR", f"a {what} has no applicability")
        return None
    if body.applicability is None:
        raise http_error(
            422,
            "VALIDATION_ERROR",
            "a project instruction names its task_types, roles and stacks ('*' for any)",
        )
    try:
        applicability = InstructionApplicability(
            tuple(body.applicability.task_types),
            tuple(body.applicability.roles),
            tuple(body.applicability.stacks),
        )
    except RecordRefused as e:
        raise http_error(422, "VALIDATION_ERROR", str(e)) from e
    refuse_unmatched(applicability)
    return applicability


def _capture_target(choice: CaptureChoice, body: CaptureRequest) -> TaskTarget | None:
    """A task instruction's cycle and tasks as the card confirmed them (#2180), or ``None`` for any
    other kind. Refused (422) when a task instruction names none, or anything else names one; a
    cited lesson is a task instruction's provenance only."""
    if choice.scope != RecordScope.TASK:
        if body.target is not None or body.lesson_revision is not None:
            raise http_error(
                422, "VALIDATION_ERROR", f"a {choice.scope} {choice.kind} has no target or lesson"
            )
        return None
    if body.target is None or not body.target.task_types:
        raise http_error(
            422, "VALIDATION_ERROR", "a task instruction names its cycle and its task types"
        )
    try:
        return TaskTarget(
            body.target.cycle_id, tuple(body.target.task_types), body.target.carries_into
        )
    except RecordRefused as e:  # a cycle the card left blank, which the person didn't fill
        raise http_error(422, "VALIDATION_ERROR", str(e)) from e


def _choice_dto(choice: CaptureChoice) -> CaptureChoiceDTO:
    return CaptureChoiceDTO(
        kind=choice.kind,
        scope=choice.scope,
        project_id=choice.project_id,
        takes_effect=choice.takes_effect,
    )


async def _reply(
    request: Request, session_id: str, text: str, *, metadata: dict | None = None
) -> ChatMessage:
    """A reply in the session that says what a capture did. Stored best-effort: when the store that
    failed the save fails this too, the answer still says it."""
    reply = ChatMessage(
        message_id=str(uuid.uuid4()),
        session_id=session_id,
        role="assistant",
        content=text,
        created_at=datetime.now(UTC),
        metadata=metadata or {},
    )
    try:
        await _get_chat_repo(request).store_message(reply)
        chat_cache = _chat_cache_of(request)
        if chat_cache is not None:
            await chat_cache.cache_message(reply)
    except Exception:  # noqa: BLE001 — the reply is still returned; the loss is logged
        logger.warning("chat_reply_not_stored", extra={"session_id": session_id}, exc_info=True)
    return reply


async def _history_for_turn(request: Request, session_id: str) -> tuple[BoundedHistory, bool]:
    """The session's earlier turns, bounded by ``comms.chat`` (#2175), and whether the read
    failed. A failed read is logged at WARNING with its error, and the turn runs without the
    history, its request saying so."""
    chat = request.app.state.config.comms.chat
    try:
        loaded = await _load_history(request, session_id)
    except Exception as e:  # noqa: BLE001 — the turn runs; the request says what it lacks
        logger.warning("chat_history_unavailable: %s", e, extra={"session_id": session_id})
        return BoundedHistory(turns=(), dropped=0), True
    bounded = bound_history(
        loaded, max_turns=chat.history_max_turns, max_tokens=chat.history_max_tokens
    )
    if bounded.dropped:
        logger.info(
            "chat_history_bounded",
            extra={
                "session_id": session_id,
                "kept": len(bounded.turns),
                "dropped": bounded.dropped,
            },
        )
    return bounded, False


async def _load_history(request: Request, session_id: str) -> list[dict]:
    """Load conversation history: Redis first, Postgres fallback.

    Returns list of {role, content} dicts for context assembly.
    Also repopulates Redis cache on miss (best-effort).
    """
    chat_cache = _chat_cache_of(request)
    # Try Redis cache first
    if chat_cache is not None:
        cached = await chat_cache.get_messages(session_id)
        if cached is not None:
            return [{"role": m["role"], "content": m["content"]} for m in cached]

    # Postgres fallback
    chat_repo = _get_chat_repo(request)
    messages = await chat_repo.get_session_messages(session_id)

    history = [{"role": m.role, "content": m.content} for m in messages]

    # Repopulate Redis cache (best-effort)
    if chat_cache is not None and messages:
        for m in messages:
            await chat_cache.cache_message(m)

    return history
