"""Contract-first build scaffolding — the deterministic walking-skeleton expander.

Per ``sips/proposed/SIP-Contract-First-Build-Scaffolding.md``: framing emits a typed
*interface manifest* (entities / endpoints / routes); this module deterministically
materializes a **walking skeleton** from it — a wired application that already builds
and boots — into which the dev agent fills bodies at fixed, scaffold-owned slots.

The dividing line between deterministic and generative work is *interface vs.
implementation*: everything identical regardless of what the app does (entry files,
config, bootstrap, cross-file wiring) is scaffolded here; only the endpoint/component
*bodies* are left for the model.

This is pure logic (``manifest -> list[{name, content}]``) — no port, no NoOp, no
factory, sibling to ``build_profiles.py``/``dev_capabilities.py``. The output shape
(``{"name", "content"}``) matches ``patch_verification.materialize_artifacts`` so the
expanded files ride the existing artifact-seeding rail with no new adapter.

Phase-0.5 spike scope: the ``fullstack_fastapi_react`` stack only; standalone parse
(not yet wired into ``ImplementationPlan.from_yaml`` or the executor seam — that is the
post-verdict integration). The emitted skeleton is deliberately *empty*: routes and
components exist, wire together, build, and boot, but their bodies are stubs.
"""

from __future__ import annotations

import ast
import hashlib
import json
import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

# #822: stack #2's expander lives in its own module — a second one inline would push this
# file past 2000 lines and interleave two stacks' source templates. No cycle: it annotates
# against ``InterfaceManifest`` under ``TYPE_CHECKING`` and imports nothing here at runtime.
from squadops.capabilities.stack_nextjs_ts import STACK_NAME as _NEXTJS_TS_NAME
from squadops.capabilities.stack_nextjs_ts import expand_nextjs_ts as _expand_nextjs_ts
from squadops.capabilities.stack_nextjs_ts import (
    fill_slots_nextjs_ts as _fill_slots_nextjs_ts,
)

# Schema v1 is frozen (SIP-0099 phase 99.1): the shape below is the canonical
# interface-manifest contract the fullstack_fastapi_react expander was proven against
# in the Phase-0.5 spike. A manifest declaring any other version/kind is rejected at
# parse time rather than silently mis-expanded — a future v2 gets its own expander.
INTERFACE_MANIFEST_VERSION = 1
INTERFACE_MANIFEST_KIND = "interface_manifest"

# --------------------------------------------------------------------------- schema


@dataclass(frozen=True)
class ManifestField:
    """A field on an entity (``entities[].fields[]``)."""

    name: str
    type: str
    required: bool = True
    generated: bool = False
    default: Any = None
    has_default: bool = False


@dataclass(frozen=True)
class Entity:
    name: str
    fields: tuple[ManifestField, ...] = ()


@dataclass(frozen=True)
class RequestShape:
    """A request body shape (``api.request_shapes``) — a projection of entity fields."""

    name: str
    required: tuple[str, ...] = ()
    optional: tuple[str, ...] = ()


@dataclass(frozen=True)
class Endpoint:
    method: str
    path: str
    summary: str = ""
    request: str | None = None  # names a RequestShape
    response: str | None = None  # e.g. "RunEvent" or "list[RunEvent]"
    errors: tuple[str, ...] = ()
    # Success status the endpoint must return. ``ErrorCode.http`` already models the
    # *error* statuses, so before pf-39 the manifest could declare "422 on validation
    # failure" but not "201 on create" — the expander emitted a bare
    # ``@router.post(path)`` (FastAPI default 200) while the derived contract probe
    # pinned 201, making the skeleton unable to satisfy its own contract. Green then
    # depended on the dev agent volunteering ``status_code=201``: pf-38 did, pf-39 did
    # not, and that single token was the whole difference. None = framework default.
    success_status: int | None = None


@dataclass(frozen=True)
class ErrorCode:
    code: str
    http: int


@dataclass(frozen=True)
class ErrorContract:
    shape: str = ""
    codes: tuple[ErrorCode, ...] = ()


@dataclass(frozen=True)
class Api:
    base_path: str = ""
    request_shapes: tuple[RequestShape, ...] = ()
    endpoints: tuple[Endpoint, ...] = ()
    error_contract: ErrorContract | None = None


@dataclass(frozen=True)
class Route:
    path: str
    view: str
    purpose: str = ""
    # #659: the view's DOM anchor contract — scaffold-owned data-testid names
    # both prompt sides receive (dev: attach/preserve; qa: query only these).
    # First entry is the ROOT anchor, stamped on the expanded stub's container.
    testids: tuple[str, ...] = ()


@dataclass(frozen=True)
class Frontend:
    framework: str = "react_vite"
    language: str = "javascript"
    api_client: str = "fetch"
    routes: tuple[Route, ...] = ()


@dataclass(frozen=True)
class Decision:
    """One design judgment the schema cannot express mechanically (SIP-0103 §5c.4).

    Pagination behavior, authorization boundaries, idempotency, caching — decisions a
    designer must make and the manifest's structural fields cannot hold. Recording them
    with a PRD ``warrant`` makes the judgment explicit, reviewable at the human gate,
    and auditable afterwards.

    ``unresolved`` marks a question the author declines to answer (§5c.10): a PRD that
    does not determine something should surface as a stated question rather than a
    silent default. An unresolved entry carries its ``question`` instead of a
    ``choice``.

    Deliberately NOT part of the structural projection — see ``_canonical``.
    """

    id: str
    choice: str = ""
    warrant: str = ""
    unresolved: bool = False
    question: str = ""


@dataclass(frozen=True)
class Revision:
    """Why one authoring attempt was rejected (#803, M5).

    Classes come from M6's taxonomy, never free text: "took three tries" cannot say whether
    those were schema failures, winnability rejections, or the author's own refinement, and
    the three have opposite remedies. The proofs are kept alongside so a reader can see the
    specific finding without re-deriving it from the class.
    """

    attempt: int
    classes: dict[str, int] = field(default_factory=dict)
    proofs: tuple[str, ...] = ()


@dataclass(frozen=True)
class Provenance:
    """How this manifest came to be (SIP-0103 §5c.5, #803).

    **System-owned and observed, never claimed.** The one part of the document an author may
    not write: an attempt count the author asserts about itself is a lie surface, and the
    schema gate rejects an author-supplied block for that reason.

    **Presence is the signal.** A manifest with provenance was authored by a squad and this
    block says how; one without did not come from this system (operator-seeded, including the
    reference instance). Data-driven, like every other mode decision here — no flag.

    Deliberately NOT part of the structural projection — see ``_canonical``. The expander
    ignores it, and a manifest whose only change is *how it was written* must expand to the
    same skeleton and keep the contract bound to it valid.
    """

    mode: str = ""
    cycle_id: str = ""
    task_id: str = ""
    attempts: int = 0
    revisions: tuple[Revision, ...] = ()


