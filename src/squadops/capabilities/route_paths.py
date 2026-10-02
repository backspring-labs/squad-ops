"""Manifest path helpers shared by every stack expander: which segments of a path are parameters.

A manifest path names a parameter in either of two spellings, ``{run_id}`` or ``:run_id``, and
authored manifests use both. The authoring rules say braces for endpoint and route paths alike,
while the authoring template's example route is ``/items/:item_id``. In the stored corpus, API
endpoints are always braces, and client routes split: FastAPI+React 218 colon to 6 brace, Next.js
139 brace to 35 colon.

Each stack renders a parameter in its own router's syntax: React Router ``:run_id``, Next.js
``[run_id]``, FastAPI ``{run_id}``. So the reading of the manifest's spelling lives here, once.
Before #1794 each stack read it for itself. Next.js translated both spellings. The React scaffold
wrote ``{run_id}`` into a ``<Route path>`` verbatim, a literal segment React Router never matches,
so the six brace-routed React apps shipped a page no browser could reach.

A leaf, importing nothing from this package, like ``type_tokens``.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PathSegment:
    """One ``/``-separated segment of a manifest path. ``param`` is True when it names a path
    parameter, in which case ``name`` is the parameter's bare name."""

    name: str
    param: bool = False


def path_segments(path: str) -> tuple[PathSegment, ...]:
    """``/runs/{run_id}/join`` or ``/runs/:run_id/join`` → ``runs``, ``run_id`` (a parameter),
    ``join``. The root ``/`` has no segments.

    Anything else is literal:
    - a segment that only partly looks like a parameter (``{run_id}.json``, ``{}``, ``:``), since
      the manifest has no syntax for it, and guessing would render a route the manifest did not
      declare;
    - Next.js's own ``[run_id]``, which two stored manifests used. That stack places it as the
      directory it already is."""
    out: list[PathSegment] = []
    for seg in path.strip("/").split("/"):
        if not seg:
            continue
        if len(seg) > 2 and seg.startswith("{") and seg.endswith("}"):
            out.append(PathSegment(seg[1:-1], param=True))
        elif len(seg) > 1 and seg.startswith(":"):
            out.append(PathSegment(seg[1:], param=True))
        else:
            out.append(PathSegment(seg))
    return tuple(out)
