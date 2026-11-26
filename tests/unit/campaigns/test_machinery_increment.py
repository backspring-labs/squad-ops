"""A scripted squad's increment through a worker, from its implementation run's start to its
judged delivery (#3050, slice 2, part 1).

Entered at ``execute_run``, which a cycle's launch calls for each of its runs, over the
``machinery`` composition: the real executor, dispatcher and reply router, the real squad on the
scripted model, and the fixture worker over the runtime's real routes. The increment approves one
scenario criterion, C-2: the door opens from its panel.

What bugs would these catch? Each seam on the way is proved on its own elsewhere; these are the
ones a live increment finds and a seam's own test can't:
- plan expansion's operation step not reaching qa as a task, or reaching it with an operation the
  worker doesn't serve, under a send the runtime's routes refuse as not current;
- a failed assertion on the worker read as a pass, or as anything but the task's failure, so no
  repair is routed; or a repair whose re-run is never sent to the worker, or sent under the old
  send and refused;
- the baseline step's reading not credited at delivery (the scenario played on the baseline
  twice), or delivery judging a tree other than the repaired one;
- a run that starts development with no worker to judge it.
"""

from __future__ import annotations

import json

import pytest

from adapters.remote_execution.fixture_operation_runner import WORLD_PATH
from squadops.campaigns.change_request import stored_change_request, validate_proposal
from squadops.remote_execution.models import AssertionOutcome, OperationStatus
from squadops.remote_execution.workers import OperationState
from tests.unit.campaigns.machinery import answer, compose, edited, emitted
from tests.unit.campaigns.test_product_change_request import _context
from tests.unit.campaigns.test_scenario_criterion import _SCENARIO_PRODUCT, _request
from tests.unit.remote_execution.scenario_fixture import OPEN, SHUT

pytestmark = [pytest.mark.domain_orchestration]

CYCLE = "cyc_machinery01"
RUN = "run_machimpl001"
SCOPE = ("tally/**", ".fixture/**")
#: The developer's first candidate: the panel is built and the door still collides.
HALF_OPEN = {"client": OPEN["client"], "server": SHUT["server"]}


def _world(world: dict) -> str:
    return json.dumps(world, indent=2)


def _change_request() -> str:
    authored = {**_request(), "footprint": [WORLD_PATH]}
    verdict = validate_proposal(authored, _context(scope=SCOPE, product=_SCENARIO_PRODUCT))
    assert verdict.accepted, verdict.refusals
    return stored_change_request(verdict.change_request)


PLAN = {
    "version": 1, "project_id": "prj-tally", "cycle_id": CYCLE, "prd_hash": "abc",
    "summary": {"total_dev_tasks": 1, "total_qa_tasks": 0, "total_tasks": 1},
    "tasks": [
        {"task_index": 0, "task_type": "development.develop", "role": "dev",
         "focus": "the door's panel", "description": "Open the door from its panel.",
         "expected_artifacts": [WORLD_PATH], "acceptance_criteria": []},
    ],
}  # fmt: skip

DONE = {
    "objective": "The door opens from its panel",
    "acceptance_criteria": ["C-2: clicking the panel's button opens the door"],
    "non_goals": ["any change to the ledger"],
    "time_budget_seconds": 300,
    "stop_conditions": ["the door's world can't be read"],
    "required_artifacts": [WORLD_PATH],
}

ANALYSIS = {
    "classification": "work_product",
    "analysis_summary": "door-open fails: Workspace.Door still collides in the world.",
    "contributing_factors": ["the world keeps CanCollide true on Workspace.Door"],
    "implicated_files": [WORLD_PATH],
    "dispute_rulings": [],
}
PATCH = {
    "correction_path": "patch",
    "decision_rationale": "One property in one file.",
    "affected_task_types": ["implementation"],
    "structural_plan_change_candidate": "none",
    "structural_plan_change_rationale": "",
}

#: The increment's script. The developer's first candidate fails the scenario's named assertion
#: on the worker; the failure is analysed, a patch decided, and the repair opens the door.
ANSWERS = [
    answer("governance.define_done", 1, emitted("definition_of_done.json", _world(DONE))),
    answer("development.develop", 1, emitted(WORLD_PATH, _world(HALF_OPEN))),
    answer("data.analyze_failure", 1, json.dumps(ANALYSIS)),
    answer("governance.correction_decision", 1, json.dumps(PATCH)),
    answer(
        "development.correction_repair",
        1,
        edited(WORLD_PATH, '        "CanCollide": true', '        "CanCollide": false'),
    ),
]


