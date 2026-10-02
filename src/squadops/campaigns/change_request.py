"""The typed change request: a proposal's only output, and its rails (SIP-0109 §7.2, §9.1; #1706).

The strategy role authors a change request; everything here is the framework's, and pure:
- ``parse_change_request`` reads the authored document into the typed shape, and refuses what
  the role may not author (the footprint, the content hash);
- ``apply_manifest_delta`` applies the typed delta to the accepted manifest, operation by
  operation, and refuses an operation that does not fit it;
- ``derive_footprint`` derives the files the change may touch from the stack's own scaffold map:
  every product file whose expansion the delta changes, plus the stack's qa test namespace;
- ``validate_proposal`` runs the rails in order and returns the change request or every
  refusal. An out-of-scope proposal is refused, never trimmed (§9.1), and a delta the SIP-0103
  manifest gates refuse is refused with their findings (§7.2).
"""

from __future__ import annotations

import copy
import dataclasses
import hashlib
import json
from dataclasses import dataclass, field
from enum import StrEnum
from fnmatch import fnmatch
from typing import Any

import yaml

# =============================================================================
# The shape (§7.2)
# =============================================================================


class ChangeKind(StrEnum):
    FEATURE = "feature"
    FIX = "fix"
    #: Adds no discriminating tests (§8.2), so it may carry no new criteria.
    REFACTOR = "refactor"


class PrdOp(StrEnum):
    ADD = "add"
    MODIFY = "modify"
    RETIRE = "retire"


class DeltaOp(StrEnum):
    ADD = "add"
    MODIFY = "modify"
    REMOVE = "remove"


class DeltaTarget(StrEnum):
    """What a manifest operation acts on, and how it is keyed in the manifest."""

    ENTITY = "entity"  # by name
    REQUEST_SHAPE = "request_shape"  # by name
    ENDPOINT = "endpoint"  # by "METHOD /path"
    CLIENT_ROUTE = "client_route"  # by path
    ERROR_CODE = "error_code"  # by code


class SurfaceKind(StrEnum):
    """A criterion's public surface: something a caller or a browser reaches (§7.2)."""

    ENDPOINT = "endpoint"
    CLIENT_ROUTE = "client_route"


@dataclass(frozen=True)
class PrdSection:
    id: str
    op: PrdOp
    text: str = ""


@dataclass(frozen=True)
class ManifestOperation:
    """One typed operation. ``definition`` is the target's whole new definition, in the
    manifest's own form, for ``add`` and ``modify``; ``None`` for ``remove``."""

    op: DeltaOp
    target: DeltaTarget
    key: str
    definition: dict | None = None


@dataclass(frozen=True)
class Criterion:
    id: str
    statement: str
    surface_kind: SurfaceKind
    #: ``"METHOD /path"`` for an endpoint, the path for a client route.
    surface: str
    #: What the criterion's test observes there.
    observable: str


@dataclass(frozen=True)
class Retirement:
    criterion_id: str
    reason: str


@dataclass(frozen=True)
class ChangeRequest:
    """§7.2's typed change request. ``footprint`` and ``content_hash`` are the framework's:
    derived from the delta and computed over the content, never authored."""

    proposal_id: str
    version: int
    baseline_tree: str
    kind: ChangeKind
    prd_delta: tuple[PrdSection, ...]
    manifest_delta: tuple[ManifestOperation, ...]
    criteria: tuple[Criterion, ...]
    must_not_break: tuple[str, ...]
    retires: tuple[Retirement, ...] = ()
    replaces_verifiers: tuple[Retirement, ...] = ()
    footprint: tuple[str, ...] = ()
    content_hash: str = ""


class RefusalKind(StrEnum):
    MALFORMED = "malformed"
    AUTHORED_DERIVED_FIELD = "authored_derived_field"
    DELTA_DOES_NOT_FIT = "delta_does_not_fit"
    MANIFEST_GATES = "manifest_gates"
    OUT_OF_SCOPE = "out_of_scope"
    UNKNOWN_SURFACE = "unknown_surface"
    UNKNOWN_PRIOR_CRITERION = "unknown_prior_criterion"
    KEEP_AND_RETIRE = "keep_and_retire"
    NO_CRITERIA = "no_criteria"


@dataclass(frozen=True)
class ProposalRefusal:
    kind: RefusalKind
    detail: str


@dataclass(frozen=True)
class ProposalVerdict:
    """The rails' answer: the change request, or every refusal (never only the first)."""

    change_request: ChangeRequest | None
    refusals: tuple[ProposalRefusal, ...] = ()
    candidate_manifest: str = ""

    @property
    def accepted(self) -> bool:
        return self.change_request is not None and not self.refusals


