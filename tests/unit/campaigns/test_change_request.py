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
    ChangeRequestError,
    ProposalContext,
    RefusalKind,
    apply_manifest_delta,
    content_hash,
    load_stored_change_request,
    parse_change_request,
    role_view,
    stored_change_request,
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
#: The 2.2 window's campaign 4 proposal (#2205), as ruled, and the accepted manifest it was
#: proposed against (the calibration cycle ``cyc_39a36288fdd2``'s).
MESSAGES_V1 = yaml.safe_load((_FIXTURES / "change-request-prop_5af48f5f739c-v1.yaml").read_text())
BASELINE_CMP4 = (_FIXTURES / "baseline-cmp_ff3ddfdfbc70-interface_manifest.yaml").read_text()


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


def test_the_windows_message_proposal_is_refused_for_its_dropped_key_and_its_unbuildable_criteria():
    """#2205, on the stored bytes, entered at the rails as the live proposal reached them.
    ``prop_5af48f5f739c`` v1 put each error's message under ``messages:`` in three endpoint
    definitions, a key the manifest does not define, and reworded a view's purpose. The parser
    dropped the key, so the footprint held only the view and the test globs. Its three criteria
    were served by ``backend/routes.py``, which no build could touch. Bugs caught: a key dropped
    silently, and criteria approved that no build was allowed to meet."""
    verdict = validate_proposal(
        _as_authored(MESSAGES_V1),
        _context(
            proposal_id=MESSAGES_V1["proposal_id"],
            baseline_tree=MESSAGES_V1["baseline_tree"],
            baseline_manifest=BASELINE_CMP4,
            prior_criteria=(),
        ),
    )

    assert verdict.change_request is None
    undefined = [r.detail for r in verdict.refusals if r.kind is RefusalKind.UNDEFINED_KEY]
    assert [d.split(":")[0] for d in undefined] == [
        "modify endpoint 'POST /runs/{run_id}/join'",
        "modify endpoint 'POST /runs/{run_id}/leave'",
        "modify endpoint 'GET /runs/{run_id}'",
    ]
    assert all("messages is not a key the interface manifest defines" in d for d in undefined)
    unbuildable = [
        r.detail for r in verdict.refusals if r.kind is RefusalKind.SURFACE_OUTSIDE_FOOTPRINT
    ]
    assert [d.split(":")[0] for d in unbuildable] == [
        "criterion T1",
        "criterion T2",
        "criterion T3",
    ]
    assert all("is served by backend/routes.py" in d for d in unbuildable)


def test_the_windows_messages_declared_on_their_codes_are_built_by_the_error_module():
    """#2205 gap 3, ruled (a) by the owner on 2026-10-14: the same proposal, its messages declared
    where the ruling puts them, on each code in the error contract. Entered at the rails as the
    live proposal reaches them. The footprint now holds the frozen error module the scaffold
    regenerates, and T1-T3, on endpoints that declare those codes, are buildable. Bugs caught: the
    footprint omitting the module a message change rewrites, and the rail refusing the criteria of
    exactly the change the ruling allows."""
    doc = copy.deepcopy(MESSAGES_V1)
    messages = {
        "duplicate_participant": (409, "A participant with this name has already joined this run."),
        "run_not_found": (404, "This run does not exist."),
        "participant_not_found": (404, "No participant with that name is on this run."),
    }
    doc["manifest_delta"] = [op for op in doc["manifest_delta"] if op["target"] != "endpoint"] + [
        {
            "op": "modify",
            "target": "error_code",
            "key": code,
            "definition": {"http": http, "message": text},
        }
        for code, (http, text) in messages.items()
    ]

    verdict = validate_proposal(
        _as_authored(doc),
        _context(
            proposal_id=doc["proposal_id"],
            baseline_tree=doc["baseline_tree"],
            baseline_manifest=BASELINE_CMP4,
            prior_criteria=(),
        ),
    )

    assert verdict.accepted, verdict.refusals
    assert "backend/errors.py" in verdict.change_request.footprint
    assert "backend/routes.py" not in verdict.change_request.footprint


def test_a_criterion_on_an_endpoint_the_delta_does_change_is_not_refused():
    """The control: the reference request changes ``backend/routes.py`` (its endpoints carry a new
    field), so its endpoint criteria are buildable and nothing new refuses it."""
    verdict = validate_proposal(_authored(), _context())

    assert verdict.accepted, verdict.refusals


def test_an_entity_fields_undefined_key_is_named_with_its_field():
    doc = _authored()
    op = next(o for o in doc["manifest_delta"] if o["target"] == "entity")
    op["definition"]["fields"][0]["label"] = "Name"

    verdict = validate_proposal(doc, _context())

    [refusal] = [r for r in verdict.refusals if r.kind is RefusalKind.UNDEFINED_KEY]
    assert f"fields[{op['definition']['fields'][0]['name']}].label" in refusal.detail