@dataclass(frozen=True)
class InterfaceManifest:
    """The typed interface contract framing emits and the expander consumes."""

    version: int
    kind: str
    project_id: str
    stack: str
    source_prd: str = ""
    scope: str = ""
    entities: tuple[Entity, ...] = ()
    api: Api = field(default_factory=Api)
    frontend: Frontend = field(default_factory=Frontend)
    persistence: str = "in_memory"
    #: Design judgments and open questions (SIP-0103 §5c.4/§5c.10). Provenance, not
    #: structure: excluded from ``_canonical`` so revising an explanation never moves
    #: the hash the verification contract is bound to.
    decisions: tuple[Decision, ...] = ()
    #: How the document was authored (#803). ``None`` for anything this system did not
    #: author. Excluded from ``_canonical`` for the same reason ``decisions`` is.
    provenance: Provenance | None = None

    @classmethod
    def from_yaml(cls, content: str) -> InterfaceManifest:
        data = yaml.safe_load(content)
        if not isinstance(data, dict):
            raise ValueError("interface manifest must be a YAML mapping")
        return cls.from_dict(data)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> InterfaceManifest:
        required_keys = ("version", "kind", "project_id", "stack")
        missing = [k for k in required_keys if k not in data]
        if missing:
            raise ValueError(f"interface manifest missing required keys: {missing}")

        version = int(data["version"])
        if version != INTERFACE_MANIFEST_VERSION:
            raise ValueError(
                f"unsupported interface manifest version {version}; "
                f"this expander is schema v{INTERFACE_MANIFEST_VERSION}"
            )
        kind = str(data["kind"])
        if kind != INTERFACE_MANIFEST_KIND:
            raise ValueError(
                f"interface manifest kind must be {INTERFACE_MANIFEST_KIND!r}, got {kind!r}"
            )

        entities = tuple(_parse_entity(e) for e in data.get("entities", []))
        api = _parse_api(data.get("api", {}) or {})
        frontend = _parse_frontend(data.get("frontend", {}) or {})
        return cls(
            version=version,
            kind=kind,
            project_id=str(data["project_id"]),
            stack=str(data["stack"]),
            source_prd=str(data.get("source_prd", "")),
            scope=str(data.get("scope", "")),
            entities=entities,
            api=api,
            frontend=frontend,
            persistence=str(data.get("persistence", "in_memory")),
            decisions=tuple(
                Decision(
                    id=str(d.get("id", "")),
                    choice=str(d.get("choice", "")),
                    warrant=str(d.get("warrant", "")),
                    unresolved=bool(d.get("unresolved", False)),
                    question=str(d.get("question", "")),
                )
                for d in (data.get("decisions") or [])
                if isinstance(d, dict)
            ),
            provenance=_parse_provenance(data.get("provenance")),
        )

    def _canonical(self) -> dict[str, Any]:
        """Deterministic structural projection for hashing — every field the expander
        reads to produce the skeleton, and nothing else. Provenance (``source_prd``,
        ``scope``) is excluded: the expander ignores it, so a provenance-only edit must
        not spuriously move the hash and invalidate the verification contract bound to
        it (SIP-0098 §10 drift). ``project_id`` IS included — it is substituted into the
        emitted package name and app title, so it changes the skeleton."""
        return {
            "version": self.version,
            "kind": self.kind,
            "project_id": self.project_id,
            "stack": self.stack,
            "persistence": self.persistence,
            "entities": [
                {
                    "name": e.name,
                    "fields": [
                        {
                            "name": f.name,
                            "type": f.type,
                            "required": f.required,
                            "generated": f.generated,
                            "default": f.default,
                            "has_default": f.has_default,
                        }
                        for f in e.fields
                    ],
                }
                for e in self.entities
            ],
            "api": {
                "base_path": self.api.base_path,
                "request_shapes": [
                    {"name": s.name, "required": list(s.required), "optional": list(s.optional)}
                    for s in self.api.request_shapes
                ],
                "endpoints": [
                    {
                        "method": ep.method,
                        "path": ep.path,
                        "summary": ep.summary,
                        "request": ep.request,
                        "response": ep.response,
                        "errors": list(ep.errors),
                        # The expander emits this onto the decorator, so it changes the
                        # skeleton and must move the hash — omitting it would let two
                        # manifests that produce different skeletons hash identically
                        # and silently keep a contract bound to the wrong one.
                        "success_status": ep.success_status,
                    }
                    for ep in self.api.endpoints
                ],
                "error_contract": (
                    {
                        "shape": self.api.error_contract.shape,
                        "codes": [
                            {"code": c.code, "http": c.http} for c in self.api.error_contract.codes
                        ],
                    }
                    if self.api.error_contract
                    else None
                ),
            },
            "frontend": {
                "framework": self.frontend.framework,
                "language": self.frontend.language,
                "api_client": self.frontend.api_client,
                "routes": [
                    {
                        "path": r.path,
                        "view": r.view,
                        "purpose": r.purpose,
                        **({"testids": list(r.testids)} if r.testids else {}),
                    }
                    for r in self.frontend.routes
                ],
            },
        }

    def content_hash(self) -> str:
        """Stable sha256 identifying the skeleton this manifest expands to. SIP-0098's
        verification contract binds ``skeleton.interface_manifest_hash`` to this value,
        so drift between a contract and the skeleton it verifies becomes detectable."""
        canonical = json.dumps(self._canonical(), sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    def lint(self) -> list[str]:
        """Return the consistency defects that make this manifest unusable for
        scaffolding — the "malformed/incomplete" net a framing LLM emission is checked
        against (SIP-0099 phase 99.2). Gross malformation (bad version/kind, missing
        required keys) is already raised by ``from_dict``; this catches the manifests
        that *parse* but cannot be expanded (no endpoints, an endpoint referencing an
        undeclared request shape, a route with no view). Empty list ⇒ usable.
        """
        errors: list[str] = []
        if not self.project_id:
            errors.append("project_id is required")
        if self.stack not in _STACKS:
            errors.append(
                f"stack {self.stack!r} has no scaffold expander (known: {sorted(_STACKS)})"
            )
        if not self.api.endpoints:
            errors.append("api.endpoints is empty — declare at least one endpoint to scaffold")

        entity_names = {e.name for e in self.entities}
        shape_names = {s.name for s in self.api.request_shapes}
        for ep in self.api.endpoints:
            label = f"endpoint {ep.method} {ep.path}".rstrip()
            if not ep.method or not ep.path:
                errors.append(f"{label}: method and path are required")
            if ep.request and ep.request not in shape_names and ep.request not in entity_names:
                errors.append(
                    f"{label}: request {ep.request!r} is not a declared request_shape or entity"
                )
            if ep.response:
                base = _base_type_name(ep.response)
                # a capitalized response type names an entity; a lowercase one is a
                # primitive (str/int/…) the expander passes through.
                if base and base[0].isupper() and base not in entity_names:
                    errors.append(f"{label}: response references undeclared entity {base!r}")

        for route in self.frontend.routes:
            if not route.view:
                errors.append(f"frontend route {route.path!r}: view is required")

        return errors


def _parse_provenance(raw: Any) -> Provenance | None:
    """Parse the system-owned provenance block, or ``None`` when absent.

    Tolerant by design: provenance is a record, not a contract. A malformed block must not
    make an otherwise-valid design unparseable, because that would let a bookkeeping defect
    reject a manifest the squad got right.
    """
    if not isinstance(raw, dict):
        return None
    revisions = tuple(
        Revision(
            attempt=int(r.get("attempt", 0)),
            classes={str(k): int(v) for k, v in (r.get("classes") or {}).items()},
            proofs=tuple(str(x) for x in (r.get("proofs") or [])),
        )
        for r in (raw.get("revisions") or [])
        if isinstance(r, dict)
    )
    return Provenance(
        mode=str(raw.get("mode", "")),
        cycle_id=str(raw.get("cycle_id", "")),
        task_id=str(raw.get("task_id", "")),
        attempts=int(raw.get("attempts", 0)),
        revisions=revisions,
    )


def _parse_entity(raw: dict[str, Any]) -> Entity:
    fields = []
    for f in raw.get("fields", []):
        has_default = "default" in f
        fields.append(
            ManifestField(
                name=str(f["name"]),
                type=str(f["type"]),
                required=bool(f.get("required", True)),
                generated=bool(f.get("generated", False)),
                default=f.get("default"),
                has_default=has_default,
            )
        )
    return Entity(name=str(raw["name"]), fields=tuple(fields))


def _parse_api(raw: dict[str, Any]) -> Api:
    shapes = tuple(
        RequestShape(
            name=str(name),
            required=tuple(str(x) for x in (spec or {}).get("required", [])),
            optional=tuple(str(x) for x in (spec or {}).get("optional", [])),
        )
        for name, spec in (raw.get("request_shapes", {}) or {}).items()
    )
    endpoints = tuple(
        Endpoint(
            method=str(ep["method"]).upper(),
            path=str(ep["path"]),
            summary=str(ep.get("summary", "")),
            request=(str(ep["request"]) if ep.get("request") else None),
            response=(str(ep["response"]) if ep.get("response") else None),
            errors=tuple(str(x) for x in ep.get("errors", [])),
            success_status=(
                int(ep["success_status"]) if ep.get("success_status") is not None else None
            ),
        )
        for ep in raw.get("endpoints", [])
    )
    ec_raw = raw.get("error_contract")
    error_contract = None
    if ec_raw:
        codes = tuple(
            ErrorCode(code=str(code), http=int((spec or {}).get("http", 400)))
            for code, spec in (ec_raw.get("codes", {}) or {}).items()
        )
        error_contract = ErrorContract(shape=str(ec_raw.get("shape", "")), codes=codes)
    return Api(
        base_path=str(raw.get("base_path", "")),
        request_shapes=shapes,
        endpoints=endpoints,
        error_contract=error_contract,
    )


def _parse_frontend(raw: dict[str, Any]) -> Frontend:
    routes = tuple(
        Route(
            path=str(r["path"]),
            view=str(r["view"]),
            purpose=str(r.get("purpose", "")),
            testids=tuple(str(t) for t in r.get("testids", [])),
        )
        for r in raw.get("routes", [])
    )
    return Frontend(
        framework=str(raw.get("framework", "react_vite")),
        language=str(raw.get("language", "javascript")),
        api_client=str(raw.get("api_client", "fetch")),
        routes=routes,
    )


# ------------------------------------------------------------------------- expander


def expand(manifest: InterfaceManifest) -> list[dict[str, str]]:
    """Materialize the walking skeleton for ``manifest.stack``.

    Returns a list of ``{"name": <workspace-relative path>, "content": <str>}`` —
    the shape ``patch_verification.materialize_artifacts`` writes to disk.
    """
    return _stack(manifest.stack).expand(manifest)


def materialize(manifest: InterfaceManifest, dest: Path) -> int:
    """Write the expanded skeleton under ``dest``. Returns the file count.

    The canonical writer for ``expand`` output. Two copies of this loop had grown in
    ``scripts/dev/`` (one with the chroot guard, one without); callers that need a
    skeleton on disk use this instead of re-implementing the walk, so the safety check
    below can never be the one that gets left out.

    Raises:
        ValueError: if an expander emits a name that escapes ``dest``.
    """
    root = dest.resolve()
    files = expand(manifest)
    for f in files:
        out = (dest / f["name"]).resolve()
        # chroot safety: an expander must never write outside the target root.
        if root != out and root not in out.parents:
            raise ValueError(f"refusing to write outside {root}: {f['name']!r}")
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(f["content"], encoding="utf-8")
    return len(files)


def fill_slot_paths(manifest: InterfaceManifest) -> tuple[str, ...]:
    """Workspace-relative paths of the *fill slots* — the files the dev agent fills
    bodies into. Everything else ``expand`` emits is frozen (scaffold-owned): the
    SIP-0098 verification contract pins those by hash and hangs per-file criteria only
    on these slots. Same stack dispatch as ``expand``; raises for an unknown stack.

    Each stack answers this for itself (#S1). It used to be answered inline behind a guard
    that only checked whether the stack was *registered*, so a second stack would silently
    have inherited ``backend/routes.py`` and ``.jsx`` view paths — a wrong answer that
    nothing would have objected to, because the guard it passed asks a different question.
    """
    return _stack(manifest.stack).fill_slots(manifest)


def error_seam_instructions(manifest: InterfaceManifest | None) -> list[str]:
    """Authoritative error-contract lines for correction/repair prompts (pf-34).

    The ``ApiError(code, message)`` raise convention and the code→status map are
    scaffold-owned interface knowledge; they live in the manifest's
    ``error_contract`` and in the fill-slot STUB's docstring — which dies the
    moment the first fill replaces the stub. Repairs then guess the seam:
    ``ApiError(status_code=..., detail=...)`` appeared in dev repairs on two
    consecutive rolls (pf-33 corr-01, pf-34 corr-00 — every error path
    TypeError→500 at runtime, failing the behavioral retest AFTER passing all
    typed checks, which cannot see call signatures). These lines travel the
    same failure_evidence → authoritative-block transport as interface drift
    and frozen-ownership instructions. Empty when the manifest declares no
    error contract (author mode, non-scaffold stacks).
    """
    ec = manifest.api.error_contract if manifest is not None else None
    if ec is None or not ec.codes:
        return []
    code_map = ", ".join(f"`{c.code}` → {c.http}" for c in ec.codes)
    return [
        (
            "on failure raise `ApiError(code, message)` (imported from `.errors`): the "
            "FIRST argument is the error-code STRING, the second a human message — "
            "never `ApiError(status_code=..., detail=...)` and never `HTTPException` "
            "for contract errors; the frozen `errors.py` maps the code to the HTTP "
            "status and renders the pinned envelope"
        ),
        f"valid error codes (code → HTTP status, mapped by frozen `errors.py`): {code_map}",
    ]


def model_surface_instructions(manifest: InterfaceManifest | None) -> list[str]:
    """Authoritative importable names from the frozen ``models.py`` (pf-41).

    ``models.py`` is scaffold-frozen and its contents are fully determined by the
    manifest's entities and request shapes — yet nothing puts those names in front of a
    repair. So repairs guess them, and the guesses compound: on pf-41 the dev agent
    imported the correct names, then three consecutive repairs replaced them with
    ``Run``/``CreateRun``, then ``RunCreate``, then a five-name invention
    (``RunCreate``, ``RunResponse``, ``RunJoin``, ``RunLeave``, ``RunDetailResponse``) —
    none of which exist. Working code degraded into unimportable code across the
    correction loop.

    Detection already exists (``emission_integrity.unresolved_imports`` rejects a patch
    whose intra-package imports do not resolve) and it works — on pf-40 it caught every
    bad repair. But detection only throws the repair away; it never tells the model what
    the right names ARE, so the next attempt guesses again. These lines close that: same
    ``failure_evidence`` → authoritative-block transport as the error seam and frozen
    ownership.

    Field-level since pf-45: class names alone did not carry the surface a fill body
    actually touches. pf-45's dev wrote ``pace=data.pace`` against a model declaring
    ``pace_target`` — a one-token invention this block could not have prevented, because
    it named the classes and not their fields. Every POST /runs raised into a 500. The
    signature form makes the field vocabulary exact for both consumers of this transport
    (the initial fill prompt and the repair prompt).

    Also names the frozen store: pf-45's dev re-declared local store dicts in the fill
    slot, shadowing ``backend/store.py`` — the scaffold's ``reset()`` then cleared the
    unused stores, so test isolation silently broke.

    Empty when there is no manifest (author mode, non-scaffold stacks) — additive, like
    every other entry on that transport.
    """
    if manifest is None:
        return []
    signatures = [f"`{e.name}({', '.join(f.name for f in e.fields)})`" for e in manifest.entities]
    signatures += [
        f"`{s.name}({', '.join(dict.fromkeys(list(s.required) + list(s.optional)))})`"
        for s in manifest.api.request_shapes
    ]
    if not signatures:
        return []
    lines = [
        (
            "`backend/models.py` is scaffold-frozen and defines EXACTLY these names: "
            f"{', '.join(dict.fromkeys(signatures))}. Import only from this list — these "
            "are the complete contents of that module"
        ),
        (
            "field names are exact — construct and read models with the fields shown above; "
            "a near-miss (`pace` for `pace_target`, `meeting_location` for `location`) raises "
            "at request time and every affected endpoint returns HTTP 500"
        ),
        (
            "do NOT invent model names or aliases (`Run`, `RunCreate`, `RunResponse`, "
            "`RunJoin` and similar do not exist); an import of a name absent from the list "
            "above fails at load, the app never starts, and the patch is rejected"
        ),
        (
            "`models.py` is frozen — if a name you want is missing, use the declared names "
            "and shape the response in the fill slot; do not edit or re-emit the model module"
        ),
    ]
    if manifest.persistence == "in_memory":
        stores = ", ".join(f"`{_snake(e.name)}_store`" for e in manifest.entities)
        lines.append(
            f"`backend/store.py` is scaffold-frozen and already defines the in-memory "
            f"stores: {stores} (plus `reset()` for test isolation). Import them "
            "(`from .store import ...`); do NOT declare your own store dicts — a shadow "
            "store is invisible to `reset()`, so state leaks between tests and the suite "
            "fails on isolation"
        )
    return lines


def testid_surface_instructions(manifest: InterfaceManifest | None) -> list[str]:
    """The manifest-pinned DOM anchor inventory, one line per view (#659).

    Frontend suites never converge because nothing arbitrates the DOM: qa
    asserts invented render details (roles, text, structure), dev patches the
    view toward the last suite, and the re-dispatched suite re-rolls its
    expectations — two models chasing a moving target (fay-6, fay-12: five
    correction rounds, all on the frontend suite, backend green throughout).
    The backend converges because the contract is injected into BOTH prompts;
    these lines are that move applied to the DOM.

    Data only, per the same transport as ``model_surface_instructions`` — the
    dev-side "attach and preserve" and qa-side "query only these" prose lives
    in the managed appendix assets (CLAUDE.md #448). Empty when no manifest or
    no route declares testids — additive.
    """
    if manifest is None:
        return []
    return [
        f"`{r.view}` (route `{r.path}`): root container `{r.testids[0]}`; "
        f"anchors: {', '.join(f'`{t}`' for t in r.testids)}"
        for r in manifest.frontend.routes
        if r.testids
    ]


def _class_field_names(node: ast.ClassDef) -> list[str]:
    """Annotated attribute names declared directly on a class body."""
    return [
        stmt.target.id
        for stmt in node.body
        if isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name)
    ]


