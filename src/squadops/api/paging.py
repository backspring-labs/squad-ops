"""A page of a list route (``docs/architecture/api-route-lanes.md``, "Paging a list"; #1891, #1976).

A list that can outgrow one response takes ``limit``, with a stated default and maximum, and
``offset``. The response stays the bare list. A full page means there may be more: the client asks
again from ``offset + limit``.
"""

from __future__ import annotations

from dataclasses import dataclass

from fastapi import Query

DEFAULT_LIMIT = 50
MAX_LIMIT = 500


@dataclass(frozen=True)
class Page:
    limit: int
    offset: int


def page(
    limit: int = Query(DEFAULT_LIMIT, ge=1, le=MAX_LIMIT, description="Items per page"),
    offset: int = Query(0, ge=0, description="Items to skip, in the list's order"),
) -> Page:
    """The route's page, as a FastAPI dependency: ``page: Page = Depends(page)``."""
    return Page(limit, offset)
