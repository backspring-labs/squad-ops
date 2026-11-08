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
from squadops.campaigns.change_request import SurfaceKind, load_stored_change_request

#: Contract 7's reasons (SIP-0112 §8.2.1), and SIP-0113 §4.1's for no runner, as a route's detail.
NO_START_DECLARATION = "no start declaration"
START_FAILED = "start failed"
SECRET_NOT_AVAILABLE = "secret not available"
NO_RUNNER = "no runner"
#: §8.3's evidence is the view's root anchor: without one, a page read shows nothing of its view.
NO_ANCHOR = "its view declares no anchor, so no page can show it rendered"
NO_MANIFEST = "the approved manifest its routes were read from can't be read"
#: A route the change request adds, and names no anchor for: a product's request carries no
#: manifest delta (§24bv point 5), and a request stored before §24cp names no anchor, so nothing on
#: its page can show it rendered. The rails refuse such a criterion since §24cp.
NO_ANCHOR_REQUESTED = (
    "the change request adds it, and names no anchor of its view, so no page can show it rendered"
)
#: §24co item 13: a fallback or a redirect shows another view's root anchor, so the root-anchor rule
#: reads it broken only while no two routes share one (#2780 makes them unique at the rails). Where
#: two do, neither page can be told from the other's.
SHARED_ANCHOR = (
    "its view's root anchor is also {other}'s, so its page can't be told from that one's"
)

#: §24cp: an added route whose requested anchor another page carries (``anchor_conflicts``). A page
#: the build never made would read held there, where the app's fallback renders that other view.
#: The rails refuse such a request; one stored before the rule is blocked by this.
ANCHOR_NOT_UNIQUE = "the change request names an anchor another page carries"
#: Where a route in the expected set came from (the record's ``source``). An accepted page is one
#: an earlier increment added and acceptance held (SIP-0109 §24dq).
FROM_MANIFEST, FROM_CHANGE_REQUEST = "approved_manifest", "change_request"
FROM_ACCEPTED_PAGE = "accepted_page"
#: §24dq: the key naming the accepted-page inventory, on a PROMOTE row's binding (the pages that
#: increment added) and on a repository-backed increment's ``campaign_proposal`` block (every page
#: the campaign's accepted increments added, pinned at its launch).
ACCEPTED_PAGES = "accepted_pages"


def pages_added_and_held(evaluation: Mapping[str, Any] | None) -> list[dict[str, Any]]:
    """The pages an accepted increment added, as its acceptance read them (§24dq): each route the
    renderer judged from the change request (``FROM_CHANGE_REQUEST``) and held, with the anchor it
    was held by and every test id its page's elements carried, the anchor first. Read from the
    stored evaluation's ``renderings``, so a replayed promotion writes the same record (#1943).
    Every id, not only the root: a later page's fallback renders this whole view (§24cp item 6).
    A sample application's evaluation has no ``renderings``, and gives none: its pages are its
    manifest's."""
    record = (evaluation or {}).get("renderings")
    pages = []
    for r in (record or {}).get("routes") or () if isinstance(record, Mapping) else ():
        anchor = r.get("anchor")
        if r.get("source") != FROM_CHANGE_REQUEST or r.get("held") != str(Held.HELD) or not anchor:
            continue
        others = sorted({str(t) for t in r.get("seen") or ()} - {anchor})
        pages.append(
            {"route": str(r["route"]), "anchor": str(anchor), "testids": [anchor, *others]}
        )
    return sorted(pages, key=lambda p: p["route"])


def page_inventory(records: Any) -> dict[str, tuple[str, ...]]:
    """§24dq: the accepted-page inventory a launch block carries, as each page's route and the test
    ids its page carried at acceptance, its anchor first. A block composed before §24dq names none.

    Raises:
        ValueError: A record names no route or no anchor. The inventory is the only record of
            those pages' anchors, so one it can't read is refused, never skipped: skipping it would
            let a later page reuse that anchor unseen."""
    pages: dict[str, tuple[str, ...]] = {}
    for record in records or ():
        if not isinstance(record, Mapping) or not record.get("route") or not record.get("anchor"):
            raise ValueError(f"an accepted page names no route or no anchor: {record!r}")
        anchor = str(record["anchor"])
        others = [str(t) for t in record.get("testids") or () if str(t) != anchor]
        pages[str(record["route"])] = (anchor, *dict.fromkeys(others))
    return pages


def requested_routes(change_request: str) -> dict[str, str]:
    """The client routes the approved change request's criteria are asserted on (§7.2's
    ``client_route`` surface, §24bv point 5): the routes the increment adds or changes, beside the
    pinned ones the profile names. In order, once each, with the anchor its criteria name for its
    view (§24cp), or ``""`` where none does. The rails let the criteria on one route name only one
    anchor; the first named is taken."""
    request = load_stored_change_request(change_request)
    routes: dict[str, str] = {}
    for c in request.criteria:
        if c.surface_kind is SurfaceKind.CLIENT_ROUTE:
            routes[c.surface] = routes.get(c.surface) or c.anchor
    return routes


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
        requested_routes: Mapping[str, str],
        accepted_pages: Mapping[str, Sequence[str]],
    ) -> ProductRoutes: ...


def route_record(
    results: Sequence[RouteResult],
    anchors: Mapping[str, tuple[str, ...]],
    read: Mapping[str, Any],
    start: dict[str, Any] | None,
    sources: Mapping[str, str] | None = None,
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
                "source": (sources or {}).get(r.path, FROM_MANIFEST),
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
    named: Sequence[str],
    why: str,
    start: dict[str, Any] | None = None,
    sources: Mapping[str, str] | None = None,
) -> ProductRoutes:
    """Every route ``named`` unrendered, ``blocked_unverified`` for ``why``, never passed
    (SIP-0096); none named is none judged."""
    if not named:
        return ProductRoutes((), None)
    results = tuple(RouteResult(r, Held.BLOCKED_UNVERIFIED, detail=why) for r in sorted(named))
    return ProductRoutes(results, route_record(results, {}, {}, start, sources))


__all__ = [
    "ACCEPTED_PAGES",
    "ANCHOR_NOT_UNIQUE",
    "FROM_ACCEPTED_PAGE",
    "NO_ANCHOR",
    "NO_MANIFEST",
    "NO_RUNNER",
    "NO_ANCHOR_REQUESTED",
    "NO_START_DECLARATION",
    "SHARED_ANCHOR",
    "SECRET_NOT_AVAILABLE",
    "START_FAILED",
    "ProductRoutes",
    "RouteRenderer",
    "page_inventory",
    "pages_added_and_held",
    "route_record",
    "requested_routes",
    "routes_blocked",
]
