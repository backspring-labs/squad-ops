"""The standard error body, built in one place (#1976; the route-lane standard, #218).

Every error the runtime API returns is ``{"error": {"code", "message", "details"}}``, under
FastAPI's ``detail`` for an ``HTTPException``. ``details`` is always present, and nullable, so a
client reads one shape (T9). The cycle, campaign and chat routers each kept a copy of the same
builder; a plain-string ``detail`` was left on the health, agent-status and auth routes, and on
the auth middleware's refusals.

A server failure says what failed and gives the request id, never the exception's text. The text
can carry a connection string, a query or a path, and some of these routes are unauthenticated;
the request id finds the logged traceback.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence

from fastapi import HTTPException, Request

#: A domain error type, the status it answers with, and its code.
ErrorRow = tuple[type[Exception], int, str]


def error_body(code: str, message: str, details: dict | None = None) -> dict:
    return {"error": {"code": code, "message": message, "details": details}}


def http_error(status: int, code: str, message: str, details: dict | None = None) -> HTTPException:
    return HTTPException(status_code=status, detail=error_body(code, message, details))


def mapped_error(
    e: Exception, table: Sequence[ErrorRow], details: dict | None = None
) -> tuple[int, dict]:
    """The (status, body) of the first row of ``table`` whose type ``e`` is; a domain error the
    table doesn't name is a 500 ``INTERNAL_ERROR`` carrying its own message."""
    for exc_type, status, code in table:
        if isinstance(e, exc_type):
            return status, error_body(code, str(e), details)
    return 500, error_body("INTERNAL_ERROR", str(e), details)


def server_error(
    request: Request,
    what: str,
    exc: BaseException,
    logger: logging.Logger,
    *,
    status: int = 500,
    code: str = "INTERNAL_ERROR",
) -> HTTPException:
    """``what`` failed: logged with its traceback and the request id, answered with both and
    without the exception's text."""
    request_id = getattr(request.state, "request_id", None)
    logger.error("%s (request %s)", what, request_id, exc_info=exc)
    return http_error(status, code, what, {"request_id": request_id})
