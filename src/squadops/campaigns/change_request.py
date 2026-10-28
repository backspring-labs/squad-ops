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
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from enum import StrEnum
from fnmatch import fnmatch
from typing import Any

import yaml

from squadops.campaigns.criterion_placement import RunnerPlacement, Unplaceable, place_criterion
from squadops.cycles.acceptance_check_spec import parse_method_path
from squadops.cycles.manifest_gates import assess_winnability
from squadops.cycles.verification_contract import VerificationContract
from squadops.stacks.scaffold import (
    MANIFEST_ELEMENT_KEYS,
    InterfaceManifest,
    expand,
    is_qa_test_path_for_stack,
    qa_test_namespace,
    qa_test_namespace_for_stack,
    undefined_manifest_keys,
)
from squadops.stacks.scaffold_contract import emit_contract_dict

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
    """A criterion's public surface: something a caller or a browser reaches (§7.2). On a
    repository-backed Project, also a command-line entry point or a package's public interface,
    whichever the derived profile names (§24bv point 5)."""

    ENDPOINT = "endpoint"
    CLIENT_ROUTE = "client_route"
    COMMAND = "command"
    PACKAGE = "package"


class IncrementBasis(StrEnum):
    """What an increment's accepted tree is, as its launch's ``campaign_proposal`` block names it
    (§24bv point 5). The one marker every increment seam reads, never whether a manifest is
    present: a repository-backed increment carries none."""

    #: A sample application's: the vault's accepted tree and its interface manifest.
    MANIFEST = "manifest"
    #: A repository-backed Project's: the campaign branch's head (§24bv point 2), which has no
    #: interface manifest. Contract 1 names its pin the same way (``pinned_from``).
    CAMPAIGN_BRANCH = "campaign_branch"

    @property
    def has_manifest(self) -> bool:
        """Whether the change is a typed delta to an interface manifest, whose footprint the
        stack's scaffold map derives. On the campaign branch it is authored instead."""
        return self is IncrementBasis.MANIFEST


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
    #: §24bv point 5, on a repository-backed Project only: the product paths it exercises, which
    #: choose the runner its test is placed under. Empty, the footprint's are. Left out of the
    #: document and its hash when empty, so every request stored before keeps its identity.
    paths: tuple[str, ...] = ()


@dataclass(frozen=True)
class PlacedCriterionFile:
    """A criterion's own test file on a repository-backed Project (§24bv point 5): placed by the
    framework under the runner that covers it, never authored."""

    criterion_id: str
    path: str


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
    #: SIP-0113 §10t ruling 4: the goals the proposal means to move, by the ids it was shown. Read
    #: after the build by the ledger; left out of the document and its hash when empty, so every
    #: request stored before §4.5 keeps its identity. Only the proposer and the supervisor see it.
    moves_goals: tuple[str, ...] = ()
    #: §24bv point 5: the accepted tree it changes. Stored only for a campaign branch.
    basis: IncrementBasis = IncrementBasis.MANIFEST
    #: Derived from the manifest delta on a sample application. On a campaign branch, authored as
    #: path globs, with the framework's placed criterion files appended.
    footprint: tuple[str, ...] = ()
    #: §24bv point 5: each criterion's test file on a campaign branch, placed by the framework.
    #: Empty on a sample application, whose stack places it (``scaffold.criterion_test_path``).
    criterion_files: tuple[PlacedCriterionFile, ...] = ()
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
    REUSED_CRITERION = "reused_criterion"
    NOTHING_TO_BUILD = "nothing_to_build"
    UNDEFINED_KEY = "undefined_key"
    SURFACE_OUTSIDE_FOOTPRINT = "surface_outside_footprint"
    UNKNOWN_GOAL = "unknown_goal"
    GOAL_TEXT_COPIED = "goal_text_copied"
    #: §24bv point 5: a repository-backed Project has no interface manifest to apply a delta to.
    MANIFEST_DELTA_ON_PRODUCT = "manifest_delta_on_product"
    #: §24bv point 5: no runner of the product's can host the criterion's own test file.
    UNPLACEABLE_CRITERION = "unplaceable_criterion"


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

