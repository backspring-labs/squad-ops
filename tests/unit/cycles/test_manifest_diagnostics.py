"""The design-quality signal M4 spent before it existed (SIP-0103 §5c.7).

M4 removed the mandatory human manifest review arguing that design quality moves to *sampling,
not gating*, carried by four diagnostics — structural diff vs the human reference, revision and
attempt counts, the gate-rejection taxonomy, and manifest size/surface counts. Two were built
(M5, M6). **These two were not**, so the justification for dropping a human gate was half-funded
until now (SIP-0103 §5d C).

Bug classes guarded:

- **a design regression that the app survives** — the case that motivated this. V4 roll 2
  flattened the reference's typed `Participant` entity into an untyped list and still went
  green: installed, built, booted, answered every probe. FAY is structurally blind to it;
- **the squad shrinking the exam it sits.** The manifest decides the contract and the contract
  decides the checks, so a roll can win by declaring less — 29 executed checks on V4 roll 2
  against 57 on V5, same PRD. A count that only appears when non-zero would hide exactly the
  roll that declared nothing;
- the diagnostic reporting noise on an unchanged design, which is how an advisory signal earns
  being ignored;
- **the reference manifest reaching the squad.** It is excluded from authoring inputs (§4,
  §5c.1), so this comparison is operator-run and must stay unreachable from the pipeline;
- the diagnostic acquiring a failure mode. §5c.7 is explicitly non-gating; a diff that can
  raise becomes a gate the first time it does;
- a surface silently entering or leaving the count set mid-window, which makes two rolls
  incomparable — the one thing a pre-registered window cannot absorb.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from squadops.capabilities.scaffold import InterfaceManifest
from squadops.cycles.manifest_diagnostics import (
    SURFACE_KEYS,
    render,
    structural_diff,
    surface_counts,
)

pytestmark = [pytest.mark.domain_contracts]

_ROOT = Path(__file__).resolve().parents[3]
_REFERENCE = InterfaceManifest.from_yaml(
    (_ROOT / "examples" / "03_group_run" / "interface_manifest.yaml").read_text(encoding="utf-8")
)
_AUTHORED = InterfaceManifest.from_yaml(
    (_ROOT / "tests" / "fixtures" / "authored_v4" / "interface_manifest_roll2.yaml").read_text(
        encoding="utf-8"
    )
)


def _surface(diff, name):
    return next(d for d in diff.diffs if d.surface == name)


# --------------------------------------------------------------------------- #
# The case this exists for
# --------------------------------------------------------------------------- #


def test_the_flattened_entity_that_went_green_is_detected():
    """V4 roll 2's one real divergence from the human design: the reference models
    `Participant` as a typed entity; the authored manifest collapsed it into an untyped list.
    The delivered app installed, built, booted and answered all five probes — so yield saw
    nothing. This is the instrument that does."""
    diff = structural_diff(_AUTHORED, _REFERENCE)

    assert "Participant" in _surface(diff, "entities").only_reference
    assert diff.authored_counts["entities"] < diff.reference_counts["entities"]
    assert "entities" in diff.divergent_surfaces


def test_a_shrinking_declared_surface_is_visible_in_the_counts():
    """The squad authors the exam it sits: fewer endpoints means fewer derived checks means an
    easier green. A window with no size instrument cannot tell a strong roll from a small one."""
    import dataclasses

    from squadops.capabilities.scaffold import Api

    narrowed = dataclasses.replace(
        _AUTHORED,
        api=Api(
            base_path=_AUTHORED.api.base_path,
            request_shapes=_AUTHORED.api.request_shapes,
            endpoints=_AUTHORED.api.endpoints[:2],
            error_contract=_AUTHORED.api.error_contract,
        ),
    )

    assert surface_counts(narrowed)["endpoints"] == 2
    assert surface_counts(_AUTHORED)["endpoints"] == 5

    diff = structural_diff(narrowed, _AUTHORED)
    assert not diff.identical
    assert len(_surface(diff, "endpoints").only_reference) == 3, (
        "the three dropped endpoints must be named, not merely counted"
    )


def test_differing_detail_on_a_shared_key_is_reported_not_dropped():
    """A set difference alone would call `POST /runs/{run_id}/join` "present in both" while the
    two designs disagreed on its success status and one of its error codes."""
    changed = _surface(structural_diff(_AUTHORED, _REFERENCE), "endpoints").changed

    assert any("join" in c for c in changed)
    assert any("status=" in c for c in changed)


# --------------------------------------------------------------------------- #
# Counts
# --------------------------------------------------------------------------- #


def test_every_surface_is_always_counted_including_zeros():
    """An absent key and a zero are different facts. A roll that declared no decisions must
    report `decisions: 0`, not omit the key — otherwise aggregation across a window silently
    drops the rolls that most need explaining."""
    bare = InterfaceManifest.from_yaml(
        "version: 1\nkind: interface_manifest\nproject_id: p\n"
        "stack: fullstack_fastapi_react\napi:\n  endpoints: []\n"
    )

    counts = surface_counts(bare)

    assert set(counts) == set(SURFACE_KEYS)
    assert all(v == 0 for v in counts.values()), counts


def test_the_counts_read_the_reference_correctly():
    """Exact values, not shapes: these are the numbers a window trends, and an off-by-one in
    the instrument is indistinguishable from drift in the thing measured."""
    counts = surface_counts(_REFERENCE)

    assert counts["endpoints"] == 5
    assert counts["endpoints_declaring_status"] == 1  # the #772 sparsity, measured
    assert counts["entities"] == 2
    assert counts["decisions"] == 4
    assert counts["unresolved_decisions"] == 0


def test_an_unresolved_decision_is_counted_apart_from_the_rest():
    """M4's gate fires on unresolved decisions, so the window needs to relate "how often did the
    gate stop" to "how often did a design decline to guess"."""
    counts = surface_counts(_AUTHORED)

    assert counts["unresolved_decisions"] == 1
    assert counts["decisions"] > counts["unresolved_decisions"]


