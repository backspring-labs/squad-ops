"""The typed change request and its rails (SIP-0109 §7.2, §9.1; #1706), on real manifests.

The baseline is the 1.9 roll cyc_7a4b7a6fbf0e's own authored manifest, and the request is the
validation plan's reference scenario (§4): the PRD's capacity limit, criteria C1–C3.
"""

from __future__ import annotations

import copy
from pathlib import Path

import pytest
import yaml

from squadops.campaigns.change_request import (
    ChangeKind,
    ProposalContext,
    RefusalKind,
    apply_manifest_delta,
    content_hash,
    parse_change_request,
    validate_proposal,
)

_FIXTURES = Path(__file__).resolve().parents[2] / "fixtures" / "campaigns"
BASELINE = (_FIXTURES / "baseline-cyc_7a4b7a6fbf0e-interface_manifest.yaml").read_text()
REFERENCE = yaml.safe_load((_FIXTURES / "reference-capacity-change-request.yaml").read_text())


def _context(**overrides) -> ProposalContext:
    values = dict(
        proposal_id="prop_1",
        version=1,
        baseline_tree="tree:7a4b7a6f",
        baseline_manifest=BASELINE,
        expected_stack="fullstack_fastapi_react",
        allowed_scope=("backend/**", "frontend/**"),
        prior_criteria=("B1", "B2"),
    )
    values.update(overrides)
    return ProposalContext(**values)


def _authored(**overrides) -> dict:
    doc = copy.deepcopy(REFERENCE)
    doc.update(overrides)
    return doc


def _kinds(verdict) -> set[RefusalKind]:
    return {r.kind for r in verdict.refusals}


def test_the_reference_request_passes_every_rail_on_the_real_baseline():
    """The validation plan's reference scenario, end to end through the rails. Bug caught: a
    footprint that is not the delta's — too wide lets the build rewrite the app, too narrow
    refuses the change it was approved for."""
    verdict = validate_proposal(_authored(), _context())

    assert verdict.accepted, verdict.refusals
    request = verdict.change_request
    assert request.footprint == (
        "backend/errors.py",
        "backend/models.py",
        "backend/routes.py",
        "frontend/src/views/RunDetailView.jsx",
        "backend/tests/**",
        "frontend/src/__tests__/**",
        "frontend/src/tests/**",
    )
    assert [c.id for c in request.criteria] == ["C1", "C2", "C3"]
    assert (
        "capacity" in yaml.safe_load(verdict.candidate_manifest)["entities"][0]["fields"][7]["name"]
    )
    assert request.content_hash == content_hash(request)


def test_an_out_of_scope_delta_is_refused_not_trimmed():
    """§9.1: refused, never trimmed. Bug caught: the frontend half silently dropped so the
    backend half builds."""
    verdict = validate_proposal(_authored(), _context(allowed_scope=("backend/**",)))

    assert verdict.change_request is None
    [refusal] = verdict.refusals
    assert refusal.kind is RefusalKind.OUT_OF_SCOPE
    assert "frontend/src/views/RunDetailView.jsx" in refusal.detail


def test_a_delta_the_manifest_gates_refuse_never_reaches_the_gate():
    """§7.2: the SIP-0103 gates run on the manifest the delta produces. Here the detail route
    loses its test ids, so qa would have no anchor to query."""
    doc = _authored()
    for op in doc["manifest_delta"]:
        if op["target"] == "client_route":
            op["definition"]["testids"] = []

    verdict = validate_proposal(doc, _context())

    assert verdict.change_request is None
    assert [r.kind for r in verdict.refusals] == [RefusalKind.MANIFEST_GATES]
    assert verdict.refusals[0].detail.startswith("testid_coverage:")