def _imported_modules(tree: ast.AST) -> list[str]:
    """Module strings as the source actually writes them — ``.routes`` stays relative.

    The relative form is the point: pf-42's plan asserted ``import_present`` for
    ``backend.routes`` against a frozen ``main.py`` that says ``from .routes import
    router``. Rendering the *written* form is what makes that mismatch visible.
    """
    modules: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            modules.append("." * node.level + (node.module or ""))
    # __future__ is on every emitted module and tells the author nothing.
    return [m for m in modules if m != "__future__"]


def _python_surface(source: str, name: str = "") -> str:
    """One line describing what a frozen Python module declares, or "" if nothing useful.

    ``name`` is the workspace-relative path; when given, the line opens with the module
    path a consumer imports the file BY (#787). The index always rendered the file's
    *own* imports — accurate for the plan author writing ``import_present`` checks, but
    the one available reading for an author reaching for a symbol was usage guidance,
    and the modeled form is relative (``.models``): V2's qa suite wrote
    ``from .store import reset`` twice and the chain terminated as plan_defect. The
    reachable form is derivable from the path alone, so the line now states it instead
    of leaving it to be guessed from a field that means something else.
    """
    try:
        tree = ast.parse(source)
    except SyntaxError:  # pragma: no cover - the expander emits valid Python
        return ""

    classes = [
        f"{node.name}({', '.join(fields)})" if (fields := _class_field_names(node)) else node.name
        for node in tree.body
        if isinstance(node, ast.ClassDef)
    ]
    # Module-level state is the whole public API of some frozen modules, and omitting it
    # is how pf-43 died: `store.py` is two annotated dicts plus `reset()`, so an index
    # listing only functions read as "an empty stub", and the plan author wrote a task to
    # build the store it already had — five typed checks against a file no agent may
    # change. A name the author cannot see is a name it will invent.
    state = [
        f"{stmt.target.id}: {ast.unparse(stmt.annotation)}"
        for stmt in tree.body
        if isinstance(stmt, ast.AnnAssign)
        and isinstance(stmt.target, ast.Name)
        and not stmt.target.id.startswith("_")
    ]
    # #863: parameters, not just names. pf-42 gave classes their fields
    # (`User(id, email)`) and left functions as bare names, so the index published a
    # symbol's existence and withheld how to call it. Roll 8 imported the right function
    # from the right module and wrote `all()` against `all(table)`; tsc rejected it and the
    # correction chain terminated. Same sentence as pf-42, one level down — a signature the
    # author cannot see is a signature it will guess. Names only, not annotations: the index
    # is prose for an author, and `insert(table, row)` carries the arity and the meaning
    # while the full type costs a line's readability for something the caller never restates.
    # #871 revised that trade for the ECMAScript reader only (roll 12: `find(table, id)`
    # concealed `id: string`, the repair invented numeric ids, the tree stopped compiling).
    # This reader stays names-only until a Python roll fails on a concealed type — its
    # frozen sources annotate optionally, so rendered types would be intermittent anyway.
    functions = [
        f"{node.name}({', '.join(a.arg for a in node.args.args if a.arg != 'self')})"
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and not node.name.startswith("_")
    ]
    modules = sorted(set(_imported_modules(tree)))

    parts = []
    # conftest.py is pytest plumbing loaded by discovery, never imported — an
    # "import as `conftest`" line would teach exactly the anti-pattern its own
    # header forbids.
    if name and name.rsplit("/", 1)[-1] != "conftest.py":
        dotted = name.removesuffix(".py").replace("/", ".").removesuffix(".__init__")
        parts.append(f"import as `{dotted}`")
    if classes:
        parts.append("defines " + ", ".join(classes))
    if state:
        parts.append("module state " + ", ".join(state))
    if functions:
        parts.append("functions " + ", ".join(functions))
    if modules:
        parts.append("its own imports " + ", ".join(f"`{m}`" for m in modules))
    return "; ".join(parts)