class ChangeRequestError(ValueError):
    """An authored document that does not have the change request's shape."""


# =============================================================================
# Parsing the authored document
# =============================================================================

#: Fields the framework derives; a document that authors them is refused, not corrected.
_DERIVED_FIELDS = ("footprint", "content_hash", "proposal_id", "version", "baseline_tree")


def parse_change_request(
    authored: dict, *, proposal_id: str, version: int, baseline_tree: str
) -> ChangeRequest:
    """The typed change request an authored document describes.

    Raises:
        ChangeRequestError: If a required field is missing, a value is outside its vocabulary,
            or the document authors a field the framework derives.
    """
    if not isinstance(authored, dict):
        raise ChangeRequestError("a change request is a mapping")
    authored_derived = [f for f in _DERIVED_FIELDS if f in authored]
    if authored_derived:
        raise ChangeRequestError(
            f"the framework derives {', '.join(authored_derived)}; the proposal may not author it"
        )
    try:
        request = ChangeRequest(
            proposal_id=proposal_id,
            version=version,
            baseline_tree=baseline_tree,
            kind=ChangeKind(authored["kind"]),
            prd_delta=tuple(
                PrdSection(id=_text(s, "id"), op=PrdOp(s["op"]), text=str(s.get("text", "")))
                for s in authored.get("prd_delta") or ()
            ),
            manifest_delta=tuple(
                ManifestOperation(
                    op=DeltaOp(o["op"]),
                    target=DeltaTarget(o["target"]),
                    key=_text(o, "key"),
                    definition=o.get("definition"),
                )
                for o in authored.get("manifest_delta") or ()
            ),
            criteria=tuple(
                Criterion(
                    id=_text(c, "id"),
                    statement=_text(c, "statement"),
                    surface_kind=SurfaceKind(c["surface_kind"]),
                    surface=_text(c, "surface"),
                    observable=_text(c, "observable"),
                )
                for c in authored.get("criteria") or ()
            ),
            must_not_break=tuple(str(i) for i in authored.get("must_not_break") or ()),
            retires=_retirements(authored.get("retires")),
            replaces_verifiers=_retirements(authored.get("replaces_verifiers")),
        )
    except (KeyError, TypeError, ValueError) as e:
        if isinstance(e, ChangeRequestError):
            raise
        raise ChangeRequestError(f"not a change request: {e!r}") from e
    for op in request.manifest_delta:
        if (op.op is DeltaOp.REMOVE) != (op.definition is None):
            raise ChangeRequestError(
                f"{op.op} {op.target} {op.key!r}: add and modify carry the whole new definition; "
                "remove carries none"
            )
    return request


def load_stored_change_request(document: str) -> ChangeRequest:
    """A change request as the proposal run stored it (``change_request.yaml``): the authored
    content, parsed by the one parse, with the framework's derived fields restored. The stored
    hash must be the content's, so a document altered after it was ruled on is refused."""
    data = yaml.safe_load(document)
    if not isinstance(data, dict):
        raise ChangeRequestError("a stored change request is a mapping")
    try:
        request = parse_change_request(
            {k: v for k, v in data.items() if k not in _DERIVED_FIELDS},
            proposal_id=str(data["proposal_id"]),
            version=int(data["version"]),
            baseline_tree=str(data["baseline_tree"]),
        )
    except KeyError as e:
        raise ChangeRequestError(f"the stored change request has no {e}") from e
    stored_hash = str(data.get("content_hash") or "")
    if content_hash(request) != stored_hash:
        raise ChangeRequestError("the stored change request's content does not match its hash")
    return dataclasses.replace(
        request, footprint=tuple(data.get("footprint") or ()), content_hash=stored_hash
    )


def _text(raw: Any, key: str) -> str:
    value = raw[key]
    if not isinstance(value, str) or not value.strip():
        raise ChangeRequestError(f"{key} is required text")
    return value


def _retirements(raw: Any) -> tuple[Retirement, ...]:
    return tuple(
        Retirement(criterion_id=_text(r, "criterion_id"), reason=_text(r, "reason"))
        for r in raw or ()
    )


def content_hash(request: ChangeRequest) -> str:
    """The hash a ruling binds to (§9.2): the authored content, not the derived fields or the
    proposal's identity."""
    payload = dataclasses.asdict(request)
    for derived in ("footprint", "content_hash", "proposal_id", "version", "baseline_tree"):
        payload.pop(derived)
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


# =============================================================================
# Applying the delta to the accepted manifest
# =============================================================================


class DeltaDoesNotFit(ValueError):
    """An operation that does not fit the manifest it is applied to."""


