"""A seeded quality reading's plan (SIP-0113 §10j, §10n; #2562): a Project's seed file written as
requests through a delivery's own declared interface, and the pages each seeded record is measured
on.

§10f's reading scores a delivery's pages as they load, on an empty app. So a page with a parameter
is never measured, and a list is only ever measured empty. The seeded reading starts the tree a
second time, writes the seed through the app's API, and measures every declared page, each
parameterised one once per record the seed names for it.

The rules are route rendering's and the release screenshots', in one place (§10n ruling 2):
- **an endpoint is the one the manifest declares,** as it writes it. A seed names a create or a
  member action without a base (``POST /runs``), and it is matched as written, under the
  manifest's ``base_path``, or under a prefix the manifest wrote itself (a Next.js app's
  ``/api/runs``), as ``increment_tree.route_seeds`` resolves a create. The request goes to the
  path as written, never through the scenarios' API prefix;
- **a record's values go under the request shape's field names,** through the seed's aliases. A
  field the shape requires with no value refuses that record (``seed_refused``), and a value no
  shape field takes is a note, never dropped silently;
- **each record's id is read from its create's own response,** and its members join that record,
  so a seed can bring a run to its capacity without the code ever reading "capacity";
- **each parameterised route is measured once per labelled record the seed names for it** (§10n
  ruling 3), keyed by the route as declared and the label. A route the seed names no record for,
  or one with two parameters or a wildcard, reads ``no_seed_value``.

Pure: the runner sends the requests and measures the pages. ``campaigns``, not
``squadops.scenarios``, since route rendering's rules are the squad side's and the held-out
boundary keeps that side from importing the evaluator's (§10n ruling 2).
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from squadops.campaigns.increment_tree import declared_routes, route_param

#: The planner's rules, as a measure's version: moved whenever what a seed plans changes, so two
#: readings planned two ways are never compared (§10n ruling 5).
MAPPING_VERSION = 1

#: Why a seeded page wasn't measured.
NO_SEED_VALUE = "no_seed_value"
SEED_REFUSED = "seed_refused"


class SeedRefused(ValueError):
    """The delivery's interface can't take the seed, or one of its records (§10j's
    ``seed_refused``): no declared endpoint for it, or a required field with no value."""


def norm_route(path: str) -> str:
    """``/runs/{run_id}``, ``/runs/:run_id`` and ``/runs/{id}`` are one route."""
    return re.sub(r"\{[^}/]+\}|:[A-Za-z_][A-Za-z0-9_]*", "{id}", path)


def under_base(candidates: Sequence[str], base: str) -> list[str]:
    """The seed names endpoints without a base path (``POST /runs``); an interface declares its
    endpoints under one (``base_path: /api``, so ``POST /api/runs``). Each candidate is also tried
    under the base, the form the app's own client uses (the 1.8.2 cut found the committed seed
    matching nothing on an app behind ``/api``)."""
    if not base:
        return list(candidates)
    under = []
    for c in candidates:
        method, _, path = c.partition(" ")
        under.append(c if path == base or path.startswith(base + "/") else f"{method} {base}{path}")
    return list(dict.fromkeys([*candidates, *under]))


def body_for(
    record: Mapping[str, Any],
    required: Sequence[str],
    optional: Sequence[str],
    aliases: Mapping[str, Sequence[str]],
    where: str,
) -> tuple[dict[str, Any], set[str]]:
    """The record's values under the shape's field names, through the seed's aliases, and the
    record keys that carried over. A required field with no value refuses it."""
    body: dict[str, Any] = {}
    used: set[str] = set()
    for name in [*required, *optional]:
        key = next((k for k in record if k == name or name in (aliases.get(k) or [])), None)
        if key is not None:
            body[name] = record[key]
            used.add(key)
        elif name in required:
            raise SeedRefused(
                f"{where}: the interface requires {name!r} and the seed has no value for it "
                f"(record keys {sorted(record)}, aliases {dict(aliases)})"
            )
    return body, used


@dataclass(frozen=True)
class SeedRequest:
    """One request the runner sends, at the path the manifest writes. A member action's path
    keeps its parameter segment (``segment``), which the record's id fills (``fill``)."""

    method: str
    path: str
    json: Mapping[str, Any]
    segment: str | None = None


@dataclass(frozen=True)
class SeedRecord:
    """One labelled record: its create, then the member actions that join it."""

    label: str
    create: SeedRequest
    members: tuple[SeedRequest, ...] = ()