_TS_INTERFACE = re.compile(r"^export\s+(?:interface|type)\s+(\w+)", re.M)
#: Name, then an optional generic list, the arguments, then an optional return type up to
#: the body brace. The generic clause is not optional in practice — `lib/api.ts` declares
#: `export async function api<T>(...)`, and a pattern without it silently rendered that
#: file as a bare name (caught before commit). The return-type clause stops at `{` or
#: newline, so an object-literal return type would truncate — no emitted file declares
#: one, and this reader is scoped to the expanders' known shapes by design.
_TS_FUNCTION = re.compile(
    r"^export\s+(?:async\s+)?function\s+(\w+)\s*(?:<[^>]*>)?\s*\(([^)]*)\)\s*(?::\s*([^{\n]+?))?\s*\{",
    re.M,
)
#: #871: `export class` had no clause at all, so frozen `lib/errors.ts` rendered as
#: "exports ERROR_STATUS; functions errorResponse(err)" — `ApiError`, the one seam the
#: error contract expects every route to use, was never named. Roll 12's original defect
#: is the invention that predicts: m001 passed a bare string to `errorResponse()`
#: (TypeScript-legal, the param is `unknown`) and every error path returned 500.
_TS_CLASS = re.compile(r"^export\s+(?:abstract\s+)?class\s+(\w+)", re.M)
_TS_CONSTRUCTOR = re.compile(r"constructor\s*\(([^)]*)\)", re.S)
#: Constructor parameter-property modifiers (`public code: string`) — stripped so the
#: rendered signature is the call form, not the declaration form.
_TS_PARAM_MODIFIERS = re.compile(r"^(?:(?:public|private|protected|readonly)\s+)+")
_TS_CONST = re.compile(r"^export\s+const\s+(\w+)", re.M)
_TS_FIELD = re.compile(r"^\s{2}(\w+\??: *[^\n;,]+)", re.M)
_TS_IMPORT = re.compile(r"""^import\s+[^'"]*from\s+['"]([^'"]+)['"]""", re.M)


def _ts_param_list(params: str) -> list[str]:
    """``table: string,\n  row: Record<string, unknown> = {}`` → the params, one string each.

    Splits on top-level commas only: a generic or object type carries its own commas
    (``Record<string, unknown>``), and splitting naively would invent parameters.
    Whitespace is collapsed; types and defaults are KEPT (#871) — see the revision note
    on the rendering site below.
    """
    segments: list[str] = []
    depth = 0
    current = ""
    for ch in params:
        if ch in "<([{":
            depth += 1
        elif ch in ">)]}":
            depth -= 1
        if ch == "," and depth == 0:
            segments.append(current)
            current = ""
        else:
            current += ch
    segments.append(current)
    return [" ".join(seg.split()) for seg in segments if seg.strip()]


def _ecmascript_surface(source: str) -> str:
    """One line describing what a frozen JS/TS module declares, or ``""``.

    The ``_python_surface`` counterpart, and the same reason for existing: pf-43 died
    because ``store.py``'s module state was omitted and the author wrote a task to build a
    store it already had. **A name the author cannot see is a name it will invent** — that
    holds regardless of language, and stack #2 had no reader at all.

    Regex rather than a parser, which is safe *here specifically*: these files are emitted
    by the stacks' own expander templates, so the shapes are known and fixed. This is not a
    general JS/TS reader and must not be reused as one — teaching the typed CHECKS to parse
    TS is S4's work and needs a real parser, because those read code the squad wrote.

    Named for ECMAScript rather than TypeScript because it covers both, and it covers both
    because the first version did not. It was written for stack #2 and read `.ts`/`.tsx`
    only, which left **stack #1's entire frontend still bare** — `App.jsx`, `main.jsx`,
    `api.js` — after a commit whose own message said the gap was on both stacks. The
    TypeScript-only constructs simply do not match in a `.js` file; nothing else needed to
    change.
    """
    interfaces: list[str] = []
    for match in _TS_INTERFACE.finditer(source):
        body = source[match.end() :].split("}", 1)[0]
        fields = [" ".join(f.split()).rstrip(",;") for f in _TS_FIELD.findall(body)]
        interfaces.append(
            f"`{match.group(1)}({', '.join(fields)})`" if fields else f"`{match.group(1)}`"
        )
    # #871 revises the #863 names-only ruling FOR THIS READER: types and defaults are
    # kept, and the return type is rendered. Roll 12's repair invented a numeric-id
    # scheme in exactly the blind spot names-only leaves — `find(table, id)` concealed
    # `id: string` and `nextId()` concealed its `string` return, so the repair wrote
    # `find('runs', Number(run_id))` and the tree stopped compiling. The types are
    # literal in the frozen source; concealing them traded a line's readability for a
    # terminal run. `_python_surface` deliberately stays names-only — no Python roll
    # has failed on a concealed type, and its frozen sources annotate optionally.
    # Signatures are backtick-wrapped so commas inside types (`Record<string, unknown>`)
    # never read as list separators.
    functions = []
    for name, params, ret in _TS_FUNCTION.findall(source):
        signature = f"{name}({', '.join(_ts_param_list(params))})"
        if ret.strip():
            signature += f": {ret.strip()}"
        functions.append(f"`{signature}`")
    # #871: a class's call surface is its constructor. Bounded at the next top-level
    # `export` so one class's constructor is never attributed to the class before it.
    classes: list[str] = []
    for match in _TS_CLASS.finditer(source):
        body = source[match.end() :]
        next_export = re.search(r"^export\s", body, re.M)
        if next_export:
            body = body[: next_export.start()]
        ctor = _TS_CONSTRUCTOR.search(body)
        ctor_params = [
            _TS_PARAM_MODIFIERS.sub("", p) for p in _ts_param_list(ctor.group(1) if ctor else "")
        ]
        classes.append(f"`{match.group(1)}({', '.join(ctor_params)})`")
    consts = _TS_CONST.findall(source)
    modules = sorted(set(_TS_IMPORT.findall(source)))

    parts = []
    if interfaces:
        parts.append("defines " + ", ".join(interfaces))
    if classes:
        parts.append("classes " + ", ".join(classes))
    if consts:
        parts.append("exports " + ", ".join(consts))
    if functions:
        parts.append("functions " + ", ".join(functions))
    if modules:
        # Labelled as the file's OWN imports for the same reason as the Python
        # reader (#787) — though here mimicry is usually correct, since sibling
        # files model the alias form (`@/lib/store`) the consumer should use.
        parts.append("its own imports " + ", ".join(f"`{m}`" for m in modules))
    return "; ".join(parts)


def _package_json_surface(source: str) -> str:
    """One line naming the dependency surface a ``package.json`` declares, or ``""``.

    A dependency list is a declaration surface exactly as a module's exports are: roll 9's
    qa suite opened with ``import request from 'supertest'`` against a manifest declaring
    no such package, and the suite could never collect. The index rendered the file as a
    bare name, so the closed set of importable packages was a fact no author was shown.
    Versions are dropped — the author needs the names, and pinning prose to versions
    would churn the index on every template bump.
    """
    try:
        data = json.loads(source)
    except ValueError:
        return ""
    if not isinstance(data, dict):
        return ""
    parts = []
    for key, label in (("dependencies", "dependencies"), ("devDependencies", "devDependencies")):
        section = data.get(key)
        if isinstance(section, dict) and section:
            parts.append(f"{label} " + ", ".join(sorted(section)))
    return "; ".join(parts)


