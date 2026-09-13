"""Domain errors become the standard envelope in one place (#576).

Every cycles/runs/artifacts/chat route used to wrap its body in
``try/except CycleError: raise handle_cycle_error(e)`` — 43 blocks that said the same
thing. The app registers these handlers once; the envelope tables in
``routes/cycles/errors.py`` and ``routes/chat/errors.py`` still own the status and code
for each error, and the wire shape — ``{"detail": {"error": {...}}}`` with the mapped
status — is unchanged. A test that mounts a router on its own app calls
``register_domain_error_handlers`` the way the runtime does.
"""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from squadops.api.routes.chat.errors import chat_error_envelope
from squadops.api.routes.cycles.errors import cycle_error_envelope
from squadops.comms.models import ChatError
from squadops.cycles.models import CycleError


async def cycle_error_to_response(request: Request, exc: CycleError) -> JSONResponse:
    status, detail = cycle_error_envelope(exc)
    return JSONResponse(status_code=status, content={"detail": detail})


async def chat_error_to_response(request: Request, exc: ChatError) -> JSONResponse:
    status, detail = chat_error_envelope(exc)
    return JSONResponse(status_code=status, content={"detail": detail})


def register_domain_error_handlers(app: FastAPI) -> FastAPI:
    """Install the domain-error handlers on ``app``; returns it for chaining."""
    app.add_exception_handler(CycleError, cycle_error_to_response)
    app.add_exception_handler(ChatError, chat_error_to_response)
    return app
