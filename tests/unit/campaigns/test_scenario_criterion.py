"""A scenario criterion on a repository-backed Project (#3044, part 2; SIP-0117 R5.8).

Entered at ``validate_proposal``, the function the proposal task's handler calls, with the
product context the run composes. The vocabulary is the fixture provider's, as a supplier's kept
skill would hold it (SIP-0116 §17g); the declaration is the remote-execution fixture's.
"""

from __future__ import annotations

import copy
import dataclasses

import pytest

from adapters.remote_execution.fixture_operation_runner import VOCABULARY
from squadops.campaigns.change_request import (
    PlacedCriterionFile,
    ProposalContext,
    RefusalKind,
    load_stored_change_request,
    stored_change_request,
    validate_proposal,
)
from squadops.capabilities.handlers.planning.proposal import product_context
from tests.unit.campaigns.test_product_change_request import _PRODUCT, _context
from tests.unit.remote_execution.scenario_fixture import DOOR_OPENS

_SCENARIO_PRODUCT = dataclasses.replace(_PRODUCT, scenario_vocabulary=VOCABULARY)


def _scenario(**changes) -> dict:
    declaration = copy.deepcopy(DOOR_OPENS)
    declaration.update(changes)
    return declaration


def _request(scenario=None, **criterion) -> dict:
    return {
        "kind": "feature",
        "prd_delta": [{"id": "door", "op": "add", "text": "The door opens from its panel."}],
        "footprint": ["tally/report.py"],
        "criteria": [
            {
                "id": "C-2",
                "statement": "Clicking the panel's button opens the door",
                "surface_kind": "scenario",
                "surface": "Workspace.Door",
                "observable": "the door stops colliding, so the player can walk through",
                "scenario": scenario if scenario is not None else _scenario(),
                **criterion,
            }
        ],
        "must_not_break": [],
    }


def _ctx(product=_SCENARIO_PRODUCT) -> ProposalContext:
    return _context(product=product)


def test_a_scenario_criterion_is_placed_by_the_framework_and_kept_with_its_declaration():
    """Bugs caught: a scenario criterion sent to a runner's placement (none runs it, so it is
    refused as unplaceable); its file left out of the footprint, so the plan gate's frozen-file
    rules don't keep tasks off it; its declaration dropped from the stored request, so what was
    ruled on isn't what is frozen."""
    verdict = validate_proposal(_request(), _ctx())

    assert verdict.accepted, verdict.refusals
    request = verdict.change_request
    assert request.criterion_files == (
        PlacedCriterionFile("C-2", ".squadops/scenarios/criterion_C_2.json"),
    )
    assert ".squadops/scenarios/criterion_C_2.json" in request.footprint
    assert request.criteria[0].scenario == DOOR_OPENS
    assert load_stored_change_request(stored_change_request(request)) == request


def test_a_request_with_no_scenario_keeps_its_document_and_hash():
    """Bug caught: every stored request's hash moved by an empty ``scenario`` key, so a ruled
    request no longer loads."""
    request = validate_proposal(
        {
            **_request(),
            "criteria": [
                {
                    "id": "R1",
                    "statement": "The report's last line is the total",
                    "surface_kind": "package",
                    "surface": "tally.report",
                    "observable": "render([3, 4])'s last line is 'total 7'",
                }
            ],
        },
        _ctx(),
    ).change_request

    assert "scenario" not in stored_change_request(request)


@pytest.mark.parametrize(
    ("authored", "product", "kind", "says"),
    [
        (_request(), _PRODUCT, RefusalKind.SCENARIO_UNVERIFIABLE, "keeps no scenario reader"),
        (
            _request(_scenario(steps=[{"action": "execute_luau", "code": "x"}])),
            _SCENARIO_PRODUCT,
            RefusalKind.SCENARIO_OUTSIDE_VOCABULARY,
            "action 'execute_luau' is outside fixture/1's vocabulary",
        ),
        (
            _request(_scenario(scenario_id="C-9")),
            _SCENARIO_PRODUCT,
            RefusalKind.SCENARIO_OUTSIDE_VOCABULARY,
            "names itself 'C-9'",
        ),
        (
            _request(surface="Workspace.Gate"),
            _SCENARIO_PRODUCT,
            RefusalKind.SCENARIO_OUTSIDE_VOCABULARY,
            "its named assertion door-open observes 'Workspace.Door'",
        ),
    ],
    ids=["no vocabulary kept", "outside the vocabulary", "another criterion's id", "a surface"],
)
def test_a_scenario_its_reader_cant_run_is_refused_to_its_author(authored, product, kind, says):
    """Bug caught: a scenario frozen that no provider could run, or whose surface names a path
    its assertion never reads, so the plan gate shows a reviewer the wrong thing."""
    verdict = validate_proposal(authored, _ctx(product))

    assert not verdict.accepted
    assert [r.kind for r in verdict.refusals] == [kind]
    assert says in verdict.refusals[0].detail


@pytest.mark.parametrize(
    ("criterion", "says"),
    [
        ({"surface_kind": "package", "surface": "tally.report"}, "Leave scenario out"),
        ({"scenario": "door_opens.json"}, "declares its scenario: an object"),
    ],
)
def test_a_scenario_on_the_wrong_criterion_or_not_an_object_is_malformed(criterion, says):
    """Bug caught: a declaration on a package criterion silently kept, or a path to a file
    accepted as one."""
    verdict = validate_proposal(_request(**criterion), _ctx())

    assert [r.kind for r in verdict.refusals] == [RefusalKind.MALFORMED]
    assert says in verdict.refusals[0].detail


def test_the_proposals_product_context_reads_the_kept_vocabulary_and_none_without_it():
    """The wiring between the runtime's input and the rails. Bug caught: the vocabulary the
    runtime composed dropped on the way to the rails, so every scenario reads unverifiable; or
    an input with no vocabulary read as some default reader's."""
    base = {"profile": {"public_surfaces": [], "placements": []}}

    with_vocabulary = product_context({**base, "scenario_vocabulary": VOCABULARY.to_document()})

    assert with_vocabulary.scenario_vocabulary == VOCABULARY
    assert product_context(base).scenario_vocabulary is None