@dataclass(frozen=True)
class SeededPage:
    """A page the seeded reading measures, keyed by the route as declared and the record that
    fills its parameter (``None`` for a route with none). ``segment`` is the parameter as the
    route writes it."""

    route: str
    record: str | None = None
    segment: str | None = None

    @property
    def key(self) -> str:
        """The page's key across trees: the route with its parameter's name normalised, and the
        record's label (§10n ruling 4). A filled URL differs on every instance."""
        route = norm_route(self.route)
        return f"{route}#{self.record}" if self.record else route


@dataclass(frozen=True)
class SeedPlan:
    """What the runner sends and measures. ``refused`` and ``unfilled`` name what wasn't, with
    why, and ``notes`` what didn't carry over."""

    records: tuple[SeedRecord, ...]
    pages: tuple[SeededPage, ...]
    refused: tuple[tuple[str, str], ...] = ()
    unfilled: tuple[tuple[str, str], ...] = ()
    notes: tuple[str, ...] = ()
    seed_sha256: str = ""
    mapping_version: int = MAPPING_VERSION

    @property
    def version(self) -> str:
        """The seed's part of the measure's version: its bytes and the planner's rules."""
        return f"seed:{self.seed_sha256[:12]}:plan-v{self.mapping_version}"

    def as_dict(self) -> dict[str, Any]:
        """The plan on the wire to the sandbox's runner, which sends and measures it."""

        def request(r: SeedRequest) -> dict[str, Any]:
            return {"method": r.method, "path": r.path, "json": dict(r.json), "segment": r.segment}

        return {
            "records": [
                {
                    "label": r.label,
                    "create": request(r.create),
                    "members": [request(m) for m in r.members],
                }
                for r in self.records
            ],
            "pages": [
                {"route": p.route, "record": p.record, "segment": p.segment} for p in self.pages
            ],
            "refused": [list(x) for x in self.refused],
            "unfilled": [list(x) for x in self.unfilled],
            "notes": list(self.notes),
            "seed_sha256": self.seed_sha256,
            "mapping_version": self.mapping_version,
        }

    @classmethod
    def from_dict(cls, d: Mapping[str, Any]) -> SeedPlan:
        def request(r: Mapping[str, Any]) -> SeedRequest:
            return SeedRequest(r["method"], r["path"], dict(r.get("json") or {}), r.get("segment"))

        return cls(
            records=tuple(
                SeedRecord(
                    r["label"], request(r["create"]), tuple(map(request, r.get("members", ())))
                )
                for r in d["records"]
            ),
            pages=tuple(
                SeededPage(p["route"], p.get("record"), p.get("segment")) for p in d["pages"]
            ),
            refused=tuple((str(a), str(b)) for a, b in d.get("refused", ())),
            unfilled=tuple((str(a), str(b)) for a, b in d.get("unfilled", ())),
            notes=tuple(d.get("notes", ())),
            seed_sha256=str(d.get("seed_sha256", "")),
            mapping_version=int(d.get("mapping_version", MAPPING_VERSION)),
        )


def fill(path: str, segment: str | None, value: str) -> str:
    """``path`` with its parameter segment, as written, replaced by ``value``."""
    if segment is None:
        return path
    return "/".join(value if part == segment else part for part in path.split("/"))


def seed_sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _endpoint(manifest: Any, candidates: Sequence[str], what: str) -> Any:
    """The declared endpoint one of ``candidates`` names: as written, under the base, or under a
    prefix the manifest wrote itself, one match only (a page two endpoints could serve is never
    guessed, as ``route_seeds`` rules)."""
    api = manifest.api
    base = str(api.base_path or "").rstrip("/")
    endpoints = list(api.endpoints or ())
    for candidate in under_base(candidates, base):
        method, _, path = candidate.partition(" ")
        want = (method.upper(), norm_route(path))
        exact = [e for e in endpoints if (e.method.upper(), norm_route(e.path)) == want]
        if exact:
            return exact[0]
    for candidate in candidates:
        method, _, path = candidate.partition(" ")
        tail = norm_route(path)
        written = [
            e
            for e in endpoints
            if e.method.upper() == method.upper()
            and norm_route(e.path).endswith(tail)
            and norm_route(e.path)[: -len(tail)].startswith("/")
        ]
        if len(written) == 1:
            return written[0]
    declared = sorted(f"{e.method.upper()} {e.path}" for e in endpoints)
    raise SeedRefused(
        f"none of the seed's {what} endpoints {list(candidates)} is declared: {declared}"
    )


