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
from squadops.campaigns.increment_tree import increment_criterion_files, suite_criterion_files
from squadops.capabilities.handlers.planning.proposal import product_context
from squadops.cycles.implementation_plan import ImplementationPlan
from squadops.cycles.task_plan import _inject_increment_indexes
from squadops.execution.source_delivery import placed_framework_files
from squadops.remote_execution.scenario import frozen_scenario, scenario_digest
from tests.unit.campaigns.test_product_change_request import _PRODUCT, _context
from tests.unit.campaigns.test_product_page_loader import _Vault, increment
from tests.unit.remote_execution.scenario_fixture import DOOR_OPENS, SCENARIO_PATH

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
    assert request.criterion_files == (PlacedCriterionFile("C-2", SCENARIO_PATH),)
    assert SCENARIO_PATH in request.footprint
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


# ---------------------------------------------------------------- the framework's file (C2a)


def _stored_with_a_suite_criterion() -> str:
    """A stored request with a scenario criterion and a package criterion beside it."""
    authored = _request()
    authored["criteria"].append(
        {
            "id": "R1",
            "statement": "The report's last line is the total",
            "surface_kind": "package",
            "surface": "tally.report",
            "observable": "render([3, 4])'s last line is 'total 7'",
        }
    )
    verdict = validate_proposal(authored, _ctx())
    assert verdict.accepted, verdict.refusals
    return stored_change_request(verdict.change_request)


async def test_delivery_writes_the_frozen_declaration_into_the_candidate():
    """The wiring, entered at the delivery hook every repository-backed increment's candidate
    passes through. Bugs caught: a scenario's declaration missing from the delivered candidate,
    so Campaign acceptance finds nothing to run; or a text other than the frozen one, so the
    provider refuses it as changed after freezing."""
    vault = _Vault()
    cycle = increment(vault, _stored_with_a_suite_criterion())

    files = await placed_framework_files(cycle, vault)

    text = files[SCENARIO_PATH].decode("utf-8")
    assert scenario_digest(text) == frozen_scenario(DOOR_OPENS, VOCABULARY).digest
    assert set(files) == {SCENARIO_PATH}


def test_a_qa_suite_is_held_to_its_criteria_and_never_to_a_scenarios_declaration():
    """Bug caught: a scenario's declaration routed to a qa task as a test file to write, so the
    plan gate refuses every plan that doesn't write it, and the head check runs it as a test."""
    stored = _stored_with_a_suite_criterion()

    every = increment_criterion_files(stored, "")
    suite = suite_criterion_files(every)

    assert [f.criterion_id for f in every] == ["C-2", "R1"]
    assert [f.criterion_id for f in suite] == ["R1"]


def _plan(*artifacts: str) -> ImplementationPlan:
    listed = "".join(f'\n      - "{a}"' for a in artifacts) or " []"
    return ImplementationPlan.from_yaml(
        "version: 1\nproject_id: p\ncycle_id: c\nprd_hash: h\ntasks:\n"
        "  - task_index: 0\n    task_type: development.develop\n    role: dev\n"
        '    focus: "Door"\n    description: "Open the door"\n'
        f"    expected_artifacts:{listed}\n    depends_on: []\n"
        "summary:\n  total_tasks: 1\n"
    )


def test_the_plan_gate_refuses_a_task_that_writes_a_scenarios_declaration():
    """Bug caught: a task allowed to write the declaration, so its edit is discarded at delivery
    unread, or, if it were kept, the frozen scenario is replaced by the squad's."""
    errors = _plan("src/door.luau", SCENARIO_PATH).validate_increment_scenario_files(
        {SCENARIO_PATH: "C-2"}
    )

    assert len(errors) == 1
    assert "the declaration of scenario criterion C-2" in errors[0]
    assert _plan("src/door.luau").validate_increment_scenario_files({SCENARIO_PATH: "C-2"}) == []


def test_a_planner_is_never_offered_a_scenarios_declaration_to_claim():
    """Bug caught: the declaration listed among the footprint's claimable files, so a compliant
    planner names it and the gate refuses the plan it was taught to write."""
    inputs: dict = {}

    _inject_increment_indexes(inputs, ("src/door.luau", SCENARIO_PATH), ())

    assert inputs["increment_footprint_index"] == "- `src/door.luau`"


# ---------------------------------------------------------------- the operation step (C2b)


def _equipped(monkeypatch):
    """The Tally increment's cycle, equipped as cycle creation equips one whose work requires
    the fixture skillsets, with the deployment's catalog holding the scenario's tool."""
    from squadops.capabilities import skillsets
    from tests.unit.capabilities.test_operation_supply import TOOL, _catalog
    from tests.unit.cycles._product_increment import increment_cycle
    from tests.unit.cycles.skillset_fixture import built, requiring_config

    catalog = _catalog(TOOL)
    record, _ = built(requiring_config(monkeypatch), catalog)
    monkeypatch.setattr(skillsets, "packaged_skillsets", lambda: catalog)
    return dataclasses.replace(increment_cycle(), skillset_record=record), catalog


def test_plan_expansion_appends_one_operation_step_that_runs_the_frozen_scenario(monkeypatch):
    """The wiring, entered at ``generate_task_plan`` for the increment's implementation run, as
    ``RunProvisioning.prepare`` calls it. Bugs caught: a scenario criterion that no task runs;
    one run under a tool other than the one the cycle recorded; a scenario whose digest isn't
    the frozen one, so the provider refuses it; or no repair surface, so a failed assertion has
    nothing to be repaired in."""
    from squadops.cycles.task_plan import generate_task_plan
    from tests.unit.cycles._product_increment import plan, run, squad

    cycle, catalog = _equipped(monkeypatch)

    envelopes = generate_task_plan(
        cycle,
        run("implementation"),
        squad(),
        plan=plan("tally/report.py"),
        change_request=_stored_with_a_suite_criterion(),
    )

    [step] = [e for e in envelopes if e.task_type == "qa.run_remote_operation"]
    frozen = frozen_scenario(DOOR_OPENS, VOCABULARY)
    assert step.agent_id == "eve"
    assert step.inputs["operation"] == {
        "contract": "fixture.scenario",
        "mode": "play",
        "role": "qa",
        "skillset": "fixture-qa",
        "skillset_digest": catalog["fixture-qa"].digest,
        "agent_id": "eve",
    }
    assert step.inputs["operation_scenario"] == {
        "scenario_id": "C-2",
        "digest": frozen.digest,
        "assertions": ["spawned", "door-open"],
        "named_assertion": "door-open",
        "path": SCENARIO_PATH,
        "document": frozen.document,
    }
    assert step.inputs["implementation_artifacts"] == ["tally/report.py"]
    # After the plan's body, which builds the candidate it verifies.
    assert envelopes.index(step) > max(
        i for i, e in enumerate(envelopes) if e.task_type == "development.develop"
    )


def test_a_scenario_no_one_can_run_stops_plan_expansion_by_name(monkeypatch):
    """Bug caught: a scenario criterion silently dropped from the plan because its cycle's
    record offers no operation, so the increment is judged without it."""
    from squadops.cycles.models import CycleError
    from squadops.cycles.task_plan import generate_task_plan
    from tests.unit.cycles._product_increment import plan, run, squad

    cycle, _ = _equipped(monkeypatch)
    cycle = dataclasses.replace(cycle, skillset_record=None)

    with pytest.raises(CycleError, match="names scenario criteria \\(C-2\\), and none can be run"):
        generate_task_plan(
            cycle,
            run("implementation"),
            squad(),
            plan=plan("tally/report.py"),
            change_request=_stored_with_a_suite_criterion(),
        )