#: File suffixes whose *interior* ``frozen_surface_index_lines`` can describe. Everything
#: else is listed by name alone.
#:
#: Declared rather than left implicit in an ``endswith(".py")`` (2a). The limit was read as
#: a stack-#2 gap when #849 found a Next.js author guessing at a frozen file it had no
#: declarations for — but the inventory shows **stack #1 renders 10 of its 15 frozen entries
#: bare too**, including the whole of `frontend/` (`App.jsx`, `api.js`, `main.jsx`). pf-42's
#: index has only ever described the Python half, on both stacks, and nobody noticed because
#: the checks that would trip on a frontend guess are bundler-level rather than
#: declaration-level.
#:
#: Naming it makes the gap countable and gives the appendix's "may not be checked at all"
#: rule a mechanical referent, and a test asserts the declaration and the renderers stay in
#: step. ``.ts``/``.tsx`` were added when 2a's inventory showed stack #2 rendering **every**
#: entry bare — the appendix's escape hatch had no line anywhere on that stack, so no frozen
#: file could be checked at all. ``.js``/``.jsx``/``.mjs`` followed in the same PR (this
#: comment previously still listed them as undescribed — stale the moment it merged).
#: Still short of complete: `.html` and `.json`-other-than-``package.json`` remain
#: undescribed on both stacks.
DESCRIBED_FROZEN_SUFFIXES: tuple[str, ...] = (".py", ".ts", ".tsx", ".js", ".jsx", ".mjs")

#: Basenames described regardless of suffix. ``package.json`` earned its entry at roll 9:
#: its dependency list is the closed set of packages a suite may import, the qa author was
#: never shown it, and the emitted suite opened with a package the manifest does not
#: declare. The prior reading — "``.json`` has no declarations to give" — was wrong in
#: exactly the way this index exists to prevent.
DESCRIBED_FROZEN_BASENAMES: tuple[str, ...] = ("package.json",)


def frozen_surface_index_lines(manifest: InterfaceManifest | None) -> list[str]:
    """One line per scaffold-frozen file, naming exactly what it declares (pf-42).

    The plan author is shown a criteria index covering the *fill slots* and nothing else
    — four files out of seventeen. The other thirteen are frozen, and the author has
    never been told they exist, let alone what is in them. So when it wants a check on
    one it invents the contents: pf-42 asserted a ``RunEvent`` field called
    ``meeting_location`` (the manifest says ``location``) and an ``import_present`` for
    ``backend.routes`` against a file that writes ``from .routes``. Neither could ever
    pass, and neither could be repaired — a frozen emission is restored before the check
    re-runs — so the plan was dead on arrival and cost a roll to discover.

    Derived by parsing the *expanded skeleton itself* rather than describing it by hand,
    so this index cannot drift from what the expander emits: change a template and the
    lines change with it.

    The companion to the plan-validation net (``cycles.frozen_check_validation``), and
    the same pairing as the repair path's model surface + unresolved-import gate: supply
    the authoritative fact so nothing has to guess, and verify deterministically so a
    guess can never cost a roll.

    Empty when there is no manifest (author mode, non-scaffold stacks) — additive.
    """
    if manifest is None:
        return []
    fills = set(fill_slot_paths(manifest))
    lines = []
    for f in expand(manifest):
        name = f["name"]
        if name in fills:
            continue
        if name.rsplit("/", 1)[-1] in DESCRIBED_FROZEN_BASENAMES:
            detail = _package_json_surface(f["content"])
        elif name.endswith(".py"):
            detail = _python_surface(f["content"], name)
        elif name.endswith((".ts", ".tsx", ".js", ".jsx", ".mjs")):
            detail = _ecmascript_surface(f["content"])
        else:
            detail = ""
        lines.append(f"- `{name}` — {detail}" if detail else f"- `{name}`")
    return lines


def qa_test_namespace(manifest: InterfaceManifest) -> tuple[str, ...]:
    """Workspace-relative directory prefixes that own QA test files for ``manifest.stack``.

    Deterministic for a given stack (no dependence on the manifest contents), so plan
    validation and Phase-2 write authorization derive the same surface. Raises for an unknown
    stack (parity with ``expand`` / ``fill_slot_paths``)."""
    return _stack(manifest.stack).qa_test_namespace


def is_qa_test_path_for_stack(path: str, stack: str) -> bool:
    """True when a workspace-relative ``path`` falls within ``stack``'s QA test namespace.

    Membership is by normalized directory-prefix (``./`` and ``//`` collapsed); it does not
    resolve traversal — Phase-2 authorization owns canonical-target identity (D7). Stack-keyed
    (tolerant: unknown stack → no namespace) so bind-mode dispatch, which has the stack from the
    contract, can use it without a manifest."""
    norm = str(path).strip().lstrip("./").replace("//", "/")
    known = _STACKS.get(stack)
    return bool(known) and any(norm.startswith(ns) for ns in known.qa_test_namespace)


def is_qa_test_path(path: str, manifest: InterfaceManifest) -> bool:
    """Manifest-keyed convenience over ``is_qa_test_path_for_stack``."""
    return is_qa_test_path_for_stack(path, manifest.stack)


def harness_entry_modules(stack: str) -> tuple[str, ...]:
    """App entry modules a QA test must not import for ``stack`` (SIP-0100 harness boundary).

    Empty for a stack without a declared boundary — dispatch then binds no ``harness_boundary``
    check (author-mode / non-scaffolded parity)."""
    known = _STACKS.get(stack)
    return known.harness_entry_modules if known else ()


def is_scaffoldable_stack(stack: str) -> bool:
    """True when ``stack`` has a registered walking-skeleton expander — i.e. a cycle on
    this stack can be scaffolded. Half of the authored-mode predicate
    (``cycles.manifest_authoring.authors_interface_manifest``): only scaffoldable cycles
    dispatch an authoring stage, so a non-scaffoldable stack never produces a manifest
    describing a skeleton nothing can build."""
    return bool(stack) and stack in _STACKS


# ------------------------------------------------- fullstack_fastapi_react templates

_PY_PRIMITIVES = {"string": "str", "integer": "int", "number": "float", "boolean": "bool"}


def _py_type(type_str: str) -> str:
    """Map a manifest type token onto a Python annotation.

    ``string`` -> ``str``; ``list[X]`` -> ``list[X]``; an entity name passes through
    as the class name (models are emitted in manifest order, referenced entities
    first, and routes import the classes they reference — so no forward refs).
    """
    t = type_str.strip()
    if t.startswith("list[") and t.endswith("]"):
        inner = t[len("list[") : -1].strip()
        return f"list[{_py_type(inner)}]"
    return _PY_PRIMITIVES.get(t, t)


def _base_type_name(type_str: str) -> str:
    """The bare entity/model name inside a type token (``list[RunEvent]`` -> ``RunEvent``)."""
    t = type_str.strip()
    if t.startswith("list[") and t.endswith("]"):
        return _base_type_name(t[len("list[") : -1])
    return t


def _model_source(manifest: InterfaceManifest) -> str:
    lines = [
        '"""Pydantic models — scaffold-owned interface (entities + request shapes).',
        "",
        "Field bodies (validators, computed defaults) are fill-only; the class",
        "surface here is fixed by the interface manifest.",
        '"""',
        "",
        "from __future__ import annotations",
        "",
        "from typing import Annotated",
        "",
        "from pydantic import BaseModel, Field, StringConstraints",
        "",
        "# #593: required request fields reject blank/whitespace-only input at the",
        "# model layer — the contract pins validation_error → 422 for it, and the",
        "# blank-input probe enforces it against the running app. Whitespace is",
        "# stripped before the length check, so '  ' is as blank as ''.",
        "NonBlankStr = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]",
        "",
    ]
    for entity in manifest.entities:
        lines.append(f"class {entity.name}(BaseModel):")
        if not entity.fields:
            lines.append("    pass")
        for f in entity.fields:
            ann = _py_type(f.type)
            if f.required and not f.has_default:
                lines.append(f"    {f.name}: {ann}")
            elif f.has_default and isinstance(f.default, list):
                lines.append(f"    {f.name}: {ann} = Field(default_factory=list)")
            elif f.has_default:
                lines.append(f"    {f.name}: {ann} = {f.default!r}")
            else:
                lines.append(f"    {f.name}: {ann} | None = None")
        lines.append("")

    for shape in manifest.api.request_shapes:
        lines.append(f"class {shape.name}(BaseModel):")
        if not shape.required and not shape.optional:
            lines.append("    pass")
        for name in shape.required:
            lines.append(f"    {name}: NonBlankStr")
        for name in shape.optional:
            lines.append(f"    {name}: str | None = None")
        lines.append("")
    return "\n".join(lines)


def _route_func_name(ep: Endpoint) -> str:
    slug = ep.path.strip("/").replace("{", "").replace("}", "").replace("/", "_")
    slug = slug.replace("-", "_") or "root"
    return f"{ep.method.lower()}_{slug}"