def apply_manifest_delta(baseline_manifest: str, delta: tuple[ManifestOperation, ...]) -> str:
    """The manifest the delta produces from the accepted one, as YAML.

    Raises:
        DeltaDoesNotFit: For each operation that does not fit, all of them in one message: an
            ``add`` of something present, a ``modify`` or ``remove`` of something absent, or a
            definition whose own key disagrees with the operation's.
    """
    manifest = copy.deepcopy(yaml.safe_load(baseline_manifest))
    problems = []
    for op in delta:
        try:
            _apply(manifest, op)
        except DeltaDoesNotFit as e:
            problems.append(str(e))
    if problems:
        raise DeltaDoesNotFit("; ".join(problems))
    return yaml.safe_dump(manifest, sort_keys=False)


def _apply(manifest: dict, op: ManifestOperation) -> None:
    api = manifest.setdefault("api", {})
    if op.target is DeltaTarget.ENTITY:
        _apply_to_list(manifest.setdefault("entities", []), op, lambda e: e.get("name"))
    elif op.target is DeltaTarget.ENDPOINT:
        _apply_to_list(
            api.setdefault("endpoints", []),
            op,
            lambda e: f"{str(e.get('method', '')).upper()} {e.get('path')}",
        )
    elif op.target is DeltaTarget.CLIENT_ROUTE:
        _apply_to_list(
            manifest.setdefault("frontend", {}).setdefault("routes", []),
            op,
            lambda r: r.get("path"),
        )
    elif op.target is DeltaTarget.REQUEST_SHAPE:
        _apply_to_mapping(api.setdefault("request_shapes", {}), op)
    elif op.target is DeltaTarget.ERROR_CODE:
        _apply_to_mapping(api.setdefault("error_contract", {}).setdefault("codes", {}), op)


def _apply_to_list(items: list, op: ManifestOperation, key_of) -> None:
    index = next((i for i, item in enumerate(items) if key_of(item) == op.key), None)
    if op.op is DeltaOp.ADD:
        if index is not None:
            raise DeltaDoesNotFit(f"add {op.target} {op.key!r}: it already exists")
        _check_definition_key(op, key_of)
        items.append(copy.deepcopy(op.definition))
    elif index is None:
        raise DeltaDoesNotFit(f"{op.op} {op.target} {op.key!r}: it does not exist")
    elif op.op is DeltaOp.MODIFY:
        _check_definition_key(op, key_of)
        items[index] = copy.deepcopy(op.definition)
    else:
        del items[index]


def _check_definition_key(op: ManifestOperation, key_of) -> None:
    if not isinstance(op.definition, dict) or key_of(op.definition) != op.key:
        raise DeltaDoesNotFit(
            f"{op.op} {op.target} {op.key!r}: its definition names {key_of(op.definition or {})!r}"
        )


def _apply_to_mapping(items: dict, op: ManifestOperation) -> None:
    present = op.key in items
    if op.op is DeltaOp.ADD and present:
        raise DeltaDoesNotFit(f"add {op.target} {op.key!r}: it already exists")
    if op.op is not DeltaOp.ADD and not present:
        raise DeltaDoesNotFit(f"{op.op} {op.target} {op.key!r}: it does not exist")
    if op.op is DeltaOp.REMOVE:
        del items[op.key]
    else:
        items[op.key] = copy.deepcopy(op.definition)


# =============================================================================
# The footprint (§7.2: derived by the stack's scaffold map, never authored)
# =============================================================================


def derive_footprint(baseline_manifest: str, candidate_manifest: str) -> tuple[str, ...]:
    """The files the change may touch: each product file whose expansion differs between the
    accepted manifest and the delta's (added, changed or removed), plus the stack's qa test
    namespace as ``<dir>**`` patterns. Sorted, so equal deltas give equal footprints."""
    from squadops.capabilities.scaffold import InterfaceManifest, expand, qa_test_namespace

    before = InterfaceManifest.from_yaml(baseline_manifest)
    after = InterfaceManifest.from_yaml(candidate_manifest)
    old = {f["name"]: f["content"] for f in expand(before)}
    new = {f["name"]: f["content"] for f in expand(after)}
    namespace = qa_test_namespace(after)
    changed = {
        name
        for name in old.keys() | new.keys()
        if old.get(name) != new.get(name) and not name.startswith(namespace)
    }
    return tuple(sorted(changed)) + tuple(f"{prefix}**" for prefix in namespace)


def in_footprint(path: str, footprint: tuple[str, ...]) -> bool:
    return any(fnmatch(path, pattern) for pattern in footprint)


# =============================================================================
# The rails, in order
# =============================================================================


