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
#: The 2.0 set's campaign 1, increment 2, version 1 as stored, and the accepted manifest it was
#: proposed against (read from its proposal cycle's stored ``campaign_proposal`` block).
EMPTY_DELTA_V1 = yaml.safe_load(
    (_FIXTURES / "change-request-prop_5fb2d8136c36-v1.yaml").read_text()
)
BASELINE_CMP1_INC2 = (
    _FIXTURES / "baseline-cmp_c4b81554bd59-increment-2-interface_manifest.yaml"
).read_text()


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


def test_a_new_criterion_may_not_take_a_frozen_criterions_id():
    """§8.1. Bug caught: a second increment naming its first criterion C1 again — the new test
    written over the frozen one's file, and its bundle filed under the old criterion's id."""
    doc = _authored()
    doc["criteria"][0]["id"] = "B2"  # frozen by an earlier increment (_context's prior)

    verdict = validate_proposal(doc, _context())

    assert [r.kind for r in verdict.refusals] == [RefusalKind.REUSED_CRITERION]
    assert verdict.refusals[0].detail.startswith("B2 already name")


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


def _as_authored(stored: dict) -> dict:
    """A stored change request as its author wrote it: without the fields the framework derives."""
    derived = ("footprint", "content_hash", "proposal_id", "version", "baseline_tree")
    return {k: v for k, v in stored.items() if k not in derived}


def test_the_2_0_sets_empty_delta_feature_is_refused_with_nothing_to_build():
    """#1961, on the stored bytes. ``prop_5fb2d8136c36`` v1 (``kind: feature``,
    ``manifest_delta: []``) passed every rail in the 2.0 set and reached the supervisor's gate,
    though its derived footprint held only the qa test namespace. Bug caught: a behaviour change
    no build could deliver being approved on its criteria."""
    verdict = validate_proposal(
        _as_authored(EMPTY_DELTA_V1),
        _context(
            proposal_id=EMPTY_DELTA_V1["proposal_id"],
            baseline_tree=EMPTY_DELTA_V1["baseline_tree"],
            baseline_manifest=BASELINE_CMP1_INC2,
            prior_criteria=("T1",),
        ),
    )

    assert [r.kind for r in verdict.refusals] == [RefusalKind.NOTHING_TO_BUILD]
    assert verdict.change_request is None
    assert "already built" in verdict.refusals[0].detail


@pytest.mark.parametrize(
    ("kind", "refused"),
    [("feature", True), ("fix", True), ("refactor", False)],
)
def test_an_empty_delta_has_nothing_to_build_unless_it_is_a_refactor(kind, refused):
    """#1961. Bugs caught: a ``fix`` slipping past the rail the ``feature`` meets, or a
    ``refactor`` (no new behaviour, no criteria, the build may restructure tests alone) refused
    for a footprint it is entitled to."""
    doc = _authored(kind=kind, manifest_delta=[])
    if kind == "refactor":
        doc["criteria"] = []

    verdict = validate_proposal(doc, _context())

    assert (RefusalKind.NOTHING_TO_BUILD in _kinds(verdict)) is refused