# --------------------------------------------------------------------------- #
# It must not become a gate, and must not reach the squad
# --------------------------------------------------------------------------- #


def test_an_identical_manifest_reports_no_divergence():
    """Advisory signals that cry wolf get ignored, and this one is the replacement for a human
    review — it has to be quiet when nothing moved."""
    diff = structural_diff(_REFERENCE, _REFERENCE)

    assert diff.identical
    assert diff.divergent_surfaces == ()
    assert "No structural divergence." in render(diff)


def test_an_empty_manifest_diffs_without_raising():
    """§5c.7 is non-gating, which has to be structural rather than a promise: a diff that can
    raise becomes a gate the first time it does, inside the window where nothing may be fixed."""
    bare = InterfaceManifest.from_yaml(
        "version: 1\nkind: interface_manifest\nproject_id: p\n"
        "stack: fullstack_fastapi_react\napi:\n  endpoints: []\n"
    )

    diff = structural_diff(bare, _REFERENCE)

    assert not diff.identical
    assert render(diff)


def test_nothing_in_the_pipeline_can_reach_this_module():
    """Contamination discipline (§4, §5c.1): the reference manifest is excluded from squad
    inputs, and this module *reads the reference*. An import from a handler, capability or the
    executor would make it an input — the diagnostic is operator-run, after a window, never by a
    cycle during one."""
    offenders = []
    for path in (_ROOT / "src" / "squadops").rglob("*.py"):
        if path.name == "manifest_diagnostics.py":
            continue
        if "manifest_diagnostics" in path.read_text(encoding="utf-8"):
            offenders.append(str(path.relative_to(_ROOT)))
    for path in (_ROOT / "adapters").rglob("*.py"):
        if "manifest_diagnostics" in path.read_text(encoding="utf-8"):
            offenders.append(str(path.relative_to(_ROOT)))

    assert offenders == [], f"diagnostics reachable from the pipeline: {offenders}"


def test_the_reference_manifest_is_not_an_authoring_input():
    """The other half of the same guard, stated where the reference is actually consumed."""
    from squadops.cycles.manifest_authoring import AUTHORING_INPUT_CONTRACT

    assert not any("reference" in key for key in AUTHORING_INPUT_CONTRACT)


# --------------------------------------------------------------------------- #
# Rendering
# --------------------------------------------------------------------------- #


def test_the_report_leads_with_counts_and_names_the_divergent_surfaces():
    """Counts first because they are what trends across rolls; the diff is what you read once a
    count moves. §5c.7 declines a score deliberately — distance from the human design is not
    error, and roll 2's 409-for-conflict was better than the reference's."""
    report = render(structural_diff(_AUTHORED, _REFERENCE))

    assert report.index("## Surface counts") < report.index("## Structural diff")
    assert "| entities | 1 | 2 | -1 |" in report
    assert "### entities" in report
    assert "score" not in report.lower()