@pytest.fixture
async def machinery(tmp_path, monkeypatch):
    world = await compose(tmp_path, monkeypatch)
    await world.increment(
        CYCLE, RUN, change_request=_change_request(), plan=PLAN, answers=ANSWERS,
        allowed_scope=SCOPE,
    )  # fmt: skip
    yield world
    await world.broker.drained()


def _named(operation) -> AssertionOutcome:
    [record] = [r for r in operation.result.records if r.assertion_id == "door-open"]
    return record.outcome


async def test_a_scenario_that_fails_on_the_worker_is_repaired_and_its_candidate_accepted(
    machinery,
):
    async with machinery.worker():
        await machinery.executor.execute_run(CYCLE, RUN, "machinery")

    run = await machinery.registry.get_run(RUN)
    assert run.status == "completed"
    # Plan expansion's step after the plan's body; the failure routed to the developer's repair,
    # and the scenario sent to the worker again on the repaired tree.
    assert machinery.dispatched() == [
        "governance.define_done",
        "development.develop",
        # #3179: the plan authors no suite, so no suite step stands between the developer's
        # task and the play. The workload's own had no file to author on an increment.
        "qa.run_remote_operation",
        "data.analyze_failure",
        "governance.correction_decision",
        "development.correction_repair",
        "qa.run_remote_operation",
    ]
    replies = machinery.replies()
    assert replies[2] == (
        "FAILED",
        "scenario:C-2:door-open: observed 'true', expected 'equals false'",
    )
    assert replies[-1] == ("SUCCEEDED", "")

    # Four operations, each claimed once and settled: the baseline step's on the accepted tree,
    # qa's task and the retest the repair is judged by, and delivery's on the candidate. The baseline reading is
    # credited at delivery, so the baseline is played once.
    baseline, first, rerun, candidate = machinery.operations()
    for operation in (baseline, first, rerun, candidate):
        assert (operation.state, operation.attempt, operation.result.status) == (
            OperationState.SETTLED,
            1,
            OperationStatus.COMPLETED,
        )
    assert baseline.request.task_id.endswith(":C-2:baseline")
    assert candidate.request.task_id.endswith(":C-2:candidate")
    assert (first.origin["agent_id"], rerun.origin["agent_id"]) == ("eve", "eve")
    assert first.request.task_id.startswith("task-run_machimpl")
    assert rerun.request.task_id.startswith("retest-run_machimpl")
    assert [_named(o) for o in (baseline, first, rerun, candidate)] == [
        AssertionOutcome.FAILED, AssertionOutcome.FAILED, AssertionOutcome.PASSED,
        AssertionOutcome.PASSED,
    ]  # fmt: skip
    assert json.loads(baseline.request.source_files[WORLD_PATH]) == SHUT
    assert json.loads(first.request.source_files[WORLD_PATH]) == HALF_OPEN
    assert json.loads(rerun.request.source_files[WORLD_PATH]) == OPEN
    assert json.loads(candidate.request.source_files[WORLD_PATH]) == OPEN

    evaluation = await machinery.evaluation(CYCLE)
    assert evaluation["verdict"] == "accepted"
    [judged] = evaluation["discriminations"]
    assert (judged["criterion_id"], judged["met"], judged["discriminating"]) == (
        "C-2", True, ["door-open"]
    )  # fmt: skip
    assert evaluation["scenario_readings"]["C-2"]["reused"] == ["baseline"]


async def test_with_no_worker_the_run_ends_before_development(machinery):
    """The worker offline before the run starts. Bug caught: development started on a scenario
    no worker can judge, so the squad's work is spent and the increment is judged unread."""
    await machinery.executor.execute_run(CYCLE, RUN, "machinery")

    run = await machinery.registry.get_run(RUN)
    assert run.status == "failed"
    assert run.failure_reason.endswith(
        "C-2: not executed on the baseline: door-open (missing); the operation is not_executed: "
        "no registered worker serves fixture/declared_scenario"
    )
    assert machinery.dispatched() == []
    assert machinery.operations() == []