#: Fields the framework derives; a document that authors them is refused, not corrected. On a
#: campaign branch the footprint is authored instead (§24bv point 5), and every other one stays.
_DERIVED_FIELDS = (
    "footprint",
    "content_hash",
    "proposal_id",
    "version",
    "baseline_tree",
    "basis",
    "criterion_files",
)


def _derived_fields(basis: IncrementBasis) -> tuple[str, ...]:
    """The fields a document on ``basis`` may not author."""
    if basis.has_manifest:
        return _DERIVED_FIELDS
    return tuple(f for f in _DERIVED_FIELDS if f != "footprint")


def parse_change_request(
    authored: dict,
    *,
    proposal_id: str,
    version: int,
    baseline_tree: str,
    basis: IncrementBasis = IncrementBasis.MANIFEST,
) -> ChangeRequest:
    """The typed change request an authored document describes. On a campaign branch (§24bv
    point 5) the document authors its ``footprint``, and a criterion may name its ``paths``.

    Raises:
        ChangeRequestError: If a required field is missing, a value is outside its vocabulary,
            or the document authors a field the framework derives.
    """
    if not isinstance(authored, dict):
        raise ChangeRequestError("a change request is a mapping")
    authored_derived = [f for f in _derived_fields(basis) if f in authored]
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
            criteria=tuple(_criterion(c, basis) for c in authored.get("criteria") or ()),
            must_not_break=tuple(str(i) for i in authored.get("must_not_break") or ()),
            retires=_retirements(authored.get("retires")),
            replaces_verifiers=_retirements(authored.get("replaces_verifiers")),
            moves_goals=_goal_ids(authored.get("moves_goals")),
            basis=basis,
            footprint=() if basis.has_manifest else _paths(authored.get("footprint"), "footprint"),
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


def _criterion(raw: Any, basis: IncrementBasis) -> Criterion:
    if basis.has_manifest and "paths" in raw:
        raise ChangeRequestError(
            f"criterion {raw.get('id')!r}: paths are named only on a repository-backed Project; "
            "on this application the stack places a criterion's test"
        )
    return Criterion(
        id=_text(raw, "id"),
        statement=_text(raw, "statement"),
        surface_kind=SurfaceKind(raw["surface_kind"]),
        surface=_text(raw, "surface"),
        observable=_text(raw, "observable"),
        paths=_paths(raw.get("paths"), f"criterion {raw.get('id')!r} paths"),
    )


def _paths(raw: Any, field_name: str) -> tuple[str, ...]:
    """Repository-relative path globs, as a footprint or a criterion's paths are authored: each
    inside the product, never absolute and never climbing out of it."""
    if raw is None:
        return ()
    if not isinstance(raw, list) or not all(isinstance(p, str) and p.strip() for p in raw):
        raise ChangeRequestError(f"{field_name} is a list of repository-relative path globs")
    for p in raw:
        if p.strip().startswith("/") or ".." in p.strip().split("/"):
            raise ChangeRequestError(f"{field_name}: {p!r} leaves the product's repository")
    return tuple(dict.fromkeys(p.strip() for p in raw))


def stored_change_request(request: ChangeRequest) -> str:
    """The document the proposal run stores (``change_request.yaml``), which
    ``load_stored_change_request`` reads back: every field, the derived ones included, as plain
    YAML data. ``moves_goals`` only when it names a goal (§10t ruling 4); ``basis``,
    ``criterion_files`` and a criterion's ``paths`` only on a campaign branch (§24bv point 5)."""
    return _dumped(_authored_fields(dataclasses.asdict(request)))


def role_view(document: str) -> str:
    """A stored change request as every role but its proposer is shown it: without the goals it
    means to move (SIP-0113 §10t ruling 4), so no framing or build role is told which held-out
    goal its work is aimed at. A document that names none is returned as it is. For showing only:
    its hash is the whole request's, so it is never loaded back."""
    data = yaml.safe_load(document)
    if not isinstance(data, dict) or "moves_goals" not in data:
        return document
    return _dumped({k: v for k, v in data.items() if k != "moves_goals"})