@dataclass(frozen=True)
class ProposalContext:
    """What the rails read beside the authored document (§9.1's inputs)."""

    proposal_id: str
    version: int
    baseline_tree: str
    baseline_manifest: str
    expected_stack: str
    #: The objective's allowed scope: path patterns the footprint must stay within.
    allowed_scope: tuple[str, ...]
    #: The ids of the criteria frozen by earlier accepted increments.
    prior_criteria: tuple[str, ...] = field(default_factory=tuple)


def validate_proposal(authored: dict, context: ProposalContext) -> ProposalVerdict:
    """Every rail, every refusal. A malformed document or a delta that does not fit stops the
    rails that need a candidate manifest; the rest still run."""
    try:
        request = parse_change_request(
            authored,
            proposal_id=context.proposal_id,
            version=context.version,
            baseline_tree=context.baseline_tree,
        )
    except ChangeRequestError as e:
        kind = (
            RefusalKind.AUTHORED_DERIVED_FIELD
            if "the framework derives" in str(e)
            else RefusalKind.MALFORMED
        )
        return ProposalVerdict(None, (ProposalRefusal(kind, str(e)),))

    refusals = _criteria_refusals(request, context)
    try:
        candidate = apply_manifest_delta(context.baseline_manifest, request.manifest_delta)
    except DeltaDoesNotFit as e:
        return ProposalVerdict(
            None, (ProposalRefusal(RefusalKind.DELTA_DOES_NOT_FIT, str(e)), *refusals)
        )

    from squadops.cycles.manifest_gates import assess_winnability

    for finding in assess_winnability(candidate, context.expected_stack):
        refusals.append(
            ProposalRefusal(RefusalKind.MANIFEST_GATES, f"{finding.proof}: {finding.detail}")
        )
    if any(r.kind is RefusalKind.MANIFEST_GATES for r in refusals):
        return ProposalVerdict(None, tuple(refusals), candidate)

    footprint = derive_footprint(context.baseline_manifest, candidate)
    outside = [
        p
        for p in footprint
        if not any(
            fnmatch(p, scope) or p.startswith(scope.rstrip("*")) for scope in context.allowed_scope
        )
    ]
    if outside:
        refusals.append(
            ProposalRefusal(
                RefusalKind.OUT_OF_SCOPE,
                f"the delta reaches {', '.join(outside)}, outside the objective's allowed scope "
                f"({', '.join(context.allowed_scope)}); a proposal is refused, never trimmed",
            )
        )
    refusals.extend(_surface_refusals(request, candidate))
    if refusals:
        return ProposalVerdict(None, tuple(refusals), candidate)
    final = dataclasses.replace(request, footprint=footprint)
    return ProposalVerdict(
        dataclasses.replace(final, content_hash=content_hash(final)), (), candidate
    )


def _criteria_refusals(request: ChangeRequest, context: ProposalContext) -> list[ProposalRefusal]:
    refusals: list[ProposalRefusal] = []
    if request.kind is not ChangeKind.REFACTOR and not request.criteria:
        refusals.append(
            ProposalRefusal(
                RefusalKind.NO_CRITERIA,
                f"a {request.kind} adds behaviour, so it names at least one criterion (§8.2)",
            )
        )
    prior = set(context.prior_criteria)
    retired = {r.criterion_id for r in (*request.retires, *request.replaces_verifiers)}
    unknown = sorted((set(request.must_not_break) | retired) - prior)
    if unknown:
        refusals.append(
            ProposalRefusal(
                RefusalKind.UNKNOWN_PRIOR_CRITERION,
                f"no earlier increment froze {', '.join(unknown)}",
            )
        )
    both = sorted(set(request.must_not_break) & {r.criterion_id for r in request.retires})
    if both:
        refusals.append(
            ProposalRefusal(
                RefusalKind.KEEP_AND_RETIRE, f"{', '.join(both)} cannot be both kept and retired"
            )
        )
    return refusals


def _surface_refusals(request: ChangeRequest, candidate: str) -> list[ProposalRefusal]:
    """Each criterion's public surface must exist in the manifest the delta produces."""
    manifest = yaml.safe_load(candidate)
    endpoints = {
        f"{str(e.get('method', '')).upper()} {e.get('path')}"
        for e in (manifest.get("api") or {}).get("endpoints") or ()
    }
    routes = {r.get("path") for r in (manifest.get("frontend") or {}).get("routes") or ()}
    refusals = []
    for c in request.criteria:
        surfaces = endpoints if c.surface_kind is SurfaceKind.ENDPOINT else routes
        if c.surface not in surfaces:
            refusals.append(
                ProposalRefusal(
                    RefusalKind.UNKNOWN_SURFACE,
                    f"criterion {c.id}: no {c.surface_kind} {c.surface!r} in the manifest the "
                    "delta produces",
                )
            )
    return refusals
