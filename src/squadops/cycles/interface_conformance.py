"""Deterministic interface-drift diagnosis for the correction loop (piece 1).

When an app renames an interface *identifier* — a model field or a route path —
the failure the correction loop sees is opaque ("status 404 != expected 201").
The LLM analyzer then guesses from post-extraction artifacts and mislabels it, and
the repair thrashes.

This module makes the *diagnosis* exact and leaves the *reconciliation* to the
agent — the right division of labor. It parses the app's generated model/route
files, diffs the identifiers against the interface manifest, and when the app
declares identifiers the interface does not define, emits a ``DriftFinding``
carrying the offending set, the interface identifiers currently absent, and a
precise instruction. The agent renames by meaning (which an LLM does well and a
1:1 set-diff cannot do safely when several identifiers drift at once — the real
case: pf-13 drifted both ``location`` and ``pace_target`` simultaneously).

Conservative on both ends: a clean file, class-name drift, or an unparseable file
yields NO finding and falls through to the existing loop. Pure (manifest +
{path: content} → findings); AST-based; never raises.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass
from typing import Any

_ROUTE_METHODS = {"get", "post", "put", "patch", "delete"}
# Pydantic/class internals that are not interface fields even if annotated.
_NON_FIELD_NAMES = {"model_config"}


@dataclass(frozen=True)
class DriftFinding:
    """Identifier drift for one file, with the sets the agent needs to reconcile.

    ``extra`` are identifiers the app declares that the interface does not define
    (the offenders). ``missing`` are interface identifiers absent from the app
    (the rename targets). ``instruction`` is the precise, self-contained repair
    directive handed to the agent.
    """

    kind: str  # "field_drift" | "route_drift"
    file: str
    extra: tuple[str, ...]
    missing: tuple[str, ...]
    instruction: str


def detect_interface_drift(
    manifest: Any, artifact_contents: dict[str, str] | None
) -> list[DriftFinding]:
    """Diagnose field/route identifier drift against the manifest.

    ``manifest`` is an ``InterfaceManifest`` (duck-typed: ``entities`` and
    ``api.endpoints``). ``artifact_contents`` maps workspace-relative path → file
    text. Returns a finding per drifted file; empty on clean input, missing
    manifest/content, or any parse error.
    """
    if manifest is None or not artifact_contents:
        return []
    try:
        return _detect_field_drift(manifest, artifact_contents) + _detect_route_drift(
            manifest, artifact_contents
        )
    except Exception:
        # A diagnosis helper must never break the correction loop — a parse or
        # attribute surprise degrades to "no finding", i.e. today's behavior.
        return []


# --------------------------------------------------------------------------- #
# Field drift: manifest entity fields vs. Pydantic model class fields
# --------------------------------------------------------------------------- #


def _detect_field_drift(manifest: Any, contents: dict[str, str]) -> list[DriftFinding]:
    entities = getattr(manifest, "entities", ()) or ()
    if not entities:
        return []
    model_classes: dict[str, tuple[str, set[str]]] = {}
    for path, text in contents.items():
        if not path.endswith(".py") or not isinstance(text, str):
            continue
        for cls_name, fields in _model_classes(text):
            model_classes.setdefault(cls_name, (path, fields))

    findings: list[DriftFinding] = []
    for entity in entities:
        entity_name = getattr(entity, "name", None)
        if entity_name is None or entity_name not in model_classes:
            continue  # class-name drift or absent model — out of scope, fall through
        expected = {f.name for f in getattr(entity, "fields", ()) or ()}
        file, actual = model_classes[entity_name]
        actual = {a for a in actual if a not in _NON_FIELD_NAMES and not a.startswith("_")}
        extra = actual - expected  # app declares fields the interface doesn't define
        if not extra:
            continue
        missing = expected - actual  # interface fields absent from the app
        findings.append(
            DriftFinding(
                kind="field_drift",
                file=file,
                extra=tuple(sorted(extra)),
                missing=tuple(sorted(missing)),
                instruction=_field_instruction(entity_name, file, extra, missing, expected),
            )
        )
    return findings


def _field_instruction(
    entity: str, file: str, extra: set[str], missing: set[str], expected: set[str]
) -> str:
    offenders = ", ".join(f"`{n}`" for n in sorted(extra))
    iface = ", ".join(f"`{n}`" for n in sorted(expected))
    base = (
        f"The `{entity}` model in `{file}` declares field(s) {offenders} that are not part "
        f"of the interface. The interface defines exactly these fields: {iface}. "
    )
    if missing:
        targets = ", ".join(f"`{n}`" for n in sorted(missing))
        base += (
            f"Rename each non-interface field to its correct interface name — the interface "
            f"fields currently absent from your model are {targets}. Match by meaning. "
        )
    else:
        base += "Remove or rename the non-interface field(s) so the model matches the interface. "
    return base + "Update every reference (routes, tests, frontend). Change nothing else."


def _model_classes(text: str) -> list[tuple[str, set[str]]]:
    """``(class_name, {annotated field names})`` for each class — the Pydantic surface."""
    tree = ast.parse(text)
    out: list[tuple[str, set[str]]] = []
    for node in tree.body:
        if not isinstance(node, ast.ClassDef):
            continue
        fields = {
            stmt.target.id
            for stmt in node.body
            if isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name)
        }
        out.append((node.name, fields))
    return out


# --------------------------------------------------------------------------- #
# Route drift: manifest endpoints vs. FastAPI route decorators
# --------------------------------------------------------------------------- #


def _detect_route_drift(manifest: Any, contents: dict[str, str]) -> list[DriftFinding]:
    api = getattr(manifest, "api", None)
    endpoints = getattr(api, "endpoints", ()) if api is not None else ()
    if not endpoints:
        return []
    expected = {(getattr(e, "method", "").upper(), getattr(e, "path", "")) for e in endpoints}

    actual: set[tuple[str, str]] = set()
    file_by_route: dict[tuple[str, str], str] = {}
    for path, text in contents.items():
        if not path.endswith(".py") or not isinstance(text, str):
            continue
        for method, route in _route_decorators(text):
            actual.add((method, route))
            file_by_route.setdefault((method, route), path)
    if not actual:
        return []
    extra = actual - expected  # app routes not in the interface
    if not extra:
        return []
    missing = expected - actual
    # All offending routes share a file in practice; name it from the first.
    file = file_by_route[sorted(extra)[0]]
    return [
        DriftFinding(
            kind="route_drift",
            file=file,
            extra=tuple(f"{m} {p}" for m, p in sorted(extra)),
            missing=tuple(f"{m} {p}" for m, p in sorted(missing)),
            instruction=_route_instruction(file, extra, missing, expected),
        )
    ]


def _route_instruction(
    file: str, extra: set[tuple[str, str]], missing: set[tuple[str, str]], expected: set
) -> str:
    offenders = ", ".join(f"`{m} {p}`" for m, p in sorted(extra))
    iface = ", ".join(f"`{m} {p}`" for m, p in sorted(expected))
    base = (
        f"`{file}` declares route(s) {offenders} that are not part of the interface. "
        f"The interface defines exactly these routes: {iface}. "
    )
    if missing:
        targets = ", ".join(f"`{m} {p}`" for m, p in sorted(missing))
        base += (
            f"Correct the path/method of each non-interface route to match the interface — "
            f"the interface routes currently absent are {targets}. Match by meaning. "
        )
    else:
        base += "Remove or correct the non-interface route(s) so they match the interface. "
    return base + "Update every reference (tests, frontend). Change nothing else."


def _route_decorators(text: str) -> list[tuple[str, str]]:
    """``(METHOD, path)`` for each ``@x.<method>("path", ...)`` route decorator."""
    tree = ast.parse(text)
    out: list[tuple[str, str]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            continue
        for dec in node.decorator_list:
            if not isinstance(dec, ast.Call) or not isinstance(dec.func, ast.Attribute):
                continue
            method = dec.func.attr.lower()
            if method not in _ROUTE_METHODS:
                continue
            if dec.args and isinstance(dec.args[0], ast.Constant):
                value = dec.args[0].value
                if isinstance(value, str):
                    out.append((method.upper(), value))
    return out
