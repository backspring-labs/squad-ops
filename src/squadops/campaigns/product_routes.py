"""A repository-backed product's client routes at its increment's acceptance: the judgement's shape,
and the reasons a route reads unrendered (SIP-0109 §24co, §24bv point 3, §8.3).

The rendering itself starts the product from its declared start in the sandbox, which only the
scenario runner does (``scenarios.declared_routes``). The executor that calls it builds squad
task envelopes, so it never imports the held-out scenarios' package (SIP-0113 §4.1, IR-4): it is
handed a ``RouteRenderer`` by the composition root, and reads what this module defines.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Protocol

from squadops.campaigns.acceptance import Held, RouteResult

#: Contract 7's reasons (SIP-0112 §8.2.1), and SIP-0113 §4.1's for no runner, as a route's detail.
NO_START_DECLARATION = "no start declaration"
START_FAILED = "start failed"
SECRET_NOT_AVAILABLE = "secret not available"
NO_RUNNER = "no runner"
#: §8.3's evidence is the view's root anchor: without one, a page read shows nothing of its view.
NO_ANCHOR = "its view declares no anchor, so no page can show it rendered"
NO_MANIFEST = "the approved manifest its routes were read from can't be read"


@dataclass(frozen=True)
class ProductRoutes:
    """The routes' judgement and its evidence: each route's result, as a sample application's is
    judged, and ``record``, what was started and what each page showed. ``record`` is ``None``
    where the profile names no route: not applicable (§24bv point 3)."""

    results: tuple[RouteResult, ...]
    record: dict[str, Any] | None


class RouteRenderer(Protocol):
    """Renders a product's client routes on a candidate (``scenarios.declared_routes``)."""

    async def render(
        self,
        *,
        profile: Any,
        configuration: Any,
        initialization: Any,
        candidate: Any,
        verified_candidate_revision: str | None,
    ) -> ProductRoutes: ...


def route_record(
    results: Sequence[RouteResult],
    anchors: Mapping[str, tuple[str, ...]],
    read: Mapping[str, Any],
    start: dict[str, Any] | None,
) -> dict[str, Any]:
    """What was started and what each route's page showed: its view's root anchor, the path it
    was read at, the test ids its elements carried (``None`` for a page never read), and why a
    blocked one wasn't read."""

    def seen(route: str) -> list[str] | None:
        reading = read.get(route)
        return (
            list(reading.testids) if reading is not None and reading.testids is not None else None
        )

    return {
        "start": start,
        "routes": [
            {
                "route": r.path,
                "held": str(r.held),
                "anchor": anchors[r.path][0] if anchors.get(r.path) else None,
                "read_at": read[r.path].path if r.path in read else None,
                "seen": seen(r.path),
                "detail": r.detail or None,
            }
            for r in results
        ],
    }


def routes_blocked(
    named: Sequence[str], why: str, start: dict[str, Any] | None = None
) -> ProductRoutes:
    """Every route ``named`` unrendered, ``blocked_unverified`` for ``why``, never passed
    (SIP-0096); none named is none judged."""
    if not named:
        return ProductRoutes((), None)
    results = tuple(RouteResult(r, Held.BLOCKED_UNVERIFIED, detail=why) for r in sorted(named))
    return ProductRoutes(results, route_record(results, {}, {}, start))


__all__ = [
    "NO_ANCHOR",
    "NO_MANIFEST",
    "NO_RUNNER",
    "NO_START_DECLARATION",
    "SECRET_NOT_AVAILABLE",
    "START_FAILED",
    "ProductRoutes",
    "RouteRenderer",
    "route_record",
    "routes_blocked",
]
