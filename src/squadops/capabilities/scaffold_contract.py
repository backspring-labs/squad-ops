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
        }
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


def _probes(manifest: InterfaceManifest) -> list[dict[str, Any]]:
    """Self-contained probes only (POST endpoints with no path params). Sequenced
    probes (join/leave requiring a prior create) and richer response assertions land
    with the probe runner in 98.4; these are emitted now so the contract is complete."""
    shapes = {s.name: s for s in manifest.api.request_shapes}
    probes: list[dict[str, Any]] = []
    for ep in manifest.api.endpoints:
        if ep.method != "POST" or "{" in ep.path:
            continue
        shape = shapes.get(ep.request or "")
        json_body = {field: "x" for field in (shape.required if shape else ())}
        probes.append(
            {
                "id": f"vc-probe-{_slug(ep.path) or 'root'}",
                "subject": "backend",
                "request": {"method": ep.method, "path": ep.path, "json": json_body},
                # Emitted probes are parameterless POSTs — resource creates by
                # construction — and REST (and the PRD/QA suite) say a create
                # returns 201. Expecting 200 made the contract contradict the
                # PRD: a PRD-conformant app could never pass its own probe
                # (pf-3: "status 201 != expected 200" on a correct app).
                "expect": {"status": 201},
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