def _shape(manifest: Any, request: str | None) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """The request's required and optional fields: its declared shape, or what the manifest says
    a body for it must carry."""
    for shape in manifest.api.request_shapes or ():
        if shape.name == request:
            return tuple(shape.required), tuple(shape.optional)
    return tuple(manifest.request_body_fields(request)), ()


def _segment(path: str) -> str | None:
    params = [s for s in path.split("/") if route_param(s) is not None]
    return params[0] if len(params) == 1 else None


def plan(manifest: Any, seed: Mapping[str, Any], raw: bytes) -> SeedPlan:
    """The seed, as requests against THIS delivery's declared interface, and the pages to measure.
    Refuses (``SeedRefused``) a seed whose create no endpoint is declared for, since nothing of it
    could be written; a record the interface can't take is refused alone, and the rest are kept."""
    aliases = seed.get("field_aliases") or {}
    create = _endpoint(manifest, seed.get("create") or (), "create")
    create_required, create_optional = _shape(manifest, create.request)
    member = None
    if seed.get("member_action"):
        member = _endpoint(manifest, seed["member_action"], "member action")
        if _segment(member.path) is None:
            raise SeedRefused(f"the member action {member.path} names no one parameter to fill")
    records: list[SeedRecord] = []
    refused: list[tuple[str, str]] = []
    notes: list[str] = []
    for i, entry in enumerate(seed.get("records") or (), start=1):
        label = str(entry.get("label") or f"record-{i}")
        try:
            body, used = body_for(
                entry.get("values") or {}, create_required, create_optional, aliases, label
            )
            members: list[SeedRequest] = []
            for j, values in enumerate(entry.get("members") or (), start=1):
                if member is None:
                    raise SeedRefused(f"{label}: members, and the seed names no member action")
                required, optional = _shape(manifest, member.request)
                member_body, _ = body_for(
                    values, required, optional, aliases, f"{label} member {j}"
                )
                members.append(
                    SeedRequest("POST", member.path, member_body, segment=_segment(member.path))
                )
        except SeedRefused as e:
            refused.append((label, str(e)))
            continue
        notes += [
            f"{label}: {k} dropped, not a field of {create.request}"
            for k in sorted(set(entry.get("values") or {}) - used)
        ]
        records.append(SeedRecord(label, SeedRequest("POST", create.path, body), tuple(members)))
    if not records:
        raise SeedRefused(
            "no record of the seed could be written: " + "; ".join(why for _, why in refused)
        )
    pages, unfilled = _pages(
        manifest, seed, {r.label for r in records}, {label for label, _ in refused}
    )
    return SeedPlan(
        records=tuple(records),
        pages=pages,
        unfilled=unfilled,
        refused=tuple(refused),
        notes=tuple(notes),
        seed_sha256=seed_sha256(raw),
    )


def _pages(
    manifest: Any, seed: Mapping[str, Any], seeded: set[str], refused: set[str]
) -> tuple[tuple[SeededPage, ...], tuple[tuple[str, str], ...]]:
    named = {
        norm_route(route): list(labels) for route, labels in (seed.get("routes") or {}).items()
    }
    pages: list[SeededPage] = []
    unfilled: list[tuple[str, str]] = []
    for route in declared_routes(manifest):
        if not route.startswith("/"):
            continue
        segment = _segment(route)
        has_param = any(route_param(s) is not None for s in route.split("/"))
        if not has_param and "*" not in route and "[" not in route:
            pages.append(SeededPage(route))
            continue
        labels = named.get(norm_route(route)) if segment else None
        if not labels:
            unfilled.append((route, NO_SEED_VALUE))
            continue
        for label in labels:
            if label in seeded:
                pages.append(SeededPage(route, label, segment))
            else:
                why = SEED_REFUSED if label in refused else NO_SEED_VALUE
                unfilled.append((f"{route}#{label}", why))
    return tuple(pages), tuple(unfilled)


def load(raw: bytes) -> Mapping[str, Any]:
    """A seed file's content. Refused when it isn't the §10n shape: labelled records under
    ``records``, each with its ``values``."""
    doc = json.loads(raw)
    records = doc.get("records") if isinstance(doc, Mapping) else None
    if not isinstance(records, list) or not all(
        isinstance(r, Mapping) and isinstance(r.get("values"), Mapping) for r in records
    ):
        raise SeedRefused("a quality seed is {create, records: [{label, values, members}], ...}")
    return doc
