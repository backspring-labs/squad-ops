"""Non-gating design-quality observables for the authored-mode window (SIP-0103 §5c.7).

**Why this exists, stated plainly:** M4 removed the mandatory human manifest review, and the
argument for removing it was that design quality moves to *sampling, not gating*, carried by
four diagnostics §5c.7 requires — structural diff against the human reference, revision and
attempt counts, the gate-rejection taxonomy, and manifest size/surface counts. Revision counts
(M5) and the taxonomy (M6) were built. **These two were not**, so the argument for dropping the
review was half-funded until now. Recorded as SIP-0103 §5d C.

**FAY is structurally blind to what these measure.** V4 roll 2 flattened the reference's typed
``Participant`` entity into an untyped list and still went green: the app installed, built,
booted and answered every probe. A yield number cannot see a design regression that the app
happens to survive, and a multi-roll window with no design instrument reports "it worked" while
the designs drift.

The sharper risk is that **the squad authors the exam it sits.** The manifest decides the
contract and the contract decides the checks, so a roll can win by declaring less. Executed
checks were 29 on V4 roll 2 and 57 on V5 — same PRD. ``surface_counts`` is what makes that
visible; a floor would be the wrong instrument, since it invites padding in the other direction.

**Contamination discipline (§4, §5c.1).** The reference manifest is excluded from squad inputs.
Nothing here is wired into a handler, a capability, or the executor, and
``tests/unit/cycles/test_manifest_diagnostics.py`` pins that: these are read by an operator
after a window, never by a cycle during one. Non-gating is likewise structural — this module
returns data and raises nothing that could fail a run.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

# --------------------------------------------------------------------------- #
# Surface counts
# --------------------------------------------------------------------------- #

#: The counted surfaces, in report order. Named rather than derived by introspection so that
#: adding a manifest field is a deliberate act here — a count that silently appears mid-window
#: makes two rolls incomparable, which is the one thing a window cannot tolerate.
SURFACE_KEYS: tuple[str, ...] = (
    "entities",
    "entity_fields",
    "endpoints",
    "endpoints_declaring_status",
    "request_shapes",
    "error_codes",
    "routes",
    "testids",
    "decisions",
    "unresolved_decisions",
)


def surface_counts(manifest: Any) -> dict[str, int]:
    """How much interface this manifest declares (§5c.7).

    Every key in :data:`SURFACE_KEYS` is always present, including zeros: an absent key and a
    zero are different facts, and a window that silently omits one cannot be aggregated.
    """
    api = manifest.api
    frontend = manifest.frontend
    error_codes = len(api.error_contract.codes) if api.error_contract else 0
    return {
        "entities": len(manifest.entities),
        "entity_fields": sum(len(e.fields) for e in manifest.entities),
        "endpoints": len(api.endpoints),
        "endpoints_declaring_status": sum(1 for e in api.endpoints if e.success_status),
        "request_shapes": len(api.request_shapes),
        "error_codes": error_codes,
        "routes": len(frontend.routes),
        "testids": sum(len(r.testids) for r in frontend.routes),
        "decisions": len(manifest.decisions),
        "unresolved_decisions": sum(1 for d in manifest.decisions if d.unresolved),
    }


# --------------------------------------------------------------------------- #
# Structural diff against the reference
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class SurfaceDiff:
    """One surface's three-way split. ``changed`` is only populated where a shared key can
    carry differing detail — an endpoint's status, an entity's fields."""

    surface: str
    only_authored: tuple[str, ...] = ()
    only_reference: tuple[str, ...] = ()
    changed: tuple[str, ...] = ()

    @property
    def identical(self) -> bool:
        return not (self.only_authored or self.only_reference or self.changed)


@dataclass(frozen=True)
class ManifestDiff:
    """A structural comparison, deliberately not a score.

    §5c.7 declines "maintainability"/"elegance" metrics because no deterministic
    representation exists and an LLM-graded score is the evidence laundering A6 forbids. So
    this reports *what differs* and leaves *whether that is worse* to a reader. Distance from
    the human design is not error — V4 roll 2 chose 409 for the conflict case where roll 1 chose
    400, and 409 is the better answer.
    """

    diffs: tuple[SurfaceDiff, ...] = ()
    authored_counts: dict[str, int] = field(default_factory=dict)
    reference_counts: dict[str, int] = field(default_factory=dict)

    @property
    def identical(self) -> bool:
        return all(d.identical for d in self.diffs)

    @property
    def divergent_surfaces(self) -> tuple[str, ...]:
        return tuple(d.surface for d in self.diffs if not d.identical)


def _split(
    surface: str,
    authored: dict[str, Any],
    reference: dict[str, Any],
) -> SurfaceDiff:
    a_keys, r_keys = set(authored), set(reference)
    changed = tuple(
        sorted(
            f"{k}: {reference[k]} -> {authored[k]}"
            for k in a_keys & r_keys
            if authored[k] != reference[k]
        )
    )
    return SurfaceDiff(
        surface=surface,
        only_authored=tuple(sorted(a_keys - r_keys)),
        only_reference=tuple(sorted(r_keys - a_keys)),
        changed=changed,
    )


def _endpoint_detail(manifest: Any) -> dict[str, Any]:
    return {
        f"{e.method} {e.path}": f"status={e.success_status or '-'} errors={','.join(sorted(e.errors)) or '-'}"
        for e in manifest.api.endpoints
    }


def _entity_detail(manifest: Any) -> dict[str, Any]:
    return {e.name: ",".join(sorted(f.name for f in e.fields)) or "-" for e in manifest.entities}


def _route_detail(manifest: Any) -> dict[str, Any]:
    return {
        r.path: f"view={r.view} testids={','.join(sorted(r.testids)) or '-'}"
        for r in manifest.frontend.routes
    }


def _error_detail(manifest: Any) -> dict[str, Any]:
    ec = manifest.api.error_contract
    return {c.code: f"http={c.http}" for c in (ec.codes if ec else ())}


def _shape_detail(manifest: Any) -> dict[str, Any]:
    return {
        s.name: f"required={','.join(sorted(s.required)) or '-'}"
        for s in manifest.api.request_shapes
    }


#: Surface name -> projection. The projections are deliberately *shallow strings*: a nested
#: structural diff reads as a merge conflict, and the question this answers is "where did the
#: two designs part company", not "reconcile them".
_SURFACES: tuple[tuple[str, Any], ...] = (
    ("endpoints", _endpoint_detail),
    ("entities", _entity_detail),
    ("routes", _route_detail),
    ("error_codes", _error_detail),
    ("request_shapes", _shape_detail),
)


def structural_diff(authored: Any, reference: Any) -> ManifestDiff:
    """Compare an authored manifest to the human reference (§5b Q3, §5c.7).

    Mechanical and deterministic — the manifest is a typed canonical surface, so this needs no
    model and produces the same answer every time. **Non-gating by construction**: it returns a
    report and has no failure mode.
    """
    return ManifestDiff(
        diffs=tuple(
            _split(name, project(authored), project(reference)) for name, project in _SURFACES
        ),
        authored_counts=surface_counts(authored),
        reference_counts=surface_counts(reference),
    )


# --------------------------------------------------------------------------- #
# Rendering
# --------------------------------------------------------------------------- #


def render(diff: ManifestDiff) -> str:
    """A operator-readable report. Counts first — they are what a multi-roll window trends."""
    lines = ["# Manifest diagnostics (SIP-0103 §5c.7 — non-gating)", "", "## Surface counts", ""]
    lines.append("| surface | authored | reference | delta |")
    lines.append("|---|---|---|---|")
    for key in SURFACE_KEYS:
        a = diff.authored_counts.get(key, 0)
        r = diff.reference_counts.get(key, 0)
        lines.append(f"| {key} | {a} | {r} | {a - r:+d} |")

    lines += ["", "## Structural diff vs the human reference", ""]
    if diff.identical:
        lines.append("No structural divergence.")
        return "\n".join(lines) + "\n"

    for d in diff.diffs:
        if d.identical:
            continue
        lines.append(f"### {d.surface}")
        for label, items in (
            ("only in authored", d.only_authored),
            ("only in reference", d.only_reference),
            ("differing", d.changed),
        ):
            if items:
                lines.append(f"- **{label}:**")
                lines += [f"  - `{item}`" for item in items]
        lines.append("")
    return "\n".join(lines) + "\n"
