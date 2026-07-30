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
from typing import Any

import yaml

from squadops.capabilities.scaffold import InterfaceManifest, expand, fill_slot_paths

CONTRACT_VERSION = 1
CAP_PYTHON = "python"
CAP_NODE = "node"

_ROUTES_PATH = "backend/routes.py"


def emit_contract_dict(manifest: InterfaceManifest) -> dict[str, Any]:
    """Derive the verification contract for ``manifest`` (SIP-0098 §6.1).

    Deterministic: the same manifest always yields the same contract (and therefore
    the same ``content_hash``), so the frozen hash the yield baseline measures against
    is reproducible.
    """
    files = {f["name"]: f["content"] for f in expand(manifest)}
    fill = fill_slot_paths(manifest)
    fill_set = set(fill)

    frozen = [
        {"path": name, "sha256": _sha256(files[name])}
        for name in sorted(files)
        if name not in fill_set
    ]

    fill_files: dict[str, Any] = {}
    for path in fill:
        fill_files[path] = (
            _routes_criteria(manifest) if path == _ROUTES_PATH else _view_criteria(path)
        )

    behavioral = _behavioral(manifest)

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


def _view_criteria(_path: str) -> dict[str, Any]:
    # Views (.jsx) carry NO per-file criteria in v1:
    #   - `node --check` cannot parse JSX (fails on correct code), so no per-view
    #     implementation criterion is winnable; and
    #   - the SIP-0092 `import_present` evaluator skips .js/.jsx ("frontend acceptance
    #     checks disabled" — out of scope for M1.2), so a view interface criterion could
    #     only ever *skip*, never verify anything.
    # View compilation is verified by the behavioral `frontend_build` (vite is the
    # JSX-aware compiler). Per-view frontend structural criteria arrive when the
    # frontend-acceptance-checks follow-up lands; the slot is recorded here regardless so
    # the fill/frozen partition stays complete.
    return {"interface": [], "implementation": []}


def _behavioral(manifest: InterfaceManifest) -> dict[str, Any]:
    return {
        "build": [
            {"check": "frontend_build", "id": "vc-frontend-builds", "requires": CAP_NODE},
        ],
        "suite": {
            "checks": [
                {"check": "tests_pass", "id": "vc-suite-passes", "requires": CAP_PYTHON},
            ],
            "coverage_expectations": _coverage_expectations(manifest),
        },
        "probes": _probes(manifest),
    }


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


def _probes(manifest: InterfaceManifest) -> list[dict[str, Any]]:
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
        # tested the behavior. The scaffold model now owns the constraint
        # (NonBlankStr on required request fields), so this probe is a
        # scaffold-owned regression guard: pydantic rejects the blank body
        # before any stub or fill body runs, hence guards="scaffold" (passes
        # on the bare skeleton by design — the frontend_build class, not the
        # tests_pass class). Emitted only alongside an error contract, whose
        # frozen handler shapes the 422 validation_error envelope.
        if shape and shape.required and manifest.api.error_contract:
            probes.append(
                {
                    "id": f"vc-probe-{_slug(ep.path) or 'root'}-rejects-blank",
                    "subject": "backend",
                    "request": {
                        "method": ep.method,
                        "path": ep.path,
                        "json": dict.fromkeys(shape.required, ""),
                    },
                    "expect": {"status": 422, "error_code": "validation_error"},
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
    # Stable order: python before node.
    return [c for c in (CAP_PYTHON, CAP_NODE) if c in found]