def _routes_source(manifest: InterfaceManifest) -> str:
    known_models = {e.name for e in manifest.entities} | {
        s.name for s in manifest.api.request_shapes
    }
    referenced: set[str] = set()
    for ep in manifest.api.endpoints:
        if ep.request and ep.request in known_models:
            referenced.add(ep.request)
        if ep.response:
            base = _base_type_name(ep.response)
            if base in known_models:
                referenced.add(base)
    import_line = f"from .models import {', '.join(sorted(referenced))}" if referenced else ""
    # The fill raises ApiError for the declared error codes, so the seam import is wired
    # into the frozen stub — that makes import_present(ApiError) a valid *interface*
    # criterion (it must pass on the bare skeleton, SIP-0098 §6.2), and the fill dev just
    # calls the already-imported symbol.
    errors_import = "from .errors import ApiError" if manifest.api.error_contract else ""
    # #603: the state container is scaffold-owned, so wire its import into the frozen
    # stub exactly as the error seam is. The fill then USES the store instead of
    # inventing a module for it — which is what pf-40 did, with a broken import.
    store_names = [f"{_snake(e.name)}_store" for e in manifest.entities]
    store_import = f"from .store import {', '.join(store_names)}" if store_names else ""
    import_block = "\n".join(
        ln
        for ln in (
            "from fastapi import APIRouter, HTTPException",
            import_line,
            errors_import,
            store_import,
        )
        if ln
    )
    error_codes = [
        c.code for c in (manifest.api.error_contract.codes if manifest.api.error_contract else ())
    ]
    codes_hint = (
        f"On failure raise ApiError(code, message) from .errors — codes: {', '.join(error_codes)}."
        if error_codes
        else "On failure raise ApiError(code, message) from .errors."
    )
    lines = [
        '"""API route stubs — scaffold-owned signatures, fill-only bodies.',
        "",
        "Every endpoint the interface manifest declares is wired here with its",
        "correct path, method, and response model. Bodies raise 501 until filled;",
        "the app imports and boots regardless.",
        "",
        "The router takes NO prefix. The frontend calls /api/... and the proxy strips",
        "that prefix before the request reaches this app, so these paths are already",
        "the full backend paths. Adding prefix= to APIRouter puts every route behind a",
        "second /api and the app answers 404 to its own contract (pf-41).",
        "",
        codes_hint,
        '"""',
        "",
        import_block,
        "",
        "router = APIRouter()",
        "",
    ]
    for ep in manifest.api.endpoints:
        fn = _route_func_name(ep)
        path_args = [p[1:-1] for p in ep.path.split("/") if p.startswith("{") and p.endswith("}")]
        params = [f"{a}: str" for a in path_args]
        if ep.request:
            params.append(f"payload: {ep.request}")
        sig = ", ".join(params)
        decorator = f'@router.{ep.method.lower()}("{ep.path}"'
        if ep.response:
            decorator += f", response_model={_py_type(ep.response)}"
        # The success status is *interface*, not implementation — it belongs to the
        # scaffold-owned decorator so the fill dev cannot drop it (pf-39).
        if ep.success_status is not None:
            decorator += f", status_code={ep.success_status}"
        decorator += ")"
        lines.append(decorator)
        lines.append(f"def {fn}({sig}):")
        summary = ep.summary or fn
        lines.append(f'    """{summary} — TODO: implement (scaffold stub)."""')
        lines.append('    raise HTTPException(status_code=501, detail="not implemented")')
        lines.append("")
    return "\n".join(lines)


_ERRORS_PY = '''"""Error contract rendering — scaffold-owned interface wiring.

The interface manifest pins one error envelope shape and a code->status map. Both
the ApiError exception (raise ApiError(code, message) from a route body) and the
request-validation handler render that exact shape, so a fill-only dev conforms
the contract by raising ApiError — never by hand-rendering JSON, and never by
editing this file. FastAPI's default validation error ({"detail": [...]}) fires
before any route body, so this handler is the only place it can be conformed.
"""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

# code -> HTTP status, generated from the manifest error_contract.
_ERROR_STATUS: dict[str, int] = __STATUS_MAP__


class ApiError(Exception):
    """Raise from a route body to emit the pinned {"error": {...}} envelope."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = _ERROR_STATUS.get(code, 400)


def _envelope(code: str, message: str) -> dict:
    return {"error": {"code": code, "message": message}}


async def _api_error_handler(request: Request, exc: ApiError) -> JSONResponse:
    return JSONResponse(status_code=exc.status_code, content=_envelope(exc.code, exc.message))


async def _validation_error_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    return JSONResponse(
        status_code=_ERROR_STATUS.get("validation_error", 422),
        content=_envelope("validation_error", "request validation failed"),
    )


def register_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(ApiError, _api_error_handler)
    app.add_exception_handler(RequestValidationError, _validation_error_handler)
'''


def _errors_source(manifest: InterfaceManifest) -> str:
    ec = manifest.api.error_contract
    codes = ec.codes if ec else ()
    if codes:
        entries = "\n".join(f'    "{c.code}": {c.http},' for c in codes)
        status_map = "{\n" + entries + "\n}"
    else:
        status_map = "{}"
    return _ERRORS_PY.replace("__STATUS_MAP__", status_map)


_MAIN_PY = '''"""FastAPI application entry point — scaffold-owned invariant bootstrap.

CORS origins come from the CORS_ORIGINS env var (comma-separated); the health
endpoint is the deterministic readiness probe. Error handlers render the pinned
error envelope. Business routes live in routes.py.
"""

from __future__ import annotations

import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .errors import register_error_handlers
from .routes import router

app = FastAPI(title="{project_id}")

_origins = [o.strip() for o in os.environ.get("CORS_ORIGINS", "*").split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins or ["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

register_error_handlers(app)


@app.get("/health")
def health() -> dict[str, str]:
    return {{"status": "ok"}}


app.include_router(router)
'''

_REQUIREMENTS_TXT = """fastapi>=0.115,<0.200
uvicorn[standard]>=0.30,<0.40
pydantic>=2.7,<3
"""

_INDEX_HTML = """<!doctype html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>{project_id}</title>
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.jsx"></script>
  </body>
</html>
"""

_PACKAGE_JSON = """{{
  "name": "{project_id}-frontend",
  "private": true,
  "version": "0.0.0",
  "type": "module",
  "scripts": {{
    "dev": "vite",
    "build": "vite build",
    "preview": "vite preview",
    "test": "vitest run"
  }},
  "dependencies": {{
    "react": "^18.3.1",
    "react-dom": "^18.3.1",
    "react-router-dom": "^6.26.2"
  }},
  "devDependencies": {{
    "@testing-library/dom": "^10.4.0",
    "@testing-library/jest-dom": "^6.5.0",
    "@testing-library/react": "^16.0.1",
    "@vitejs/plugin-react": "^4.3.1",
    "jsdom": "^25.0.1",
    "vite": "^5.4.2",
    "vitest": "^2.1.9"
  }}
}}
"""

_VITE_CONFIG = """import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// The /api proxy is dev-only; production serves the built assets behind a
// reverse proxy. Backend host/port are blueprint-owned, not interface.
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\\/api/, ''),
      },
    },
  },
  // #627: the frontend test harness is scaffold-owned, mirroring the backend
  // conftest. vitest reads this key; `vite build` ignores it.
  test: {
    environment: 'jsdom',
    setupFiles: ['src/test-setup.js'],
  },
})
"""

# Scaffold-owned vitest setup (frozen) — registers jest-dom matchers for every
# suite. The frontend mirror of the conftest ``client`` fixture: harness wiring
# is a workspace invariant, never a per-suite guess (#627 / pf-53: with no
# seeded harness, qa either refused to test or invented one that could not run).
_TEST_SETUP_JS = """// The /vitest entry registers jest-dom matchers on vitest's expect — the
// bare entry assumes a GLOBAL expect and crashes collection under vitest's
// default globals:false (caught on the real toolchain, not in review).
import '@testing-library/jest-dom/vitest'
"""

# Scaffold-owned harness proof (frozen). Renders the app shell at a path no
# route claims, so it passes on the bare skeleton AND after any fill — it
# asserts harness wiring (vitest + jsdom + Testing Library + router), never
# app behavior. Doubles as the in-workspace example of the testing idiom.
_HARNESS_TEST_JSX = """// Scaffold-owned harness proof (frozen): vitest + jsdom + Testing Library +
// router wiring all work in this workspace. Write real UI tests in NEW files
// beside this one (e.g. views.test.jsx) — render with MemoryRouter exactly as
// below; jest-dom matchers are already registered via src/test-setup.js.
import { describe, expect, it } from 'vitest'
import { render } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import App from '../App.jsx'

describe('frontend test harness', () => {
  it('renders the app shell under a memory router', () => {
    const { container } = render(
      <MemoryRouter initialEntries={['/__harness__']}>
        <App />
      </MemoryRouter>,
    )
    expect(container.querySelector('.app')).toBeInTheDocument()
  })
})
"""

_MAIN_JSX = """import React from 'react'
import ReactDOM from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import App from './App.jsx'

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <BrowserRouter>
      <App />
    </BrowserRouter>
  </React.StrictMode>,
)
"""

