"""What an app serves, read from its route table (#3101).

From FastAPI 0.136 an included router is one entry in ``app.routes``, no longer its routes
flattened, so a reader that walks ``app.routes`` for paths finds none of them. FastAPI's own
``iter_route_contexts`` walks the table as it is kept: each route with its full path, methods
and endpoint, however deeply its router was included.
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.routing import RouteContext, iter_route_contexts


def served(app: FastAPI) -> list[RouteContext]:
    """Every route ``app`` serves, each with its full ``path``, its ``methods`` and ``endpoint``."""
    return list(iter_route_contexts(app.routes))
