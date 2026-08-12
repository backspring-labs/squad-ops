"""Verification-contract emission (SIP-0098 phase 98.2).

Authors the ``verification_contract.yaml`` the expander emits **alongside** the
skeleton and interface manifest (SIP-0098 §6.1). This is the "author once" half of
*author once, validate twice*: the criteria are derived deterministically from the
same interface manifest the skeleton is expanded from, so verification is a fixed
property of the scaffold rather than a per-roll LLM lottery.

Placement: this lives on the **expander surface** (capabilities), not the cycles
domain — emission is the scaffold's job; the cycles-domain
``verification_contract`` module *consumes* (loads/lints) what this produces. So this
module imports only ``scaffold`` and emits a plain dict/YAML artifact; a test proves
the artifact lints clean against the cycles-domain schema (the 98.1 ↔ 98.2 interlock).

Fill vs frozen: every file ``expand`` emits that is not a fill slot
(``scaffold.fill_slot_paths``) is frozen and pinned by content hash; criteria hang
only on the slots. The behavioral section (build/suite/probes) is the last word on
the deliverable. Probes are emitted here but not *executed* until phase 98.4 lands the
probe runner (§6.1/§6.4).
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import yaml

from squadops.capabilities.scaffold import (
    InterfaceManifest,
    criteria_pack_for,
    expand,
    fill_slot_paths,
)

CONTRACT_VERSION = 1
CAP_PYTHON = "python"
CAP_NODE = "node"

_ROUTES_PATH = "backend/routes.py"


@dataclass(frozen=True)
class CriteriaPack:
    """What proves a filled slot of each kind correct, for one stack (#818).

    Before this, the emitter was FastAPI end to end with no registration point:
    ``_ROUTES_PATH`` was hardcoded and the slot partition was a single inline
    conditional. A second stack's fill slots are ``.ts``, so nothing matched, and **every
    slot — including the API routes file — fell through to the view branch**.
    ``endpoint_defined`` was never emitted, so the guards that refuse to credit a check
    which cannot run (``manifest_gates`` ``PROOF_CHECKS_LIVE``, and the dispatch-time strip
    in ``task_plan``) had nothing to catch: the contract was not *incomplete*, it was
    *wrong*, and every gate accepted it.

    ``slot_criteria`` therefore owns **the partition as well as the criteria** — "what
    kinds of fill slot does this stack have, and how do I tell them apart" is the
    stack-specific claim that inline conditional was making silently.

    Deliberately NOT covering the manifest-derived tiers. Probes, coverage expectations,
    the frozen-file hashing, and ``skeleton.expander`` are language-agnostic already, which
    is why this seam is small — and is S2's HTTP-constant containment argument paying off
    exactly where it was meant to. (#874 carved out one probe fact: the blank-rejection
    status is framework-dependent, so it lives here — see ``blank_rejection_status``.)
    """

    name: str
    #: ``(manifest, fill_slot_path) -> {"interface": [...], "implementation": [...]}``.
    slot_criteria: Callable[[InterfaceManifest, str], dict[str, Any]]
    #: ``behavioral.build`` — what proves the deliverable builds.
    build_criteria: Callable[[], list[dict[str, Any]]]
    #: ``behavioral.suite.checks`` — what proves its test suite ran.
    suite_criteria: Callable[[], list[dict[str, Any]]]
    #: #874: what the rejects-blank probe expects. An ``int`` is a framework-FIXED status
    #: (stack #1: pydantic rejects blank required fields with its native 422 *before* any
    #: app code runs, so the manifest's declared mapping is unenforceable for this probe).
    #: ``None`` means the stack's frozen error seam owns validation status, so the
    #: expectation derives from ``error_contract.codes[validation_error].http`` — roll 13
    #: (cyc_732b773cf323) authored that mapping as 400, the hardcoded 422 contradicted the
    #: seam in the same derived YAML, and the probe was unwinnable by construction. When
    #: deriving and the mapping is absent, the probe is omitted: an expectation the seam
    #: cannot deliver is the same defect with extra steps.
    blank_rejection_status: int | None = None


def emit_contract_dict(manifest: InterfaceManifest) -> dict[str, Any]:
    """Derive the verification contract for ``manifest`` (SIP-0098 §6.1).

    Deterministic: the same manifest always yields the same contract (and therefore
    the same ``content_hash``), so the frozen hash the yield baseline measures against
    is reproducible.
    """
    pack = _pack_for(manifest.stack)
    files = {f["name"]: f["content"] for f in expand(manifest)}
    fill = fill_slot_paths(manifest)
    fill_set = set(fill)

    frozen = [
        {"path": name, "sha256": _sha256(files[name])}
        for name in sorted(files)
        if name not in fill_set
    ]

    fill_files: dict[str, Any] = {path: pack.slot_criteria(manifest, path) for path in fill}

    behavioral = _behavioral(manifest, pack)

    contract = {
        "contract_version": CONTRACT_VERSION,
        "skeleton": {
            "expander": manifest.stack,
            "interface_manifest_hash": manifest.content_hash(),
        },
        # Declared from what the criteria actually require, so the two can't drift.
        "capabilities": _required_capabilities(fill_files, behavioral),
        "frozen": frozen,
        "fill_files": fill_files,
        "behavioral": behavioral,
    }
    return contract


def emit_contract_yaml(manifest: InterfaceManifest) -> str:
    """The emitted ``verification_contract.yaml`` artifact text."""
    header = (
        "# Verification contract — emitted by the scaffold expander (SIP-0098).\n"
        "# Roll-invariant: framing BINDS these criteria by id; it never authors them.\n"
        "# Regenerate with the expander; do not hand-edit.\n"
    )
    body = yaml.safe_dump(emit_contract_dict(manifest), sort_keys=False, default_flow_style=False)
    return header + body


# --------------------------------------------------------------------------- helpers


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _slug(name: str) -> str:
    """CamelCase / path-ish name -> kebab id fragment (stable, unique per manifest)."""
    kebab = re.sub(r"(?<!^)(?=[A-Z])", "-", name)
    return re.sub(r"[^a-z0-9]+", "-", kebab.lower()).strip("-")


def _routes_criteria(manifest: InterfaceManifest) -> dict[str, Any]:
    interface: list[dict[str, Any]] = [
        {
            "check": "endpoint_defined",
            "id": "vc-routes-endpoints",
            "methods_paths": [f"{ep.method} {ep.path}" for ep in manifest.api.endpoints],
        }
    ]
    # The ApiError seam exists only when the manifest declares an error contract.
    if manifest.api.error_contract:
        interface.append(
            {
                "check": "import_present",
                "id": "vc-routes-apierror",
                "module": ".errors",
                "symbol": "ApiError",
            }
        )
    implementation = [
        {
            "check": "command_exit_zero",
            "id": "vc-routes-compiles",
            "argv": ["python", "-m", "py_compile", _ROUTES_PATH],
            "requires": CAP_PYTHON,
        },
        # #628: py_compile validates syntax only — pf-54's routes.py passed it
        # (and both AST checks) while NameError-ing at import because the
        # scaffold's `router = APIRouter()` line was dropped. module_imports is
        # the runtime-level complement: the module must actually import.
        {
            "check": "module_imports",
            "id": "vc-routes-imports",
            "file": _ROUTES_PATH,
            "requires": CAP_PYTHON,
        },
    ]
    return {"interface": interface, "implementation": implementation}


def _view_criteria(path: str) -> dict[str, Any]:
    # Views carry ONE implementation criterion (#648): the real frontend build,
    # run at task time. The v1 rationale for empty criteria stands for the
    # static vocabulary — `node --check` cannot parse JSX and the AST checks
    # skip .jsx — but fay-4 and fay-8 each shipped a view with a rollup
    # bind-time error that no static check can see, invisible until final
    # verification where no correction budget can reach it. `frontend_compiles`
    # is the bundler itself (the only tool that sees the class), anchored to
    # the view so #641 binds it onto the view's own task and a failure repairs
    # where the defect lives.
    stem = path.rsplit("/", 1)[-1].rsplit(".", 1)[0]
    return {
        "interface": [],
        "implementation": [
            {
                "check": "frontend_compiles",
                "id": f"vc-view-compiles-{_slug(stem)}",
                "file": path,
                "requires": CAP_NODE,
            }
        ],
    }


def _behavioral(manifest: InterfaceManifest, pack: CriteriaPack) -> dict[str, Any]:
    """Build and suite come from the pack; coverage and probes are manifest-derived."""
    return {
        "build": pack.build_criteria(),
        "suite": {
            "checks": pack.suite_criteria(),
            "coverage_expectations": _coverage_expectations(manifest),
        },
        "probes": _probes(manifest, pack),
    }


def _fastapi_react_slot_criteria(manifest: InterfaceManifest, path: str) -> dict[str, Any]:
    """This stack has two kinds of fill slot: one designated routes file, and views.

    The partition was previously an inline conditional in ``emit_contract_dict``, which
    made it look like a property of contracts rather than a claim about *this* stack.
    """
    return _routes_criteria(manifest) if path == _ROUTES_PATH else _view_criteria(path)


def _nextjs_ts_slot_criteria(manifest: InterfaceManifest, path: str) -> dict[str, Any]:
    """Stack #2 has two kinds of fill slot — API route handlers and pages (#822).

    **Both get the same criterion, and that is the disclosure, not an oversight.** The nine
    AST checks parse Python by construction, and ``tsc --noEmit`` is safelisted but not
    provisionable (``tsc`` lives in ``node_modules/.bin``, never on PATH — #707's
    "passes the allowlist but cannot run" class). ``next build`` runs tsc itself, so
    ``frontend_compiles`` *is* the type check here, for server and client files alike.

    Anchored per slot rather than once for the tree even though the build is whole-tree:
    #641/#648 attach it to the file under evaluation so a failure repairs where the defect
    lives. Bend 5 records the cost — stack #1 pays 3 builds, stack #2 pays 7.

    Consequence stated plainly: **no criterion here proves the declared endpoints exist in
    the source.** ``endpoint_defined`` is Python-only, so that claim is carried by the
    behavioral probes alone — late and functionally, rather than early and structurally.

    **The criterion id is derived from the whole slot path, not the basename (#849).** It was
    the basename, copied from ``_view_criteria``, and on this stack that produced *colliding
    ids*: App Router fixes the filename and puts identity in the directory, so all four route
    files slugged to ``route`` and all three pages to ``page`` — nine criteria, four distinct
    ids. ``VerificationContract.criterion_index()`` is keyed on id and documents itself as
    last-writer-wins, so five of seven fill slots resolved to no criterion while a plan that
    bound all seven refs read as fully covered and every gate passed. Measured on
    ``cyc_7899ed1feae5``. Not a coverage gap — #818's "incorrect contract that is believed",
    one layer down, and the same FastAPI-shaped assumption as ``_ROUTES_PATH``: that a
    filename identifies a file.

    ``_view_criteria`` still slugs the basename and is deliberately left alone. Stack #1's
    views are emitted into one flat directory, so its basenames are unique *by construction of
    its own expander* rather than by luck — and changing it would move the contract hash
    ``7622f570c949fe95`` that #777's guard and every bind-mode cycle are pinned to. The
    general protection against a future stack repeating this is the id linter, now wired at
    derivation, not a second hand-audit of the emitters.
    """
    return {
        "interface": [],
        "implementation": [
            {
                "check": "frontend_compiles",
                "id": f"vc-compiles-{_slug(path.rsplit('.', 1)[0]) or 'root'}",
                "file": path,
                "project_dir": ".",
                "requires": CAP_NODE,
            }
        ],
    }


_CRITERIA_PACKS: dict[str, CriteriaPack] = {
    "nextjs_ts": CriteriaPack(
        name="nextjs_ts",
        slot_criteria=_nextjs_ts_slot_criteria,
        # `next build` at the project root, not `npm run build` in `frontend/` — the
        # assumption #828 parameterised, exercised here for the first time.
        build_criteria=lambda: [
            {"check": "frontend_build", "id": "vc-frontend-builds", "requires": CAP_NODE},
        ],
        # vitest, so the suite check requires node rather than python. Stack #1's pack
        # emitted CAP_PYTHON unconditionally, which would have demanded a Python toolchain
        # of a stack that has none.
        suite_criteria=lambda: [
            {"check": "tests_pass", "id": "vc-suite-passes", "requires": CAP_NODE},
        ],
        # #874: no framework preempts the frozen error seam — route handlers shape every
        # status — so the rejects-blank expectation derives from the authored mapping.
        blank_rejection_status=None,
    ),
    "fullstack_fastapi_react": CriteriaPack(
        name="fullstack_fastapi_react",
        slot_criteria=_fastapi_react_slot_criteria,
        build_criteria=lambda: [
            {"check": "frontend_build", "id": "vc-frontend-builds", "requires": CAP_NODE},
        ],
        suite_criteria=lambda: [
            {"check": "tests_pass", "id": "vc-suite-passes", "requires": CAP_PYTHON},
        ],
        # #874: pydantic 422s a blank required field before any stub or fill body runs;
        # the declared error-contract mapping cannot change what the framework emits.
        blank_rejection_status=422,
    ),
}


def _pack_for(stack: str) -> CriteriaPack:
    """The stack's criteria pack, or a refusal (#818).

    Refusal rather than a fallback, and this is the whole point of the issue: the previous
    behavior *was* the fallback — an unregistered stack's slots quietly took the FastAPI
    view branch and produced a contract that asserted the wrong things and was believed.
    Emission is deterministic and offline, so raising here lands before a cycle spends
    anything, and it is the same refusal ``scaffold._stack`` already raises for a stack
    with no expander.
    """
    name = criteria_pack_for(stack)
    if not name:
        raise ValueError(
            f"stack {stack!r} declares no criteria_pack, so no verification contract can be "
            f"derived for it. Register one in scaffold_contract._CRITERIA_PACKS and name it "
            f"on the stack's ScaffoldStack — do not let it inherit another stack's criteria "
            f"(#818: that produced a contract asserting the wrong things, which every gate "
            f"accepted)."
        )
    pack = _CRITERIA_PACKS.get(name)
    if pack is None:
        raise ValueError(
            f"stack {stack!r} names criteria_pack {name!r}, which is not registered "
            f"(known: {sorted(_CRITERIA_PACKS)})."
        )
    return pack


def _coverage_expectations(manifest: InterfaceManifest) -> list[str]:
    out: list[str] = []
    eps = ", ".join(f"{ep.method} {ep.path}" for ep in manifest.api.endpoints)
    if eps:
        out.append(f"happy path for each endpoint: {eps}")
    if manifest.api.error_contract:
        out.extend(f"{code.code} -> HTTP {code.http}" for code in manifest.api.error_contract.codes)
    out.append("tests are order-independent; module-level state reset per test")
    return out


def _probe_sample_value(field_name: str, field_type: str) -> Any:
    """A plausible sample value for a probe request field (#524).

    ``"x"`` for every field failed apps that validate their inputs: a field named
    ``datetime`` typed ``string`` still gets parsed as a datetime by a reasonable
    app, which then 422s the bogus ``"x"`` — penalizing a *correct* app for
    validating (pf-12: the app passed its own suite yet failed the probe on
    "status 422 != expected 201"). Semantic name hints win over the declared type
    (a string-typed ``datetime`` still wants an ISO value); type is the fallback.
    """
    n = field_name.lower()
    t = (field_type or "").lower()
    if "datetime" in n or "timestamp" in n or n.endswith("_at") or n in ("date", "time"):
        return "2026-08-01T08:00:00"
    if "email" in n:
        return "sample@example.com"
    if "url" in n or "uri" in n:
        return "https://example.com"
    if t in ("int", "integer"):
        return 1
    if t in ("float", "number", "decimal"):
        return 1.0
    if t in ("bool", "boolean"):
        return True
    if t.startswith("list") or t.startswith("array"):
        return []
    return "sample"


def _probes(manifest: InterfaceManifest, pack: CriteriaPack) -> list[dict[str, Any]]:
    """POST-create probes plus their sequenced child-action probes (#651, v8).

    fay-3 shipped a broken join as "functional": v7 probed create + blank
    rejection only, so the functional bar never touched the app's core
    interactions. Child POST actions (``/runs/{run_id}/join``) are now probed
    in sequence — the create probe captures the created resource's ``id`` into
    the child path's parameter, a declared-conflict action (an error code the
    manifest maps to HTTP 409) gets an immediate duplicate probe expecting the
    envelope, and every expectation is read from the manifest (success status,
    error contract), never guessed. Winnability is the reference fill's proof,
    as ever; on the bare skeleton the create fails, nothing is captured, and
    each dependent probe fails on its unresolved placeholder — fill-behavior
    gate semantics by construction."""
    shapes = {s.name: s for s in manifest.api.request_shapes}
    # #524: resolve each required field's declared type (from entity fields) so the
    # probe body carries type/name-appropriate sample values, not a blanket "x".
    field_types = {f.name: f.type for e in manifest.entities for f in e.fields}
    ec = manifest.api.error_contract
    error_http = {c.code: c.http for c in (ec.codes if ec else ())}
    entity_field_names = {e.name: {f.name for f in e.fields} for e in manifest.entities}
    probes: list[dict[str, Any]] = []
    for ep in manifest.api.endpoints:
        if ep.method != "POST" or "{" in ep.path:
            continue
        shape = shapes.get(ep.request or "")
        json_body = {
            field: _probe_sample_value(field, field_types.get(field, "string"))
            for field in (shape.required if shape else ())
        }
        create_probe = {
            "id": f"vc-probe-{_slug(ep.path) or 'root'}",
            "subject": "backend",
            "request": {"method": ep.method, "path": ep.path, "json": json_body},
            # Emitted probes are parameterless POSTs — resource creates by
            # construction — and REST (and the PRD/QA suite) say a create
            # returns 201. Expecting 200 made the contract contradict the
            # PRD: a PRD-conformant app could never pass its own probe
            # (pf-3: "status 201 != expected 200" on a correct app).
            #
            # pf-39: read the endpoint's declared success status so the probe and
            # the emitted decorator cannot disagree. Previously this was hardcoded
            # 201 while ``_routes_source`` emitted no ``status_code`` at all, so
            # the skeleton contradicted its own contract and only a dev agent
            # volunteering ``status_code=201`` could close the gap. A manifest that
            # declares no success status keeps the historical 201 expectation.
            "expect": {"status": ep.success_status or 201},
        }
        probes.append(create_probe)
        # #593: the blank-input rejection probe. pf-38 volunteered blank-field
        # guards and pf-39 didn't — both green, because nothing required OR
        # tested the behavior. The scaffold owns the constraint (stack #1:
        # NonBlankStr on required request fields; stack #2: the frozen route
        # stub's required-field guard), so this probe is a scaffold-owned
        # regression guard, hence guards="scaffold" (passes on the bare
        # skeleton by design — the frontend_build class, not the tests_pass
        # class). Emitted only alongside an error contract.
        #
        # #874: the expected status is the pack's call, pf-39's lesson applied
        # to the rejection side (that comment above records the SUCCESS status
        # being un-hardcoded; this one stayed hardcoded 422 and roll 13's
        # authored `validation_error: 400` derived a contract that contradicted
        # its own frozen seam — unwinnable by construction, masked before by
        # every author happening to declare 422). A framework-fixed status
        # (pydantic's 422) stays fixed; a seam-owned stack derives from the
        # authored mapping, and an unmapped code omits the probe.
        if shape and shape.required and manifest.api.error_contract:
            expected_rejection = (
                pack.blank_rejection_status
                if pack.blank_rejection_status is not None
                else error_http.get("validation_error")
            )
            if expected_rejection is not None:
                probes.append(
                    {
                        "id": f"vc-probe-{_slug(ep.path) or 'root'}-rejects-blank",
                        "subject": "backend",
                        "request": {
                            "method": ep.method,
                            "path": ep.path,
                            "json": dict.fromkeys(shape.required, ""),
                        },
                        "expect": {
                            "status": expected_rejection,
                            "error_code": "validation_error",
                        },
                        "guards": "scaffold",
                    }
                )

        # #651 (v8): sequenced child-action probes. A child is a POST under
        # this create's path with exactly one path parameter
        # (``/runs/{run_id}/join``). The chain is manifest-derived end to end:
        # the create's response entity must declare an ``id`` field (that is
        # what gets captured into the parameter), the child's success status
        # is its declared one (FastAPI-default 200 otherwise), and a declared
        # error code the error contract maps to HTTP 409 yields an immediate
        # duplicate probe pinning the envelope. Children emit in manifest
        # declaration order — the winnability gate (reference fill) is the
        # proof the resulting sequence is satisfiable.
        response_fields = entity_field_names.get(ep.response or "", set())
        children = [
            child
            for child in manifest.api.endpoints
            if child.method == "POST"
            and re.fullmatch(re.escape(ep.path) + r"/\{(\w+)\}/\w+", child.path)
        ]
        if children and "id" in response_fields:
            param = re.findall(r"\{(\w+)\}", children[0].path)[0]
            create_probe["capture"] = {param: "id"}
            create_slug = _slug(ep.path) or "root"
            for child in children:
                child_shape = shapes.get(child.request or "")
                child_body = {
                    field: _probe_sample_value(field, field_types.get(field, "string"))
                    for field in (child_shape.required if child_shape else ())
                }
                action = child.path.rsplit("/", 1)[-1]
                probes.append(
                    {
                        "id": f"vc-probe-{create_slug}-{_slug(action)}",
                        "subject": "backend",
                        "request": {"method": "POST", "path": child.path, "json": child_body},
                        "expect": {"status": child.success_status or 200},
                    }
                )
                conflict_codes = [c for c in child.errors if error_http.get(c) == 409]
                if conflict_codes:
                    probes.append(
                        {
                            "id": f"vc-probe-{create_slug}-{_slug(action)}-duplicate",
                            "subject": "backend",
                            "request": {
                                "method": "POST",
                                "path": child.path,
                                "json": child_body,
                            },
                            "expect": {"status": 409, "error_code": conflict_codes[0]},
                        }
                    )
    return probes


def _required_capabilities(fill_files: dict[str, Any], behavioral: dict[str, Any]) -> list[str]:
    found: set[str] = set()
    for spec in fill_files.values():
        for cls in ("interface", "implementation"):
            for crit in spec.get(cls, []):
                if crit.get("requires"):
                    found.add(crit["requires"])
    for crit in behavioral.get("build", []):
        if crit.get("requires"):
            found.add(crit["requires"])
    for crit in behavioral.get("suite", {}).get("checks", []):
        if crit.get("requires"):
            found.add(crit["requires"])
    # Stable order: the known capabilities first, in their historical order, then anything
    # else sorted. #818: this used to be `[c for c in (CAP_PYTHON, CAP_NODE) if c in found]`,
    # a closed two-element universe that silently DROPPED a third — so a pack declaring
    # `requires: "go"` would under-declare its capabilities, in a field whose whole claim is
    # that it is "declared from what the criteria actually require, so the two can't drift".
    known = [c for c in (CAP_PYTHON, CAP_NODE) if c in found]
    return known + sorted(found - set(known))