_API_JS = """// Scaffold-owned API client — the /api base path and error-envelope unwrapping
// are interface wiring, fixed here. Views call apiFetch('/path'); the /api prefix
// routes through the Vite dev proxy to the backend. A response carrying the pinned
// {"error": {code, message}} envelope is thrown as ApiError.
export class ApiError extends Error {
  constructor(code, message, status) {
    super(message)
    this.code = code
    this.status = status
  }
}

export async function apiFetch(path, options = {}) {
  const response = await fetch(`/api${path}`, {
    headers: { 'Content-Type': 'application/json', ...(options.headers || {}) },
    ...options,
  })
  if (!response.ok) {
    let body = null
    try {
      body = await response.json()
    } catch {
      // non-JSON error body
    }
    const err = (body && body.error) || {}
    throw new ApiError(err.code || 'error', err.message || response.statusText, response.status)
  }
  if (response.status === 204) return null
  return response.json()
}
"""


def _app_jsx(manifest: InterfaceManifest) -> str:
    routes = manifest.frontend.routes
    imports = "\n".join(f"import {r.view} from './views/{r.view}.jsx'" for r in routes)
    route_els = "\n".join(
        f'        <Route path="{r.path}" element={{<{r.view} />}} />' for r in routes
    )
    return (
        "import { Routes, Route } from 'react-router-dom'\n"
        + imports
        + "\n\n"
        + "// App wiring is scaffold-owned: routes and their component imports are\n"
        + "// fixed by the interface manifest. Add a route by amending the manifest\n"
        + "// and re-expanding, never by editing this file by hand.\n"
        + "export default function App() {\n"
        + "  return (\n"
        + '    <div className="app">\n'
        + "      <Routes>\n"
        + route_els
        + "\n      </Routes>\n"
        + "    </div>\n"
        + "  )\n"
        + "}\n"
    )


def _view_stub(route: Route) -> str:
    purpose = route.purpose or route.view
    # #659: the root anchor is stamped on the stub container so it exists from
    # the bare skeleton onward; the fill inherits it in place. The full anchor
    # inventory rides as a comment because the stub has no other elements yet —
    # the dev prompt (testid surface appendix) carries the binding instruction.
    root_attr = f' data-testid="{route.testids[0]}"' if route.testids else ""
    anchor_comment = (
        f"  // DOM anchors (manifest-pinned, keep every one): {', '.join(route.testids)}\n"
        if route.testids
        else ""
    )
    return (
        "// Scaffold-owned slot: fill this component's body. The default export\n"
        "// name and file path are fixed by the interface manifest. Fetch backend\n"
        "// data via apiFetch from '../api.js' (handles the /api prefix + errors).\n"
        f"export default function {route.view}() {{\n"
        f"  // TODO: {purpose}\n"
        f"{anchor_comment}"
        f"  return <div{root_attr}>{route.view}</div>\n"
        "}\n"
    )


# Scaffold-owned pytest anchor (frozen) — the SINGLE source of the test import root.
# Puts the workspace root on sys.path so ``import backend`` resolves regardless of
# pytest's CWD, and owns the app import behind a ``client`` fixture. Suites fill bodies
# against ``client`` and never author ``from <root>.main import app`` themselves — so the
# package root is a scaffold invariant, not a per-suite guess (the pf-26 divergence:
# files under backend/ but the qa test invented ``from app.main import app``).
_CONFTEST_PY = '''"""Scaffold-owned pytest anchor (frozen) — the single source of the import root.

Puts the workspace root on sys.path so ``import backend`` resolves regardless of the
working directory pytest runs from, and exposes ``client`` as the ONE place the app is
imported. Test suites fill bodies against ``client``; they never author the app import.
"""

import os
import sys

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from backend.main import app  # noqa: E402  -- after the sys.path anchor above


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)
'''


def _snake(name: str) -> str:
    """``RunEvent`` → ``run_event``. Deterministic, so the store's names are stable."""
    out: list[str] = []
    for i, ch in enumerate(name):
        if ch.isupper() and i and not name[i - 1].isupper():
            out.append("_")
        out.append(ch.lower())
    return "".join(out)


def _store_source(manifest: InterfaceManifest) -> str:
    """The in-memory state container (#603).

    The manifest declares ``persistence: in_memory`` and the skeleton used to emit
    nothing that held the data. The planner therefore invented a module on every roll
    — reasonable engineering given an incomplete skeleton, but an invented file is
    outside every safety net: nothing freezes it, no contract criterion names it, and
    its imports are guessed fresh each time. pf-40 died exactly there, on a
    ``from models import ...`` that was missing the leading dot, so the app never
    started and the behavioural probe could not run at all.

    Emitting it makes the imports correct by construction and brings the file under
    scaffold ownership. One dict per declared entity, keyed by the entity's id.
    """
    entities = [e.name for e in manifest.entities]
    lines = [
        '"""In-memory state — scaffold-owned (frozen).',
        "",
        "The manifest declares in-memory persistence, so this module owns it: one store",
        "per declared entity, keyed by the entity's id. Fill route bodies against these",
        "names; do not define a second store elsewhere and do not edit this file.",
        '"""',
        "",
        "from __future__ import annotations",
        "",
    ]
    if entities:
        lines.append(f"from .models import {', '.join(sorted(entities))}")
        lines.append("")
    for name in entities:
        lines.append(f"{_snake(name)}_store: dict[str, {name}] = {{}}")
    if entities:
        lines.append("")
    lines.append("")
    lines.append("def reset() -> None:")
    lines.append('    """Clear every store — for test isolation between cases."""')
    if entities:
        for name in entities:
            lines.append(f"    {_snake(name)}_store.clear()")
    else:
        lines.append("    return None")
    lines.append("")
    return "\n".join(lines)


def _expand_fullstack_fastapi_react(manifest: InterfaceManifest) -> list[dict[str, str]]:
    files: list[dict[str, str]] = []

    # ---- backend (FastAPI, in-memory) ----
    files.append({"name": "backend/__init__.py", "content": ""})
    files.append(
        {"name": "backend/main.py", "content": _MAIN_PY.format(project_id=manifest.project_id)}
    )
    files.append({"name": "backend/models.py", "content": _model_source(manifest)})
    files.append({"name": "backend/store.py", "content": _store_source(manifest)})
    files.append({"name": "backend/errors.py", "content": _errors_source(manifest)})
    files.append({"name": "backend/routes.py", "content": _routes_source(manifest)})
    files.append({"name": "backend/requirements.txt", "content": _REQUIREMENTS_TXT})
    # Frozen pytest anchor: pins the import root so suites don't each guess it.
    files.append({"name": "conftest.py", "content": _CONFTEST_PY})

    # ---- frontend (React + Vite) ----
    files.append(
        {
            "name": "frontend/index.html",
            "content": _INDEX_HTML.format(project_id=manifest.project_id),
        }
    )
    files.append(
        {
            "name": "frontend/package.json",
            "content": _PACKAGE_JSON.format(project_id=manifest.project_id),
        }
    )
    files.append({"name": "frontend/vite.config.js", "content": _VITE_CONFIG})
    files.append({"name": "frontend/src/test-setup.js", "content": _TEST_SETUP_JS})
    files.append({"name": "frontend/src/__tests__/harness.test.jsx", "content": _HARNESS_TEST_JSX})
    files.append({"name": "frontend/src/main.jsx", "content": _MAIN_JSX})
    files.append({"name": "frontend/src/api.js", "content": _API_JS})
    files.append({"name": "frontend/src/App.jsx", "content": _app_jsx(manifest)})
    for route in manifest.frontend.routes:
        files.append({"name": f"frontend/src/views/{route.view}.jsx", "content": _view_stub(route)})

    return files


def _fill_slots_fullstack_fastapi_react(manifest: InterfaceManifest) -> tuple[str, ...]:
    """The route bodies, plus one component per declared route."""
    views = tuple(f"frontend/src/views/{r.view}.jsx" for r in manifest.frontend.routes)
    return ("backend/routes.py", *dict.fromkeys(views))