def _authored_fields(payload: dict) -> dict:
    """``payload`` without what a request before them never carried, when it is empty: absent, as
    in every request before §4.5 (``moves_goals``) and §24bv point 5 (``basis``,
    ``criterion_files``, a criterion's ``paths``). So every stored request keeps its document and
    its hash."""
    out = {
        k: v
        for k, v in payload.items()
        if not (k in ("moves_goals", "criterion_files") and not v)
        and not (k == "basis" and v == IncrementBasis.MANIFEST)
    }
    if "criteria" in out:
        out["criteria"] = [
            {k: v for k, v in c.items() if k != "paths" or v} for c in out["criteria"]
        ]
    return out


def _dumped(data: dict) -> str:
    return yaml.safe_dump(_plain(data), sort_keys=False, allow_unicode=True)


def _plain(value: Any) -> Any:
    """Enums to their values, tuples to lists: the document's YAML carries plain data."""
    if isinstance(value, dict):
        return {k: _plain(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_plain(v) for v in value]
    if hasattr(value, "value") and isinstance(value.value, str):
        return value.value
    return value


def load_stored_change_request(document: str) -> ChangeRequest:
    """A change request as the proposal run stored it (``change_request.yaml``): the authored
    content, parsed by the one parse, with the framework's derived fields restored. The stored
    hash must be the content's, so a document altered after it was ruled on is refused."""
    data = yaml.safe_load(document)
    if not isinstance(data, dict):
        raise ChangeRequestError("a stored change request is a mapping")
    try:
        basis = IncrementBasis(str(data.get("basis") or IncrementBasis.MANIFEST))
    except ValueError as e:
        raise ChangeRequestError(f"the stored change request's basis is unknown: {e}") from e
    try:
        placed = tuple(
            PlacedCriterionFile(str(f["criterion_id"]), str(f["path"]))
            for f in data.get("criterion_files") or ()
        )
        authored = {k: v for k, v in data.items() if k not in _derived_fields(basis)}
        if not basis.has_manifest:
            # The stored footprint is the authored globs with the placed files appended.
            stored = {f.path for f in placed}
            authored["footprint"] = [p for p in data.get("footprint") or () if p not in stored]
        request = parse_change_request(
            authored,
            proposal_id=str(data["proposal_id"]),
            version=int(data["version"]),
            baseline_tree=str(data["baseline_tree"]),
            basis=basis,
        )
    except (KeyError, TypeError) as e:
        raise ChangeRequestError(f"the stored change request has no {e}") from e
    stored_hash = str(data.get("content_hash") or "")
    if content_hash(request) != stored_hash:
        raise ChangeRequestError("the stored change request's content does not match its hash")
    return dataclasses.replace(
        request,
        footprint=tuple(data.get("footprint") or ()),
        criterion_files=placed,
        content_hash=stored_hash,
    )


def _text(raw: Any, key: str) -> str:
    value = raw[key]
    if not isinstance(value, str) or not value.strip():
        raise ChangeRequestError(f"{key} is required text")
    return value


def _goal_ids(raw: Any) -> tuple[str, ...]:
    if raw is None:
        return ()
    if not isinstance(raw, list):
        raise ChangeRequestError("moves_goals is a list of the goal ids the proposal was shown")
    ids = tuple(raw)
    if not all(isinstance(i, str) and i.strip() for i in ids):
        raise ChangeRequestError("each of moves_goals is a goal id, as the evidence shows it")
    return ids


def _retirements(raw: Any) -> tuple[Retirement, ...]:
    return tuple(
        Retirement(criterion_id=_text(r, "criterion_id"), reason=_text(r, "reason"))
        for r in raw or ()
    )


def content_hash(request: ChangeRequest) -> str:
    """The hash a ruling binds to (§9.2): the authored content, not the derived fields or the
    proposal's identity. On a campaign branch the footprint is authored (§24bv point 5), so it is
    hashed, without the placed criterion files appended to it: a footprint changed after the
    ruling is a request nobody ruled on."""
    payload = _authored_fields(dataclasses.asdict(request))
    for derived in ("content_hash", "proposal_id", "version", "baseline_tree"):
        payload.pop(derived)
    payload.pop("basis", None)
    payload.pop("criterion_files", None)
    if request.basis.has_manifest:
        payload.pop("footprint")
    else:
        placed = {f.path for f in request.criterion_files}
        payload["footprint"] = [p for p in payload["footprint"] if p not in placed]
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

    return derive_footprint_from(
        InterfaceManifest.from_yaml(baseline_manifest),
        InterfaceManifest.from_yaml(candidate_manifest),
    )


def derive_footprint_from(before: Any, after: Any) -> tuple[str, ...]:
    """``derive_footprint`` over parsed manifests: the one derivation, for a caller that
    already holds them."""

    old = {f["name"]: f["content"] for f in expand(before)}
    new = {f["name"]: f["content"] for f in expand(after)}
    namespace = qa_test_namespace(after)
    changed = {
        name
        for name in old.keys() | new.keys()
        if old.get(name) != new.get(name) and not name.startswith(namespace)
    }
    return tuple(sorted(changed)) + tuple(f"{prefix}**" for prefix in namespace)


def footprint_product_files(footprint: tuple[str, ...]) -> tuple[str, ...]:
    """The product files a footprint admits: every entry but the qa test namespace's ``<dir>**``
    patterns, which ``derive_footprint_from`` appends whatever the delta (#1961)."""
    return tuple(p for p in footprint if not p.endswith("**"))


def _path_match(path: str, pattern: str) -> bool:
    """``fnmatch`` with ``[`` literal (#2512). A footprint or a scope uses ``*`` and ``**`` only,
    and a Next.js dynamic route is a bracketed directory: read as a class, ``[run_id]`` matched
    ``r`` and never itself."""
    return fnmatch(path, pattern.replace("[", "[[]"))


def in_footprint(path: str, footprint: tuple[str, ...]) -> bool:
    return any(_path_match(path, pattern) for pattern in footprint)


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
    #: The ids of the goals the proposal was shown (SIP-0113 §4.5): what ``moves_goals`` may name.
    shown_goals: tuple[str, ...] = field(default_factory=tuple)
    #: Each shown goal's id and statement, which nothing every role reads may copy (§10t ruling 7).
    shown_goal_statements: tuple[tuple[str, str], ...] = field(default_factory=tuple)
    #: §24bv point 5: a repository-backed Project's proposal reads its derived profile in place of
    #: a manifest. ``None`` on a sample application.
    product: ProductContext | None = None


#: §24bv point 5: the proposal task's input on a repository-backed Project, composed at its run
#: (``execution.product_proposal``) and read by its handler, which builds the rails' context.
PRODUCT_PROPOSAL_INPUT = "product_proposal"


@dataclass(frozen=True)
class ProductContext:
    """What a repository-backed Project's rails read of its derived profile (§24bv point 5): the
    public surfaces a criterion may assert on, and each runner a criterion's test is placed under.
    """

    #: Each surface as ``(kind, value)``: ``http_base`` and ``ui_base`` with their URL, a
    #: ``command`` with its argv joined, a ``package`` with its name.
    surfaces: tuple[tuple[str, str], ...]
    placements: tuple[RunnerPlacement, ...]
    #: Contract 8's ``files.test``: the globs that class the product's own test files.
    test_files: tuple[str, ...] = ()

    def serves(self, kind: str) -> tuple[str, ...]:
        return tuple(value for k, value in self.surfaces if k == kind)

    def product_paths(self, paths: Iterable[str]) -> tuple[str, ...]:
        """``paths`` without the product's own test files: what a criterion exercises when it
        names no paths of its own is the footprint's product files, never the tests it edits."""
        return tuple(p for p in paths if not any(_path_match(p, g) for g in self.test_files))


def qa_namespace_paths(paths: Iterable[str], stack: str) -> tuple[str, ...]:
    """The paths in ``stack``'s qa test namespace, in their order: the footprint's ``<dir>**``
    patterns and any test file a plan names there. The framework places these (§7.2: derived,
    never authored), so the objective's scope never reads them (#2743, the owner's ruling of
    2026-10-28). An unknown stack has no namespace, and every path stays the scope's."""
    return tuple(p for p in paths if is_qa_test_path_for_stack(p, stack))


def outside_allowed_scope(
    paths: Iterable[str],
    allowed_scope: Sequence[str],
    *,
    stack: str,
    placed: Iterable[str] = (),
) -> list[str]:
    """The paths no entry of the objective's allowed scope covers, in their order, leaving out
    the framework's: ``stack``'s qa test namespace (``qa_namespace_paths``), and on a
    repository-backed Project the criterion test files the framework itself placed (``placed``,
    §24bv point 5). A product's own test files stay the scope's, as every other product file does.
    An entry is a glob (``backend/**``) or a path prefix (``backend``). One reading for the
    proposal's rails (§9.1) and the plan-review tier (§24bj), so the two cannot disagree on what
    is in scope."""
    paths = tuple(paths)
    framework = set(qa_namespace_paths(paths, stack)) | set(placed)
    return [
        p
        for p in paths
        if p not in framework
        and not any(
            _path_match(p, scope) or p.startswith(scope.rstrip("*")) for scope in allowed_scope
        )
    ]


def validate_proposal(authored: dict, context: ProposalContext) -> ProposalVerdict:
    """Every rail, every refusal. A malformed document or a delta that does not fit stops the
    rails that need a candidate manifest; the rest still run. A repository-backed Project's
    proposal runs its own rails (``_validate_product_proposal``)."""
    if context.product is not None:
        return _validate_product_proposal(authored, context, context.product)
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

    refusals = (
        _criteria_refusals(request, context)
        + _undefined_key_refusals(request)
        + _goal_refusals(request, context)
        + _goal_copy_refusals(request, context)
    )
    try:
        candidate = apply_manifest_delta(context.baseline_manifest, request.manifest_delta)
    except DeltaDoesNotFit as e:
        return ProposalVerdict(
            None, (ProposalRefusal(RefusalKind.DELTA_DOES_NOT_FIT, str(e)), *refusals)
        )

    for finding in assess_winnability(candidate, context.expected_stack):
        refusals.append(
            ProposalRefusal(RefusalKind.MANIFEST_GATES, f"{finding.proof}: {finding.detail}")
        )
    if any(r.kind is RefusalKind.MANIFEST_GATES for r in refusals):
        return ProposalVerdict(None, tuple(refusals), candidate)

    footprint = derive_footprint(context.baseline_manifest, candidate)
    outside = outside_allowed_scope(footprint, context.allowed_scope, stack=context.expected_stack)
    if outside:
        namespace = qa_test_namespace_for_stack(context.expected_stack)
        refusals.append(
            ProposalRefusal(
                RefusalKind.OUT_OF_SCOPE,
                f"the delta reaches {', '.join(outside)}, outside the objective's allowed scope "
                f"({', '.join(context.allowed_scope)}); a proposal is refused, never trimmed"
                + (
                    f". The qa test namespace ({', '.join(namespace)}) is the framework's, "
                    "and the scope does not read it"
                    if namespace
                    else ""
                ),
            )
        )
    if request.kind is not ChangeKind.REFACTOR and not footprint_product_files(footprint):
        # #1961: an empty delta derives a footprint of tests only, so no build could satisfy the
        # criteria; the 2.0 set's prop_5fb2d8136c36 v1 passed every rail and reached the gate.
        refusals.append(
            ProposalRefusal(
                RefusalKind.NOTHING_TO_BUILD,
                f"this {request.kind} declares nothing for a build to implement: its manifest "
                "delta changes no product file, so the build could touch only tests. Everything "
                "the accepted manifest declares is already built; a behaviour change needs the "
                "manifest delta that declares it",
            )
        )
    refusals.extend(_surface_refusals(request, candidate))
    if footprint_product_files(footprint):
        # With nothing to build, ``nothing_to_build`` above already names the cause.
        refusals.extend(
            _unbuildable_surface_refusals(request, context.baseline_manifest, candidate, footprint)
        )
    if refusals:
        return ProposalVerdict(None, tuple(refusals), candidate)
    final = dataclasses.replace(request, footprint=footprint)
    return ProposalVerdict(
        dataclasses.replace(final, content_hash=content_hash(final)), (), candidate
    )


def _validate_product_proposal(
    authored: dict, context: ProposalContext, product: ProductContext
) -> ProposalVerdict:
    """§24bv point 5's rails, on a repository-backed Project. Its change request is read against
    the product, not a manifest:
    - ``manifest_delta`` is refused: there is no interface manifest to apply it to;
    - ``footprint`` is authored, as path globs, and must lie inside the objective's scope. A
      product's own test files are product files, and stay the scope's (the supervisor's ruling
      under the owner's delegation, 2026-10-28; §24cj);
    - each criterion's surface is one the derived profile names, its paths lie inside the
      footprint, and its own test file is placed by the framework under the runner that covers
      them (``criterion_placement``). Those placed files are the framework's, so the scope never
      reads them, and they are appended to the footprint the build may write.
    The criteria, goal and retirement rails are the sample application's, unchanged."""
    try:
        request = parse_change_request(
            authored,
            proposal_id=context.proposal_id,
            version=context.version,
            baseline_tree=context.baseline_tree,
            basis=IncrementBasis.CAMPAIGN_BRANCH,
        )
    except ChangeRequestError as e:
        kind = (
            RefusalKind.AUTHORED_DERIVED_FIELD
            if "the framework derives" in str(e)
            else RefusalKind.MALFORMED
        )
        return ProposalVerdict(None, (ProposalRefusal(kind, str(e)),))
    refusals = (
        _criteria_refusals(request, context)
        + _goal_refusals(request, context)
        + _goal_copy_refusals(request, context)
    )
    if request.manifest_delta:
        refusals.append(
            ProposalRefusal(
                RefusalKind.MANIFEST_DELTA_ON_PRODUCT,
                "this product has no interface manifest, so a manifest_delta has nothing to apply "
                "to. Leave it out, and name the files your change touches in footprint",
            )
        )
    footprint = request.footprint
    if request.kind is not ChangeKind.REFACTOR and not footprint:
        refusals.append(
            ProposalRefusal(
                RefusalKind.NOTHING_TO_BUILD,
                f"this {request.kind} names no file for a build to change: footprint lists the "
                "product's files (path globs) the change touches",
            )
        )
    outside = outside_allowed_scope(footprint, context.allowed_scope, stack="")
    if outside:
        refusals.append(
            ProposalRefusal(
                RefusalKind.OUT_OF_SCOPE,
                f"the footprint reaches {', '.join(outside)}, outside the objective's allowed "
                f"scope ({', '.join(context.allowed_scope)}); a proposal is refused, never "
                "trimmed. Each criterion's own test file is the framework's and is not read "
                "against the scope; every other file, the product's own tests included, is",
            )
        )
    refusals.extend(_product_surface_refusals(request, product))
    placed: list[PlacedCriterionFile] = []
    for c in request.criteria:
        paths = c.paths or product.product_paths(footprint)
        stray = [p for p in c.paths if not in_footprint(p, footprint)]
        if stray:
            refusals.append(
                ProposalRefusal(
                    RefusalKind.SURFACE_OUTSIDE_FOOTPRINT,
                    f"criterion {c.id} exercises {', '.join(stray)}, which the footprint leaves "
                    "out, so the build may not touch it and the criterion cannot be met",
                )
            )
            continue
        try:
            placed.append(
                PlacedCriterionFile(c.id, place_criterion(c.id, paths, product.placements))
            )
        except Unplaceable as e:
            refusals.append(ProposalRefusal(RefusalKind.UNPLACEABLE_CRITERION, str(e)))
    if refusals:
        return ProposalVerdict(None, tuple(refusals))
    final = dataclasses.replace(
        request,
        footprint=(*footprint, *(f.path for f in placed if f.path not in footprint)),
        criterion_files=tuple(placed),
    )
    return ProposalVerdict(dataclasses.replace(final, content_hash=content_hash(final)), ())


def _product_surface_refusals(
    request: ChangeRequest, product: ProductContext
) -> list[ProposalRefusal]:
    """Each criterion's surface must be one the derived profile names (§24bv point 5): an endpoint
    or a page the start declaration serves, a declared command (or a subcommand of one), or a
    declared package (or a name inside it)."""
    refusals = []
    for c in request.criteria:
        reason = _unserved(c, product)
        if reason:
            refusals.append(
                ProposalRefusal(RefusalKind.UNKNOWN_SURFACE, f"criterion {c.id}: {reason}")
            )
    return refusals


def _unserved(c: Criterion, product: ProductContext) -> str | None:
    if c.surface_kind is SurfaceKind.ENDPOINT:
        if not product.serves("http_base"):
            return "the product declares no HTTP base its start serves, so no endpoint is reached"
        if parse_method_path(c.surface) is None:
            return f'{c.surface!r} is no endpoint: write it as "METHOD /path"'
        return None
    if c.surface_kind is SurfaceKind.CLIENT_ROUTE:
        if not product.serves("ui_base"):
            return "the product declares no UI base its start serves, so no page is reached"
        return None if c.surface.startswith("/") else f"{c.surface!r} is no route path"
    declared = product.serves(str(c.surface_kind))
    joiner = " " if c.surface_kind is SurfaceKind.COMMAND else "."
    if any(c.surface == d or c.surface.startswith(d + joiner) for d in declared):
        return None
    return f"no {c.surface_kind} {c.surface!r} among the product's declared surfaces" + (
        f" ({', '.join(declared)})" if declared else " (it declares none of that kind)"
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
    # §8.1: a criterion pins its own verifier bundle by id for the rest of the campaign, so a new
    # criterion under a frozen one's id would share its file and its bundle.
    reused = sorted({c.id for c in request.criteria} & prior)
    if reused:
        refusals.append(
            ProposalRefusal(
                RefusalKind.REUSED_CRITERION,
                f"{', '.join(reused)} already name criteria an earlier increment froze; a new "
                "criterion takes an id no earlier increment used (§8.1)",
            )
        )
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


def _goal_refusals(request: ChangeRequest, context: ProposalContext) -> list[ProposalRefusal]:
    """SIP-0113 §10t ruling 4: a goal the proposal means to move is one it was shown. Naming one
    that already passes is not refused; the ledger reads it as ``already passing`` (ruling 5)."""
    unknown = [g for g in dict.fromkeys(request.moves_goals) if g not in set(context.shown_goals)]
    if not unknown:
        return []
    return [
        ProposalRefusal(
            RefusalKind.UNKNOWN_GOAL,
            f"moves_goals names {', '.join(unknown)}, which is not the id of a goal this proposal "
            "was shown; name only goals its evidence lists",
        )
    ]


def _normalized(text: str) -> str:
    return " ".join(text.casefold().split()).strip(" .;:,")


def _goal_copy_refusals(request: ChangeRequest, context: ProposalContext) -> list[ProposalRefusal]:
    """SIP-0113 §10t ruling 7: a goal's statement copied into what every role reads (a PRD
    section, a criterion's statement or observable) would show the framing and build roles the
    held-out goal the proposal was shown. Each copy is refused by the goal's id and where it is,
    never by its text."""
    places = [(f"prd_delta {s.id}", s.text) for s in request.prd_delta] + [
        (f"criterion {c.id}", f"{c.statement} {c.observable}") for c in request.criteria
    ]
    refusals = []
    for goal_id, statement in context.shown_goal_statements:
        goal = _normalized(statement)
        copied = [where for where, text in places if goal and goal in _normalized(text)]
        if copied:
            refusals.append(
                ProposalRefusal(
                    RefusalKind.GOAL_TEXT_COPIED,
                    f"{', '.join(copied)} repeats goal {goal_id}'s statement word for word; every "
                    "role reads them, and the goal is the evaluator's. State what your change "
                    "does in your own words",
                )
            )
    return refusals


def _undefined_key_refusals(request: ChangeRequest) -> list[ProposalRefusal]:
    """#2205: a key the interface manifest does not define is refused by name. The parser drops
    it silently, so the footprint would be derived from a manifest without it, and a change that
    lived only there (2.2's `messages:` under an endpoint) would derive no file to build it in."""

    refusals = []
    for op in request.manifest_delta:
        unknown = undefined_manifest_keys(str(op.target), op.definition)
        if unknown:
            refusals.append(
                ProposalRefusal(
                    RefusalKind.UNDEFINED_KEY,
                    f"{op.op} {op.target} {op.key!r}: {', '.join(unknown)} "
                    f"{'is not a key' if len(unknown) == 1 else 'are not keys'} the interface "
                    "manifest defines, so the build would never see "
                    f"{'it' if len(unknown) == 1 else 'them'}. An {op.target} declares "
                    f"{', '.join(sorted(MANIFEST_ELEMENT_KEYS[str(op.target)]))}",
                )
            )
    return refusals


def _unbuildable_surface_refusals(
    request: ChangeRequest, baseline: str, candidate: str, footprint: tuple[str, ...]
) -> list[ProposalRefusal]:
    """#2205: an endpoint criterion whose serving file the delta leaves alone cannot be met. The
    build may write only inside the footprint (``write_authorization``, and the plan gate), so
    the criterion would fail whatever the build did. The serving file comes from the contract's
    own ``endpoint_owners``, the relation every repair aims by.

    Client-route criteria are not checked: a view's behaviour can be served by the endpoints it
    calls, so a view outside the footprint does not show the criterion unbuildable.

    Nor is an endpoint that declares an error code whose contract the delta changes (gap 3): the
    frozen error module renders that code's status and declared message, and the scaffold
    regenerates it from the candidate manifest, so the change is built outside the serving
    file."""

    before, after = InterfaceManifest.from_yaml(baseline), InterfaceManifest.from_yaml(candidate)
    owners = VerificationContract.from_dict(emit_contract_dict(after)).endpoint_owners()
    rewritten = _error_codes_changed(before, after)
    errors_of = {f"{ep.method} {ep.path}": set(ep.errors) for ep in after.api.endpoints}
    buildable = set(footprint_product_files(footprint))
    refusals = []
    for c in request.criteria:
        if c.surface_kind is not SurfaceKind.ENDPOINT:
            continue
        parsed = parse_method_path(c.surface)
        surface = f"{parsed[0]} {parsed[1]}" if parsed else ""
        if errors_of.get(surface, set()) & rewritten:
            continue
        owner = owners.get(surface)
        if owner and owner not in buildable:
            refusals.append(
                ProposalRefusal(
                    RefusalKind.SURFACE_OUTSIDE_FOOTPRINT,
                    f"criterion {c.id}: {c.surface} is served by {owner}, which this delta "
                    "leaves unchanged, so the build may not touch it and the criterion cannot be "
                    "met. Declare the change in the manifest element that file is built from, or "
                    "propose the criterion with the change that does",
                )
            )
    return refusals


def _error_codes_changed(before: Any, after: Any) -> set[str]:
    """The error codes whose contract entry (status or declared message) differs between the two
    manifests, an added or removed code included."""

    def entries(manifest: Any) -> dict[str, tuple[int, str | None]]:
        contract = manifest.api.error_contract
        return {c.code: (c.http, c.message) for c in (contract.codes if contract else ())}

    old, new = entries(before), entries(after)
    return {code for code in old.keys() | new.keys() if old.get(code) != new.get(code)}


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
