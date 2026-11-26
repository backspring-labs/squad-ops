"""A request slower than a second is logged with its path and time (#3218).

The runtime's instrument for the worker's unanswered requests. Beside the event loop watchdog
(``api/runtime/loop_watchdog.py``), it reads whether a slow worker request waited on a held loop or
on something the request itself waited for.
"""

from __future__ import annotations

import logging
import time

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

logger = logging.getLogger(__name__)

#: A request slower than this is logged (the 2.8.1 plan's bar is 2 s).
SLOW_REQUEST_S = 1.0


class SlowRequestMiddleware(BaseHTTPMiddleware):
    """Logs ``slow_request`` for a request that took longer than ``SLOW_REQUEST_S``."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        started = time.monotonic()
        response = await call_next(request)
        elapsed = time.monotonic() - started
        if elapsed > SLOW_REQUEST_S:
            logger.warning(
                "slow_request method=%s path=%s status=%s elapsed_s=%.2f",
                request.method,
                request.url.path,
                response.status_code,
                elapsed,
            )
        return response