@dataclass(frozen=True)
class ScaffoldStack:
    """Everything the scaffold knows about one stack, in one place (#S1).

    These five facts were four module-level dicts and one function with the answer written
    inline. Spread out, each new stack had to remember to appear in five places, and
    forgetting produced a *plausible* wrong answer rather than an error — ``fill_slot_paths``
    guarded on whether a stack was registered and then returned FastAPI's slot map to
    whoever asked, so a second stack would have inherited ``backend/routes.py`` silently.

    Deliberately **today's fields and nothing more**. Naming it ``ScaffoldStack`` rather than
    a blueprint is also deliberate: the Stack Blueprint SIP is not accepted, its schema is
    meant to be written against two real stacks, and a consolidation that quietly minted its
    vocabulary would prejudge exactly the question that SIP exists to answer.
    """

    name: str
    #: Manifest → the walking skeleton, as ``{"name", "content"}`` files.
    expand: Callable[[InterfaceManifest], list[dict[str, str]]]
    #: Manifest → the files a dev fills bodies into. Everything else ``expand`` emits is
    #: frozen; the verification contract pins those by hash and hangs criteria only on these.
    fill_slots: Callable[[InterfaceManifest], tuple[str, ...]]
    #: SIP-0100 D1: workspace-relative directory prefixes that own QA test files. A QA file
    #: outside this surface is an unauthorized write.
    qa_test_namespace: tuple[str, ...] = ()
    #: SIP-0100 harness boundary: app entry modules a QA test must NOT import — it consumes
    #: the scaffold-owned ``client`` fixture instead. ``app.main``/``main`` are the recurring
    #: wrong guesses that killed pf-25/26.
    harness_entry_modules: tuple[str, ...] = ()
    #: #503: the stack name the typed-check evaluators are keyed on, which is the CHECK
    #: implementation's vocabulary rather than the scaffold's — "fastapi", not the profile
    #: name. Empty means the checks skip, which is the conservative default #503 chose.
    check_stack: str = ""
    #: #818: the verification-criteria pack ``scaffold_contract`` emits for this stack —
    #: which kinds of fill slot it has, what evidence proves each kind, and what proves the
    #: deliverable builds and its suite ran. A *name*, not a callable, so the check
    #: vocabulary stays in the emitter layer; same indirection as ``check_stack``.
    #:
    #: **The default is deliberately asymmetric with ``check_stack``.** An unset
    #: ``check_stack`` means the typed checks *skip*, and a skip is safe because
    #: ``CheckOutcome.skipped`` is not executed-and-passed under SIP-0096 — it surfaces as
    #: unverified. An unset ``criteria_pack`` means the emitter **refuses**, because the
    #: failure it prevents is not a missing check but a *wrong* contract: before #818 a
    #: stack with no pack fell through to the FastAPI view branch and derived a contract
    #: that every gate accepted. Visible-and-unverified has a safe default; silently-wrong
    #: does not.
    criteria_pack: str = ""
    #: #822: the probe-boot profile ``handlers.probe_runner`` uses to stand this stack's app
    #: up for behavioral probes — the launcher and entry point (``uvicorn backend.main:app``
    #: vs ``node dist/server.js``) and the readiness path. A *name*, like ``criteria_pack``,
    #: so the boot vocabulary stays in the runner layer.
    #:
    #: **Not derived from the sandbox ``EnvironmentContract``**, which also carries a
    #: ``START_APPLICATION`` command: that argv runs *inside the sandbox container*, where
    #: ``INSTALL_DEPENDENCIES`` built ``.sandbox-venv``. Probes run in the qa container
    #: against a fresh temp dir with no venv, on ``sys.executable``. Two execution contexts,
    #: not one fact duplicated — the interpreter is context-specific, only the launcher and
    #: entry point are stack-specific.
    probe_profile: str = ""
    #: #832: the ``DEV_CAPABILITIES`` entry this stack requires — the prompt text,
    #: ``expected_extensions``, ``source_filter`` and ``test_framework`` a dev agent is given.
    #: A *name*, like the two fields above, so the capability vocabulary stays in its layer.
    #:
    #: Exists because a cycle declared its stack **twice**: ``build_profile`` selecting this
    #: registry and ``dev_capability`` selecting that one, the same literal on adjacent CRP
    #: lines, bound by convention alone. Nothing stopped a cycle from expanding one stack's
    #: skeleton while instructing the dev agent to write another stack's files — every
    #: emission landing outside the fill slots, surfacing only as a plan that claims nothing.
    #:
    #: Not a collapse of the two registries: ``python_cli``, ``python_api`` and ``react_app``
    #: are free-form capabilities for cycles with no scaffold stack at all. Not every dev
    #: capability is a stack; every stack needs one.
    dev_capability: str = ""


_STACKS: dict[str, ScaffoldStack] = {
    "fullstack_fastapi_react": ScaffoldStack(
        name="fullstack_fastapi_react",
        expand=_expand_fullstack_fastapi_react,
        fill_slots=_fill_slots_fullstack_fastapi_react,
        qa_test_namespace=("backend/tests/", "frontend/src/tests/"),
        harness_entry_modules=("backend.main", "app.main", "main"),
        check_stack="fastapi",
        # Today a pack is named for the stack that needs it; the indirection exists so a
        # later stack can share one (a FastAPI+Vue stack wants these same backend criteria)
        # without minting a fourth stack vocabulary to express it.
        criteria_pack="fullstack_fastapi_react",
        probe_profile="fastapi_uvicorn",
        dev_capability="fullstack_fastapi_react",
    ),
    # #822 stack #2. Imported below rather than defined here: a second expander inline would
    # push this module past 2000 lines and interleave two stacks' source templates. Extracting
    # stack #1 to match is a follow-up refactor, deliberately not bundled — it would move
    # bytes the reference contract is pinned to.
    _NEXTJS_TS_NAME: ScaffoldStack(
        name=_NEXTJS_TS_NAME,
        expand=_expand_nextjs_ts,
        fill_slots=_fill_slots_nextjs_ts,
        # Co-located `__tests__/` beside source, not a directory prefix at the tree root —
        # one of the three FastAPI-shaped assumptions S2 selected this stack to break.
        qa_test_namespace=("__tests__/", "app/", "lib/"),
        # Node module resolution has no import boundary between tests and app, so there is
        # no equivalent of `backend.main` to forbid. Declared empty as a fact, not an omission.
        harness_entry_modules=(),
        # Empty: the typed-check evaluators are Python AST implementations and were never
        # verified against this stack, so they skip rather than being fed a guess (#503's
        # conservative default, and #822 bend 6).
        check_stack="",
        criteria_pack=_NEXTJS_TS_NAME,
        probe_profile="nextjs_next_start",
        dev_capability=_NEXTJS_TS_NAME,
    ),
}


def _stack(stack: str) -> ScaffoldStack:
    """The registered stack, or the same refusal every accessor used to raise separately."""
    known = _STACKS.get(stack)
    if known is None:
        raise ValueError(f"no scaffold expander for stack {stack!r}; available: {sorted(_STACKS)}")
    return known


def check_stack_for(stack: str) -> str | None:
    """The typed-check evaluator vocabulary for ``stack``, or ``None`` (#503).

    Lives here so "which stacks does this system know?" has one answer. The mapping is
    conservative by design: an unmapped stack yields ``None`` and its checks skip, rather
    than being fed a guess the evaluators were never verified against.
    """
    known = _STACKS.get(stack)
    return (known.check_stack or None) if known else None


def criteria_pack_for(stack: str) -> str:
    """The verification-criteria pack ``stack`` declares, or ``""`` (#818).

    Companion to :func:`check_stack_for`, and the same reason for existing: the stack
    registry is the one place that answers "what does this stack use". Returning the empty
    string for an unknown or undeclaring stack keeps this accessor total; the *refusal*
    belongs to the emitter, which is the layer that knows a missing pack means it cannot
    produce a correct contract.
    """
    known = _STACKS.get(stack)
    return known.criteria_pack if known else ""


def probe_profile_for(stack: str) -> str:
    """The probe-boot profile ``stack`` declares, or ``""`` (#822).

    Total, like :func:`criteria_pack_for`: what to *do* about an undeclared profile belongs
    to the probe runner, whose caller treats probes as additive evidence that may report
    not-executed but must never raise.
    """
    known = _STACKS.get(stack)
    return known.probe_profile if known else ""


def dev_capability_for(stack: str) -> str:
    """The ``DEV_CAPABILITIES`` entry ``stack`` requires, or ``""`` (#832)."""
    known = _STACKS.get(stack)
    return known.dev_capability if known else ""


def resolve_dev_capability(resolved_config: Mapping[str, Any] | None) -> str | None:
    """The dev capability a cycle actually runs, or ``None`` if its config contradicts itself.

    One rule (#832): **the stack declares it; the config may restate it but not contradict
    it.** A ``build_profile`` naming a scaffoldable stack is the authority, so an absent
    ``dev_capability`` is derived rather than defaulted to ``python_cli`` — which is how a
    fullstack cycle could otherwise be handed CLI prompts.

    ``None`` means *contradiction*, and is deliberately distinguished from ``""``: the caller
    is preflight, which must reject rather than silently pick a side. Overriding an explicit
    config value would hide the drift instead of ending it.

    A cycle with no scaffoldable ``build_profile`` is a free-form generation cycle
    (``python_cli``, ``react_app``); its ``dev_capability`` is returned untouched.
    """
    config = resolved_config or {}
    declared = str(config.get("dev_capability") or "")
    required = dev_capability_for(str(config.get("build_profile") or ""))
    if not required:
        return declared
    if declared and declared != required:
        return None
    return required


def scaffold_stack_for(resolved_config: Mapping[str, Any] | None) -> str:
    """The scaffold stack a cycle's config names, or ``""`` (#822).

    Sibling of ``cycles.acceptance_evaluation.resolve_check_stack``, and deliberately not the
    same function: that one maps ``build_profile`` through to the *evaluator* vocabulary
    (``"fastapi"``), while boot profiles are keyed on the scaffold stack itself
    (``"fullstack_fastapi_react"``). Collapsing them would reintroduce the vocabulary
    confusion S3 still owes a reconciliation for.
    """
    config = resolved_config or {}
    profile = config.get("build_profile")
    return str(profile) if profile and str(profile) in _STACKS else ""
