"""
Console session and agent chat routes.

Part of SIP-0.8.9 Health Check refactor.
"""

import logging
from typing import TYPE_CHECKING, Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

if TYPE_CHECKING:
    from squadops.api.health_app import CommandHandler, ConsoleSession, HealthChecker

router = APIRouter(prefix="/console", tags=["console"])
logger = logging.getLogger(__name__)

# Will be injected at startup
_health_checker: "HealthChecker | None" = None
_console_sessions: dict[str, "ConsoleSession"] = {}
_parse_command: Any = None
_create_console_session: Any = None
_get_console_session: Any = None
_CommandHandler: type | None = None


def init_routes(
    health_checker: "HealthChecker",
    console_sessions: dict,
    parse_command,
    create_console_session,
    get_console_session,
    command_handler_cls: type,
) -> None:
    """Initialize routes with dependencies."""
    global _health_checker, _console_sessions, _parse_command
    global _create_console_session, _get_console_session, _CommandHandler
    _health_checker = health_checker
    _console_sessions = console_sessions
    _parse_command = parse_command
    _create_console_session = create_console_session
    _get_console_session = get_console_session
    _CommandHandler = command_handler_cls


class ConsoleCommandRequest(BaseModel):
    """Console command request."""

    session_id: str
    command: str


class ConsoleCommandResponse(BaseModel):
    """Console command response."""

    session_id: str
    lines: list[str]
    mode: str
    bound_agent: str | None = None
    cycle_id: str | None = None


@router.post("/command")
async def console_command(request: ConsoleCommandRequest):
    """Agent Gateway: Handle console command"""
    if not _health_checker or not _CommandHandler:
        raise RuntimeError("Console routes not initialized")

    try:
        # Get or create session
        session = _get_console_session(request.session_id)
        if not session:
            # Import ConsoleSession type dynamically to avoid circular import
            from squadops.api.health_app import ConsoleSession

            _console_sessions[request.session_id] = ConsoleSession(
                session_id=request.session_id, mode="idle"
            )
            session = _get_console_session(request.session_id)
            if not session:
                raise HTTPException(status_code=500, detail="Failed to create session")

        # Parse command
        parsed = _parse_command(request.command)
        cmd = parsed["command"]
        args = parsed["args"]

        logger.info(f"Agent Gateway command: {cmd} (session: {request.session_id})")

        # Initialize command handler
        handler = _CommandHandler(_health_checker)

        # Route command
        if cmd == "":
            return ConsoleCommandResponse(
                session_id=request.session_id,
                lines=[],
                mode=session.mode,
                bound_agent=session.bound_agent,
                cycle_id=session.cycle_id,
            )
        elif cmd == "help":
            lines = await handler.handle_help()
            return ConsoleCommandResponse(
                session_id=request.session_id,
                lines=lines,
                mode=session.mode,
                bound_agent=session.bound_agent,
                cycle_id=session.cycle_id,
            )
        elif cmd == "agent":
            return await _handle_agent_command(request, session, handler, args)
        elif cmd == "chat":
            return await _handle_chat_command(request, session, handler, args)
        elif cmd == "whoami":
            lines = await handler.handle_whoami(request.session_id)
            session = _get_console_session(request.session_id)
            return ConsoleCommandResponse(
                session_id=request.session_id,
                lines=lines,
                mode=session.mode if session else "idle",
                bound_agent=session.bound_agent if session else None,
                cycle_id=session.cycle_id if session else None,
            )
        elif cmd == "clear":
            return ConsoleCommandResponse(
                session_id=request.session_id,
                lines=["[Console cleared]"],
                mode=session.mode,
                bound_agent=session.bound_agent,
                cycle_id=session.cycle_id,
            )
        else:
            # Check if in chat mode - treat as message
            if session.mode == "chat" and session.bound_agent:
                result = await handler.handle_chat_message(request.session_id, request.command)
                return ConsoleCommandResponse(
                    session_id=request.session_id,
                    lines=result["lines"],
                    mode=result["mode"],
                    bound_agent=result["bound_agent"],
                    cycle_id=result["cycle_id"],
                )
            else:
                return ConsoleCommandResponse(
                    session_id=request.session_id,
                    lines=[f"Error: Unknown command '{cmd}'. Type 'help' for available commands."],
                    mode=session.mode,
                    bound_agent=session.bound_agent,
                    cycle_id=session.cycle_id,
                )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Agent Gateway error: {e}", exc_info=True)
        session = _get_console_session(request.session_id)
        return ConsoleCommandResponse(
            session_id=request.session_id,
            lines=[f"Error: {str(e)}"],
            mode=session.mode if session else "idle",
            bound_agent=session.bound_agent if session else None,
            cycle_id=session.cycle_id if session else None,
        )