@pytest.mark.parametrize(
    ("op", "detail"),
    [
        (
            {"op": "modify", "target": "entity", "key": "Ghost", "definition": {"name": "Ghost"}},
            "does not exist",
        ),
        (
            {"op": "add", "target": "entity", "key": "Run", "definition": {"name": "Run"}},
            "already exists",
        ),
        (
            {"op": "modify", "target": "entity", "key": "Run", "definition": {"name": "Walk"}},
            "names 'Walk'",
        ),
        ({"op": "remove", "target": "error_code", "key": "nope"}, "does not exist"),
    ],
    ids=["modify-missing", "add-present", "definition-renames", "remove-missing"],
)
def test_an_operation_that_does_not_fit_the_baseline_is_refused(op, detail):
    verdict = validate_proposal(_authored(manifest_delta=[op]), _context())
    assert RefusalKind.DELTA_DOES_NOT_FIT in _kinds(verdict)
    assert any(detail in r.detail for r in verdict.refusals)


@pytest.mark.parametrize("field", ["footprint", "content_hash", "proposal_id", "version"])
def test_a_proposal_may_not_author_what_the_framework_derives(field):
    """§7.2: the footprint is derived, never authored; the identity and hash are the
    framework's. Bug caught: a proposal widening its own write grants."""
    verdict = validate_proposal(_authored(**{field: "x"}), _context())
    assert [r.kind for r in verdict.refusals] == [RefusalKind.AUTHORED_DERIVED_FIELD]


def test_a_criterion_on_a_surface_the_delta_does_not_produce_is_refused():
    doc = _authored()
    doc["criteria"][1]["surface"] = "DELETE /runs/{run_id}"

    verdict = validate_proposal(doc, _context())

    assert [r.kind for r in verdict.refusals] == [RefusalKind.UNKNOWN_SURFACE]
    assert "C2" in verdict.refusals[0].detail


def test_every_refusal_is_reported_not_only_the_first():
    """Bug caught: the role fixing one refusal per retry and burning the proposal-retry budget
    on a document with three."""
    doc = _authored(
        must_not_break=["B1", "Z9"],
        retires=[{"criterion_id": "B1", "reason": "replaced"}],
    )
    doc["criteria"][0]["surface"] = "PUT /runs"

    verdict = validate_proposal(doc, _context())

    assert _kinds(verdict) == {
        RefusalKind.UNKNOWN_PRIOR_CRITERION,
        RefusalKind.KEEP_AND_RETIRE,
        RefusalKind.UNKNOWN_SURFACE,
    }


@pytest.mark.parametrize(
    ("kind", "accepted"), [(ChangeKind.FEATURE, False), (ChangeKind.REFACTOR, True)]
)
def test_only_a_refactor_may_name_no_criteria(kind, accepted):
    verdict = validate_proposal(_authored(kind=str(kind), criteria=[]), _context())
    assert verdict.accepted is accepted


def test_the_content_hash_moves_with_the_content_and_not_with_the_identity():
    """The ruling binds to the hash (§9.2). Bug caught: a revision with new content keeping the
    old hash, so a stale ruling still matches; or a re-numbered version moving it."""
    first = parse_change_request(REFERENCE, proposal_id="p", version=1, baseline_tree="t")
    renumbered = parse_change_request(REFERENCE, proposal_id="q", version=2, baseline_tree="u")
    revised = parse_change_request(
        _authored(prd_delta=[{"id": "capacity-limit", "op": "add", "text": "different"}]),
        proposal_id="p",
        version=2,
        baseline_tree="t",
    )
    assert content_hash(first) == content_hash(renumbered) != content_hash(revised)


def test_applying_the_delta_leaves_the_baseline_text_untouched():
    """The accepted manifest is immutable (§7.1). Bug caught: an in-place edit of the parsed
    baseline leaking into the next proposal's validation."""
    request = parse_change_request(REFERENCE, proposal_id="p", version=1, baseline_tree="t")
    before = yaml.safe_load(BASELINE)

    apply_manifest_delta(BASELINE, request.manifest_delta)

    assert yaml.safe_load(BASELINE) == before
    assert "capacity" not in BASELINE