# =============================================================================
# The goals a proposal means to move (SIP-0113 §10t ruling 4)
# =============================================================================

_STORED_REQUESTS = sorted(_FIXTURES.glob("change-request-*.yaml"))


@pytest.mark.parametrize("stored", _STORED_REQUESTS, ids=lambda p: p.stem)
def test_a_request_naming_no_goal_keeps_the_identity_it_was_ruled_on(stored):
    """Three requests stored and ruled on before §4.5. Bug caught: an empty ``moves_goals`` written
    into the document or its hash, so every stored request is refused on load and every ruling
    binds to a hash no request has."""
    document = stored.read_text()
    request = load_stored_change_request(document)
    authored = {**yaml.safe_load(document), "moves_goals": []}
    for derived in ("footprint", "content_hash", "proposal_id", "version", "baseline_tree"):
        authored.pop(derived)

    reparsed = parse_change_request(
        authored,
        proposal_id=request.proposal_id,
        version=request.version,
        baseline_tree=request.baseline_tree,
    )

    assert content_hash(reparsed) == request.content_hash
    assert stored_change_request(request) == document
    assert role_view(document) is document


def test_the_goals_a_request_names_are_bound_by_its_ruling_and_kept_from_every_other_role():
    """Bugs caught: the goals left out of the hash, so a request whose named goals were changed
    after its ruling still loads as ruled; and the framing shown them, so a build role learns
    which held-out goal its work is aimed at."""
    verdict = validate_proposal(
        _authored(moves_goals=["goal_export"]), _context(shown_goals=("goal_export", "goal_sort"))
    )
    assert verdict.accepted, verdict.refusals
    request = verdict.change_request
    document = stored_change_request(request)
    unnamed = validate_proposal(_authored(), _context()).change_request

    assert load_stored_change_request(document).moves_goals == ("goal_export",)
    assert request.content_hash != unnamed.content_hash
    stripped = yaml.safe_dump(
        {k: v for k, v in yaml.safe_load(document).items() if k != "moves_goals"}, sort_keys=False
    )
    with pytest.raises(ChangeRequestError, match="does not match its hash"):
        load_stored_change_request(stripped)
    view = role_view(document)
    assert "goal_export" not in view
    assert yaml.safe_load(view) == {
        k: v for k, v in yaml.safe_load(document).items() if k != "moves_goals"
    }


@pytest.mark.parametrize(
    ("shown", "named", "unknown"),
    [
        ((), ["goal_export"], "goal_export"),
        (("goal_export", "goal_sort"), ["goal_sort"], None),
        # Ruling 5: a goal already passing is still one it was shown, so it is not refused here.
        (("goal_export",), ["goal_export", "goal_other", "goal_other"], "goal_other"),
    ],
)
def test_a_proposal_may_name_only_the_goals_it_was_shown(shown, named, unknown):
    """Bug caught: an invented goal id accepted, so the ledger reads a prediction against a goal
    no proposal could see; or a shown goal refused."""
    verdict = validate_proposal(_authored(moves_goals=named), _context(shown_goals=shown))

    refused = [r.detail for r in verdict.refusals if r.kind is RefusalKind.UNKNOWN_GOAL]
    if unknown is None:
        assert verdict.accepted and refused == []
    else:
        assert refused == [
            f"moves_goals names {unknown}, which is not the id of a goal this proposal was "
            "shown; name only goals its evidence lists"
        ]


def test_an_unknown_goal_is_refused_with_every_other_refusal():
    """Every refusal, never only the first. Bug caught: the goal rail returning early, so the
    model fixes one reason per revision and spends its budget."""
    verdict = validate_proposal(
        _authored(moves_goals=["goal_x"], must_not_break=["Z9"]), _context()
    )

    assert {r.kind for r in verdict.refusals} >= {
        RefusalKind.UNKNOWN_GOAL,
        RefusalKind.UNKNOWN_PRIOR_CRITERION,
    }


@pytest.mark.parametrize("named", ["goal_export", [""], [3], {"goal_export": True}])
def test_moves_goals_that_is_not_a_list_of_ids_is_malformed(named):
    """Bug caught: a string read as its characters, or a blank id carried to the ledger."""
    verdict = validate_proposal(
        _authored(moves_goals=named), _context(shown_goals=("goal_export",))
    )

    [refusal] = verdict.refusals
    assert refusal.kind is RefusalKind.MALFORMED and "moves_goals" in refusal.detail