async def _handle_agent_command(request, session, handler, args) -> ConsoleCommandResponse:
    """Handle agent subcommands."""
    if len(args) == 0:
        return ConsoleCommandResponse(
            session_id=request.session_id,
            lines=["Error: 'agent' command requires subcommand (list, status, info, logs)"],
            mode=session.mode,
            bound_agent=session.bound_agent,
            cycle_id=session.cycle_id,
        )

    subcmd = args[0].lower()
    if subcmd == "list":
        lines = await handler.handle_agent_list()
    elif subcmd == "status":
        lines = await handler.handle_agent_status()
    elif subcmd == "info":
        if len(args) < 2:
            return ConsoleCommandResponse(
                session_id=request.session_id,
                lines=["Error: 'agent info' requires agent name"],
                mode=session.mode,
                bound_agent=session.bound_agent,
                cycle_id=session.cycle_id,
            )
        lines = await handler.handle_agent_info(args[1])
    elif subcmd == "logs":
        if len(args) < 2:
            return ConsoleCommandResponse(
                session_id=request.session_id,
                lines=["Error: 'agent logs' requires agent name"],
                mode=session.mode,
                bound_agent=session.bound_agent,
                cycle_id=session.cycle_id,
            )
        n = int(args[2]) if len(args) >= 3 else 10
        lines = await handler.handle_agent_logs(args[1], n)
    else:
        lines = [f"Error: Unknown agent subcommand '{subcmd}'. Use 'help' for available commands."]

    return ConsoleCommandResponse(
        session_id=request.session_id,
        lines=lines,
        mode=session.mode,
        bound_agent=session.bound_agent,
        cycle_id=session.cycle_id,
    )


async def _handle_chat_command(request, session, handler, args) -> ConsoleCommandResponse:
    """Handle chat subcommands."""
    if len(args) == 0:
        return ConsoleCommandResponse(
            session_id=request.session_id,
            lines=["Error: 'chat' command requires agent name or 'end'"],
            mode=session.mode,
            bound_agent=session.bound_agent,
            cycle_id=session.cycle_id,
        )

    if args[0].lower() == "end":
        result = await handler.handle_chat_end(request.session_id)
    else:
        result = await handler.handle_chat_start(request.session_id, args[0])

    return ConsoleCommandResponse(
        session_id=request.session_id,
        lines=result["lines"],
        mode=result["mode"],
        bound_agent=result["bound_agent"],
        cycle_id=result["cycle_id"],
    )


@router.get("/session")
async def create_console_session_endpoint():
    """Agent Gateway: Create new console session"""
    if not _create_console_session:
        raise RuntimeError("Console routes not initialized")

    session_id = _create_console_session()
    return {"session_id": session_id}


@router.get("/responses/{session_id}")
async def get_console_responses(session_id: str):
    """Agent Gateway: Get and clear pending responses for session"""
    if not _get_console_session:
        raise RuntimeError("Console routes not initialized")

    session = _get_console_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    # Return responses and clear list
    responses = session.pending_responses.copy()
    session.pending_responses.clear()

    return {"session_id": session_id, "responses": responses, "count": len(responses)}
